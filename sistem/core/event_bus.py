"""
ULTRON Event Bus (Olay Yöneticisi) — v2
═══════════════════════════════════════
Arka plan ajanları (CyberDog, Observer, vb.) ile Ana Thread (Web UI)
arasındaki iletişimi sağlayan Pub/Sub (Yayıncı/Abone) mekanizması.

v2 Yenilikleri:
  • Geriye dönük uyumlu: Mevcut bus.subscribe / bus.publish API'si aynen çalışır
  • Async desteği: async callback'ler otomatik algılanır
  • Wildcard pattern: "camera.*", "user.*", "*" gibi abone olunabilir
  • Standart Event Envelope: UltronEvent ile tipli yayın
  • Cooldown & Deduplication: Aynı event_type tekrar tekrar fırlatılmasını engeller
  • Event geçmişi: Son N event saklanır (debug/observability)

Geriye Dönük Uyumluluk:
  bus.subscribe("ui_alert", callback)   # ✅ eski API çalışır
  bus.publish("ui_alert", "mesaj")      # ✅ eski API çalışır
  bus.subscribe("camera.*", callback)   # ✅ yeni wildcard
  bus.publish_event(UltronEvent(...))   # ✅ yeni tipli API
"""

from __future__ import annotations

import asyncio
import fnmatch
import inspect
import logging
import threading
import time
from collections import deque
from typing import Any, Callable, Deque, Dict, List, Optional, Set, Tuple

from core.events import UltronEvent, EventPriority, EventSource

logger = logging.getLogger("ultron.core.event_bus")

# ── Sabitler ────────────────────────────────────────────────────────────────

DEFAULT_COOLDOWN_SECONDS = 0       # 0 = cooldown yok (geriye dönük uyum)
MAX_EVENT_HISTORY = 200            # Son N event saklanır
DEDUP_WINDOW_SECONDS = 2.0        # Aynı event_type + payload hash penceresi


class EventBus:
    """
    ULTRON Merkezi Event Bus — Singleton.

    Geriye dönük uyumlu eski API:
        bus.subscribe(event_type, callback)
        bus.publish(event_type, data)

    Yeni API:
        bus.subscribe(pattern, callback, priority=EventPriority.NORMAL)
        bus.publish_event(UltronEvent(...))
        bus.unsubscribe(event_type, callback)
        bus.get_history(event_type=None, limit=50)
    """

    _instance: Optional["EventBus"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "EventBus":
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

        # pattern → [(callback, priority)]
        self._subscribers: Dict[str, List[Tuple[Callable, int]]] = {}
        # event_type → last_publish_time (cooldown kontrolü)
        self._cooldowns: Dict[str, float] = {}
        # cooldown süresi ayarları: event_type → seconds
        self._cooldown_config: Dict[str, float] = {}
        # son event geçmişi
        self._history: Deque[UltronEvent] = deque(maxlen=MAX_EVENT_HISTORY)
        # deduplication: (event_type, payload_hash) → timestamp
        self._dedup_cache: Dict[Tuple[str, int], float] = {}

        self._sub_lock = threading.Lock()

    # ── Abone Yönetimi ──────────────────────────────────────────────────────

    def subscribe(
        self,
        event_type: str,
        callback: Callable[[Any], None],
        priority: int = EventPriority.NORMAL,
    ) -> None:
        """
        Belirli bir olay türüne veya desene abone olur.

        Desteklenen desenler:
            "ui_alert"       → Tam eşleşme
            "camera.*"       → camera. ile başlayan tüm olaylar
            "*.error"        → .error ile biten tüm olaylar
            "*"              → Tüm olaylar

        Args:
            event_type: Olay türü veya glob deseni
            callback: Çağrılacak fonksiyon. sync veya async olabilir.
            priority: Abone önceliği (yüksek önce çağrılır)
        """
        with self._sub_lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            # Aynı callback'i tekrar ekleme
            for existing_cb, _ in self._subscribers[event_type]:
                if existing_cb is callback:
                    return
            self._subscribers[event_type].append((callback, int(priority)))
            # Önceliğe göre sırala (yüksek önce)
            self._subscribers[event_type].sort(key=lambda x: x[1], reverse=True)

    def unsubscribe(self, event_type: str, callback: Callable) -> bool:
        """Bir aboneliği kaldırır. Başarılıysa True döner."""
        with self._sub_lock:
            if event_type not in self._subscribers:
                return False
            original_len = len(self._subscribers[event_type])
            self._subscribers[event_type] = [
                (cb, p) for cb, p in self._subscribers[event_type] if cb is not callback
            ]
            if not self._subscribers[event_type]:
                del self._subscribers[event_type]
            return len(self._subscribers.get(event_type, [])) < original_len

    # ── Yayın (Publish) ─────────────────────────────────────────────────────

    def publish(self, event_type: str, data: Any = None) -> None:
        """
        Eski API uyumlu yayın. Mevcut tüm publisher'lar bunu kullanıyor.

        Otomatik olarak UltronEvent zarfına sarar ve tüm eşleşen
        abone callback'lerine iletir.
        """
        # Eski API: data herhangi bir şey olabilir (str, dict, vb.)
        if isinstance(data, dict):
            payload = data
        elif data is not None:
            payload = {"value": data}
        else:
            payload = {}

        event = UltronEvent(
            event_type=event_type,
            source=EventSource.SYSTEM,
            payload=payload,
            priority=EventPriority.NORMAL,
        )
        self._dispatch(event, legacy_data=data)

    def publish_event(self, event: UltronEvent) -> None:
        """Tipli event yayınlar. Yeni API."""
        self._dispatch(event)

    # ── Dispatch (İç Mekanizma) ──────────────────────────────────────────────

    def _dispatch(self, event: UltronEvent, legacy_data: Any = None) -> None:
        """Olayı tüm eşleşen abonelere iletir."""

        # Cooldown kontrolü
        cooldown = self._cooldown_config.get(event.event_type, DEFAULT_COOLDOWN_SECONDS)
        if cooldown > 0:
            now = time.time()
            last = self._cooldowns.get(event.event_type, 0)
            if now - last < cooldown:
                logger.debug(
                    f"[EventBus] Cooldown: {event.event_type} ({cooldown}s içinde tekrar)"
                )
                return
            self._cooldowns[event.event_type] = now

        # Deduplication kontrolü
        if self._is_duplicate(event):
            logger.debug(f"[EventBus] Dedup: {event.event_type} (son {DEDUP_WINDOW_SECONDS}s)")
            return

        # Geçmişe kaydet
        self._history.append(event)

        # Eşleşen aboneleri topla
        matched_callbacks = self._match_subscribers(event.event_type)

        # Callback'leri çağır
        for callback, _priority in matched_callbacks:
            try:
                if inspect.iscoroutinefunction(callback):
                    # Async callback — çalışan event loop varsa orada çalıştır
                    self._run_async_callback(callback, event, legacy_data)
                else:
                    # Sync callback — geriye dönük uyumluluk: eski data ile çağır
                    if legacy_data is not None:
                        callback(legacy_data)
                    else:
                        callback(event.payload)
            except Exception as e:
                logger.error(
                    f"[EventBus] '{event.event_type}' abonesinde hata: {e}",
                    exc_info=True
                )

        if matched_callbacks:
            logger.debug(
                f"[EventBus] {event.event_type} → {len(matched_callbacks)} abone "
                f"(prio={event.priority.name}, id={event.event_id})"
            )

    def _match_subscribers(self, event_type: str) -> List[Tuple[Callable, int]]:
        """Olay türüne eşleşen tüm aboneleri döner (öncelik sıralı)."""
        matched = []
        with self._sub_lock:
            for pattern, subs in self._subscribers.items():
                if self._pattern_matches(pattern, event_type):
                    matched.extend(subs)
        # Önceliğe göre sırala (yüksek önce)
        matched.sort(key=lambda x: x[1], reverse=True)
        return matched

    @staticmethod
    def _pattern_matches(pattern: str, event_type: str) -> bool:
        """Pattern eşleşme kontrolü.

        Desteklenen:
            "ui_alert" == "ui_alert"            → True (tam eşleşme)
            "camera.*" vs "camera.face_detected" → True (wildcard)
            "*" vs herhangi                      → True (tümü)
        """
        if pattern == event_type:
            return True
        if "*" in pattern:
            return fnmatch.fnmatch(event_type, pattern)
        return False

    # ── Async Köprüsü ───────────────────────────────────────────────────────

    @staticmethod
    def _run_async_callback(callback: Callable, event: UltronEvent, legacy_data: Any) -> None:
        """Async callback'i mevcut event loop'ta çalıştırır."""
        try:
            loop = asyncio.get_running_loop()
            if legacy_data is not None:
                asyncio.run_coroutine_threadsafe(callback(legacy_data), loop)
            else:
                asyncio.run_coroutine_threadsafe(callback(event.payload), loop)
        except RuntimeError:
            # Çalışan event loop yok — yeni bir loop'ta çalıştır
            try:
                asyncio.run(callback(event.payload if legacy_data is None else legacy_data))
            except Exception as e:
                logger.error(f"[EventBus] Async callback hatası: {e}")

    # ── Deduplication ───────────────────────────────────────────────────────

    def _is_duplicate(self, event: UltronEvent) -> bool:
        """Aynı event_type + payload'un kısa süre içinde tekrarını engeller."""
        try:
            payload_hash = hash(str(sorted(event.payload.items())) if event.payload else "")
        except (TypeError, AttributeError):
            payload_hash = hash(str(event.payload))

        key = (event.event_type, payload_hash)
        now = time.time()

        # Eski girişleri temizle (lazy cleanup)
        expired = [k for k, t in self._dedup_cache.items() if now - t > DEDUP_WINDOW_SECONDS]
        for k in expired:
            del self._dedup_cache[k]

        if key in self._dedup_cache:
            return True
        self._dedup_cache[key] = now
        return False

    # ── Cooldown Yapılandırma ───────────────────────────────────────────────

    def set_cooldown(self, event_type: str, seconds: float) -> None:
        """Belirli bir event türü için minimum yayın aralığı belirler."""
        self._cooldown_config[event_type] = seconds

    # ── Geçmiş & Gözlemlenebilirlik ─────────────────────────────────────────

    def get_history(
        self,
        event_type: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict]:
        """Son event geçmişini döner. Opsiyonel filtre."""
        events = list(self._history)
        if event_type:
            events = [e for e in events if self._pattern_matches(event_type, e.event_type)]
        return [e.to_dict() for e in events[-limit:]]

    def get_subscriber_count(self) -> Dict[str, int]:
        """Her event türü/pattern için abone sayısını döner."""
        with self._sub_lock:
            return {k: len(v) for k, v in self._subscribers.items()}

    def reset(self) -> None:
        """Test ve debug için tüm state'i sıfırlar."""
        with self._sub_lock:
            self._subscribers.clear()
        self._cooldowns.clear()
        self._cooldown_config.clear()
        self._history.clear()
        self._dedup_cache.clear()


# ── Global Singleton ────────────────────────────────────────────────────────
bus = EventBus()
