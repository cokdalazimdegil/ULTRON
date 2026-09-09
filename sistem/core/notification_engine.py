"""
ULTRON Notification Engine — Merkezi Bildirim Motoru
═══════════════════════════════════════════════════
Tüm ULTRON bileşenlerinden gelen bildirimleri yöneten merkezi motor.

Özellikler:
  • Çok kanallı dağıtım: TTS, WebSocket UI, Desktop Toast, Telegram, HA
  • Öncelik bazlı yönlendirme: LOW → sadece log, NORMAL → UI, HIGH → UI+TTS, CRITICAL → tümü
  • Cooldown: Aynı türde bildirimin minimum aralığı
  • Deduplication: Aynı mesajın kısa sürede tekrarını engeller
  • Quiet Hours: Sessiz saatlerde düşük öncelikli bildirimleri bastırır
  • Acknowledgement: Kritik bildirimlerin kabul edilip edilmediğini izler
  • Event Bus entegrasyonu: notification.* event'leri fırlatır

Kullanım:
    from core.notification_engine import notification_engine, NotificationRequest

    notification_engine.notify(NotificationRequest(
        title="Yeni E-posta",
        message="Ali'den önemli bir e-posta geldi",
        priority=EventPriority.HIGH,
        source="email",
        channels=["tts", "web_ui"],
    ))
"""

from __future__ import annotations

import hashlib
import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

from core.events import UltronEvent, EventPriority, EventSource

logger = logging.getLogger("ultron.core.notification_engine")


# ── Bildirim Kanalları ──────────────────────────────────────────────────────

class NotificationChannel(str, Enum):
    """Desteklenen bildirim kanalları."""
    TTS       = "tts"           # Yerel SAPI5 sesli okuma
    WEB_UI    = "web_ui"        # WebSocket push → tarayıcı/PyWebView
    GEMINI    = "gemini"        # Gemini Live oturumuna mesaj → AI sesli anlatsın
    DESKTOP   = "desktop"       # Windows Toast bildirimi (gelecek)
    TELEGRAM  = "telegram"      # Telegram Bot mesajı (gelecek)
    HOME_ASSISTANT = "ha"       # HA persistent_notification (gelecek)
    LOG_ONLY  = "log_only"      # Sadece log kaydı


# ── Bildirim İsteği ─────────────────────────────────────────────────────────

@dataclass
class NotificationRequest:
    """
    Bildirim isteği. Herhangi bir ULTRON bileşeni bunu oluşturarak
    notification_engine.notify() ile gönderir.
    """
    title: str
    message: str
    priority: EventPriority = EventPriority.NORMAL
    source: str = EventSource.SYSTEM
    channels: Optional[List[str]] = None  # None = otomatik seç
    metadata: Dict[str, Any] = field(default_factory=dict)
    # Cooldown key — aynı key ile gelen bildirimler cooldown'a tabi
    cooldown_key: Optional[str] = None
    # Acknowledgement gerekiyor mu?
    requires_ack: bool = False


# ── Bildirim Sonucu ─────────────────────────────────────────────────────────

@dataclass
class NotificationResult:
    """Bildirim gönderim sonucu."""
    delivered: bool
    channels_used: List[str]
    suppressed_reason: Optional[str] = None


# ── Varsayılan Kanal Politikaları ───────────────────────────────────────────

# Öncelik → otomatik kanallar eşlemesi
DEFAULT_CHANNEL_POLICY: Dict[EventPriority, List[str]] = {
    EventPriority.LOW:      [NotificationChannel.LOG_ONLY],
    EventPriority.NORMAL:   [NotificationChannel.WEB_UI],
    EventPriority.HIGH:     [NotificationChannel.WEB_UI, NotificationChannel.GEMINI],
    EventPriority.CRITICAL: [NotificationChannel.WEB_UI, NotificationChannel.GEMINI, NotificationChannel.TTS],
}


# ── Merkezi Bildirim Motoru ─────────────────────────────────────────────────

class NotificationEngine:
    """ULTRON Merkezi Bildirim Motoru — Singleton."""

    _instance: Optional["NotificationEngine"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "NotificationEngine":
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._initialized = False
                cls._instance = inst
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        # Kanal → handler fonksiyonu eşlemesi
        self._channel_handlers: Dict[str, Callable] = {}
        # Cooldown: key → last_sent_time
        self._cooldowns: Dict[str, float] = {}
        # Dedup: message_hash → timestamp
        self._dedup_cache: Dict[str, float] = {}
        # Cooldown süresi (saniye): key_prefix → seconds
        self._cooldown_durations: Dict[str, float] = {}
        # Varsayılan cooldown
        self._default_cooldown: float = 30.0  # 30 saniye
        # Dedup penceresi
        self._dedup_window: float = 10.0  # 10 saniye
        # Quiet hours
        self._quiet_start: int = 23  # Gece 23:00
        self._quiet_end: int = 7    # Sabah 07:00
        self._quiet_enabled: bool = False
        # İstatistikler
        self._stats: Dict[str, int] = {
            "total_sent": 0,
            "total_suppressed": 0,
            "by_channel": {},
        }
        self._history: List[Dict[str, Any]] = []
        # Event bus referansı (lazy)
        self._bus = None
        # Threading lock for state
        self._state_lock = threading.Lock()

    # ── Event Bus Bağlantısı ────────────────────────────────────────────────

    def _get_bus(self):
        """Lazy event bus erişimi."""
        if self._bus is None:
            try:
                from core.event_bus import bus
                self._bus = bus
            except ImportError:
                logger.warning("[NotificationEngine] Event bus import edilemedi")
        return self._bus

    # ── Kanal Handler Kaydı ─────────────────────────────────────────────────

    def register_channel(self, channel: str, handler: Callable) -> None:
        """
        Bir bildirim kanalı için handler fonksiyonu kaydeder.

        Handler imzası:
            def handler(title: str, message: str, priority: EventPriority, metadata: dict) -> bool
            async def handler(...) -> bool  # async de olabilir

        Returns True eğer başarılı gönderildi.
        """
        self._channel_handlers[channel] = handler
        logger.info(f"[NotificationEngine] Kanal kaydedildi: {channel}")

    def unregister_channel(self, channel: str) -> None:
        """Bir kanal handler'ını kaldırır."""
        self._channel_handlers.pop(channel, None)

    # ── Ana Bildirim Metodu ─────────────────────────────────────────────────

    def notify(
        self,
        request: Optional[NotificationRequest] = None,
        *,
        title: str = "",
        message: str = "",
        priority: EventPriority = EventPriority.NORMAL,
        channels: Optional[List[str]] = None,
        source: str = "system",
        cooldown_key: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> NotificationResult:
        """
        Bildirim gönderir. Cooldown, dedup, quiet hours kontrolleri yapılır.
        Hem NotificationRequest nesnesi hem de doğrudan anahtar kelime argümanları kabul eder.

        Returns:
            NotificationResult — sonuç bilgisi
        """
        if request is None:
            request = NotificationRequest(
                title=title,
                message=message,
                priority=priority,
                channels=channels,
                source=source,
                cooldown_key=cooldown_key,
                metadata=metadata or {},
            )
        # 1. Quiet Hours kontrolü
        if self._is_quiet_time() and request.priority <= EventPriority.NORMAL:
            logger.debug(f"[NotificationEngine] Quiet hours: '{request.title}' bastırıldı")
            self._stats["total_suppressed"] += 1
            return NotificationResult(
                delivered=False,
                channels_used=[],
                suppressed_reason="quiet_hours"
            )

        # 2. Cooldown kontrolü
        cooldown_key = request.cooldown_key or f"{request.source}:{request.title}"
        if self._is_on_cooldown(cooldown_key):
            logger.debug(f"[NotificationEngine] Cooldown: '{cooldown_key}' bastırıldı")
            self._stats["total_suppressed"] += 1
            return NotificationResult(
                delivered=False,
                channels_used=[],
                suppressed_reason="cooldown"
            )

        # 3. Deduplication kontrolü
        msg_hash = self._hash_message(request.title, request.message)
        if self._is_duplicate(msg_hash):
            logger.debug(f"[NotificationEngine] Dedup: '{request.title}' bastırıldı")
            self._stats["total_suppressed"] += 1
            return NotificationResult(
                delivered=False,
                channels_used=[],
                suppressed_reason="duplicate"
            )

        # 4. Kanalları belirle
        channels = request.channels
        if channels is None:
            channels = DEFAULT_CHANNEL_POLICY.get(
                request.priority,
                [NotificationChannel.WEB_UI]
            )

        # 5. Her kanala gönder
        channels_used = []
        for channel in channels:
            channel_str = channel.value if isinstance(channel, NotificationChannel) else str(channel)
            handler = self._channel_handlers.get(channel_str)

            if handler is not None:
                try:
                    success = handler(
                        title=request.title,
                        message=request.message,
                        priority=request.priority,
                        metadata=request.metadata,
                    )
                    if success is not False:  # None veya True = başarılı
                        channels_used.append(channel_str)
                except Exception as e:
                    logger.error(
                        f"[NotificationEngine] Kanal hatası ({channel_str}): {e}",
                        exc_info=True
                    )
            else:
                # Handler kayıtlı değilse log'la
                if channel_str != NotificationChannel.LOG_ONLY:
                    logger.debug(f"[NotificationEngine] Handler yok: {channel_str}")

        # 6. Log kaydı (her zaman)
        log_level = logging.WARNING if request.priority >= EventPriority.HIGH else logging.INFO
        logger.log(
            log_level,
            f"[NOTIFICATION] [{request.priority.name}] {request.title}: {request.message} "
            f"→ channels={channels_used}"
        )

        # 7. Cooldown ve dedup güncelle
        self._update_cooldown(cooldown_key)
        self._update_dedup(msg_hash)

        # 8. İstatistik ve geçmiş güncelle
        with self._state_lock:
            self._stats["total_sent"] += 1
            for ch in channels_used:
                self._stats["by_channel"][ch] = self._stats["by_channel"].get(ch, 0) + 1
            self._history.append({
                "title": request.title,
                "message": request.message,
                "priority": request.priority.name,
                "channels": channels_used,
                "timestamp": time.time(),
            })
            if len(self._history) > 100:
                self._history.pop(0)

        # 9. Event Bus'a yayınla
        bus = self._get_bus()
        if bus:
            try:
                bus.publish_event(UltronEvent(
                    event_type="notification.sent",
                    source=EventSource.SYSTEM,
                    payload={
                        "title": request.title,
                        "message": request.message,
                        "channels": channels_used,
                        "priority": int(request.priority),
                        "source": request.source,
                    },
                    priority=request.priority,
                ))
            except Exception:
                pass

        return NotificationResult(
            delivered=len(channels_used) > 0,
            channels_used=channels_used,
        )

    # ── Cooldown Yönetimi ───────────────────────────────────────────────────

    def _is_on_cooldown(self, key: str) -> bool:
        with self._state_lock:
            last = self._cooldowns.get(key, 0)
            duration = self._cooldown_durations.get(
                key.split(":")[0], self._default_cooldown
            )
            return (time.time() - last) < duration

    def _update_cooldown(self, key: str) -> None:
        with self._state_lock:
            self._cooldowns[key] = time.time()

    def set_cooldown(self, source_prefix: str, seconds: float) -> None:
        """Belirli bir kaynak için cooldown süresi ayarlar."""
        self._cooldown_durations[source_prefix] = seconds

    # ── Deduplication ───────────────────────────────────────────────────────

    @staticmethod
    def _hash_message(title: str, message: str) -> str:
        return hashlib.md5(f"{title}:{message}".encode()).hexdigest()[:16]

    def _is_duplicate(self, msg_hash: str) -> bool:
        with self._state_lock:
            now = time.time()
            # Eski girdileri temizle
            expired = [k for k, t in self._dedup_cache.items() if now - t > self._dedup_window]
            for k in expired:
                del self._dedup_cache[k]
            return msg_hash in self._dedup_cache

    def _update_dedup(self, msg_hash: str) -> None:
        with self._state_lock:
            self._dedup_cache[msg_hash] = time.time()

    # ── Quiet Hours ─────────────────────────────────────────────────────────

    def _is_quiet_time(self) -> bool:
        if not self._quiet_enabled:
            return False
        import datetime
        hour = datetime.datetime.now().hour
        if self._quiet_start > self._quiet_end:
            # Gece geçişi (örn: 23-07)
            return hour >= self._quiet_start or hour < self._quiet_end
        return self._quiet_start <= hour < self._quiet_end

    def set_quiet_hours(self, start_hour: int, end_hour: int, enabled: bool = True) -> None:
        """Quiet hours yapılandırması."""
        self._quiet_start = start_hour
        self._quiet_end = end_hour
        self._quiet_enabled = enabled
        logger.info(f"[NotificationEngine] Quiet hours: {start_hour}:00-{end_hour}:00 ({'aktif' if enabled else 'pasif'})")

    # ── İstatistikler & Geçmiş ──────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Bildirim istatistiklerini döner."""
        with self._state_lock:
            return dict(self._stats)

    def get_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Son gönderilen bildirimlerin geçmişini döner."""
        with self._state_lock:
            return list(reversed(self._history[-limit:]))

    # ── Yapılandırma ────────────────────────────────────────────────────────

    def configure(
        self,
        default_cooldown: Optional[float] = None,
        dedup_window: Optional[float] = None,
    ) -> None:
        """Motor yapılandırmasını günceller."""
        if default_cooldown is not None:
            self._default_cooldown = default_cooldown
        if dedup_window is not None:
            self._dedup_window = dedup_window

    def reset(self) -> None:
        """Test için state sıfırlama."""
        with self._state_lock:
            self._cooldowns.clear()
            self._dedup_cache.clear()
            self._history.clear()
            self._stats = {"total_sent": 0, "total_suppressed": 0, "by_channel": {}}


# ── Global Singleton ────────────────────────────────────────────────────────
notification_engine = NotificationEngine()
