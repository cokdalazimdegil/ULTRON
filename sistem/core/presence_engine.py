"""
ULTRON Presence Engine — Varlık Durum Makinesi
═══════════════════════════════════════════════
Kamera, sistem aktiviteleri ve konum bilgilerini birleştirerek
kullanıcının varlık durumunu yöneten state machine.

Durumlar:
    UNKNOWN → PERSON_DETECTED → USER_PRESENT → USER_AWAY → USER_LEFT

Kullanım:
    from core.presence_engine import presence_engine, PresenceState

    # Observer daemon bağlantısı (otomatik):
    presence_engine.start()

    # Manuel durum kontrolü:
    state = presence_engine.get_state()
    print(f"Kullanıcı durumu: {state.name}")
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from core.events import UltronEvent, EventPriority, EventSource

logger = logging.getLogger("ultron.core.presence_engine")


# ── Varlık Durumları ────────────────────────────────────────────────────────

class PresenceState(str, Enum):
    """Kullanıcı varlık durumları."""
    UNKNOWN         = "unknown"          # Başlangıç / belirsiz
    PERSON_DETECTED = "person_detected"  # Kamerada kişi var ama kim bilinmiyor
    USER_PRESENT    = "user_present"     # Kullanıcı tespit ve doğrulanmış
    USER_AWAY       = "user_away"        # Kullanıcı kısa süredir yok (geçiş durumu)
    USER_LEFT       = "user_left"        # Kullanıcı kesinlikle ayrılmış


# ── Geçiş Kuralları ────────────────────────────────────────────────────────

# (mevcut_durum, tetikleyici) → yeni_durum
TRANSITIONS = {
    (PresenceState.UNKNOWN, "person_detected"):          PresenceState.PERSON_DETECTED,
    (PresenceState.UNKNOWN, "user_identified"):          PresenceState.USER_PRESENT,
    (PresenceState.PERSON_DETECTED, "user_identified"):  PresenceState.USER_PRESENT,
    (PresenceState.PERSON_DETECTED, "no_person"):        PresenceState.UNKNOWN,
    (PresenceState.USER_PRESENT, "no_person"):           PresenceState.USER_AWAY,
    (PresenceState.USER_AWAY, "person_detected"):        PresenceState.USER_PRESENT,
    (PresenceState.USER_AWAY, "user_identified"):        PresenceState.USER_PRESENT,
    (PresenceState.USER_AWAY, "timeout"):                PresenceState.USER_LEFT,
    (PresenceState.USER_LEFT, "person_detected"):        PresenceState.PERSON_DETECTED,
    (PresenceState.USER_LEFT, "user_identified"):        PresenceState.USER_PRESENT,
}


# ── Presence Engine ─────────────────────────────────────────────────────────

class PresenceEngine:
    """
    Kullanıcı varlık durumu state machine.

    Observer daemon'dan gelen ham kamera event'lerini alır,
    debounce uygular ve anlamlı durum geçişlerini Event Bus'a yayınlar.
    """

    _instance: Optional["PresenceEngine"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "PresenceEngine":
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

        self._state: PresenceState = PresenceState.UNKNOWN
        self._last_state_change: float = 0
        self._last_person_seen: float = 0
        self._last_greeting_time: float = 0

        # Yapılandırma
        self._away_timeout: float = 120.0       # USER_AWAY → USER_LEFT süresi (saniye)
        self._debounce_interval: float = 5.0    # Aynı durum geçişi minimum aralığı
        self._greeting_cooldown: float = 1800.0 # Karşılama arası minimum süre (30 dk)

        # Event Bus referansı (lazy)
        self._bus = None
        # State lock
        self._state_lock = threading.Lock()
        # Away timer thread
        self._away_timer: Optional[threading.Timer] = None
        # Listeners
        self._on_state_change_callbacks: List[Callable] = []
        # Started flag
        self._started = False

    # ── Yaşam Döngüsü ──────────────────────────────────────────────────────

    def start(self) -> None:
        """Presence engine'i başlatır ve Event Bus'a abone olur."""
        if self._started:
            return

        bus = self._get_bus()
        if bus:
            # Observer daemon'dan gelen ham event'lere abone ol
            bus.subscribe("observer_presence", self._on_observer_presence)
            bus.subscribe("observer_mood", self._on_observer_mood)
            # Konum event'lerine de abone ol
            bus.subscribe("user.location.*", self._on_location_event)
            logger.info("[PresenceEngine] Event Bus abonelikleri kuruldu.")

        self._started = True
        logger.info(f"[PresenceEngine] Başlatıldı. Durum: {self._state.value}")

    def stop(self) -> None:
        """Presence engine'i durdurur."""
        if self._away_timer:
            self._away_timer.cancel()
            self._away_timer = None
        self._started = False
        logger.info("[PresenceEngine] Durduruldu.")

    # ── Event Bus ───────────────────────────────────────────────────────────

    def _get_bus(self):
        if self._bus is None:
            try:
                from core.event_bus import bus
                self._bus = bus
            except ImportError:
                pass
        return self._bus

    # ── Observer Event Handler'ları ─────────────────────────────────────────

    def _on_observer_presence(self, data: Any) -> None:
        """Observer daemon'dan gelen varlık event'lerini işler."""
        if isinstance(data, dict):
            is_present = data.get("present", False)
        else:
            is_present = bool(data)

        if is_present:
            # Şimdilik yüz tanıma yok → person_detected olarak kabul et
            # Gelecekte InsightFace entegre edildiğinde user_identified kullanılacak
            self._trigger("person_detected")
            self._last_person_seen = time.time()

            # USER_AWAY iken kişi görüldüyse, bu aynı kullanıcı varsayımı
            if self._state == PresenceState.USER_AWAY:
                self._trigger("user_identified")
        else:
            self._trigger("no_person")

    def _on_observer_mood(self, data: Any) -> None:
        """Ruh hali değişikliğini metadata olarak saklar."""
        if isinstance(data, dict):
            mood = data.get("mood", "")
            if mood:
                # Ruh hali var → kullanıcı kesinlikle mevcut
                if self._state in (PresenceState.UNKNOWN, PresenceState.PERSON_DETECTED):
                    self._trigger("user_identified")

    def _on_location_event(self, data: Any) -> None:
        """Konum event'lerini işler (user.location.changed, user.arrived_home)."""
        if isinstance(data, dict):
            event_type = data.get("event_type", "")
            if "arrived_home" in str(event_type):
                self._trigger("user_identified")

    # ── State Machine ───────────────────────────────────────────────────────

    def _trigger(self, trigger: str) -> None:
        """Durum geçişi tetikler."""
        with self._state_lock:
            key = (self._state, trigger)
            new_state = TRANSITIONS.get(key)

            if new_state is None:
                return  # Geçersiz geçiş — sessizce geç

            if new_state == self._state:
                return  # Aynı durum — geçiş yok

            # Debounce kontrolü
            now = time.time()
            if now - self._last_state_change < self._debounce_interval:
                logger.debug(
                    f"[PresenceEngine] Debounce: {self._state.value} → {new_state.value} "
                    f"({self._debounce_interval}s içinde)"
                )
                return

            old_state = self._state
            self._state = new_state
            self._last_state_change = now

            logger.info(f"[PresenceEngine] Durum geçişi: {old_state.value} → {new_state.value}")

        # Away timer yönetimi
        if new_state == PresenceState.USER_AWAY:
            self._start_away_timer()
        else:
            self._cancel_away_timer()

        # Event Bus'a yayınla
        self._publish_state_change(old_state, new_state, trigger)

        # Karşılama kontrolü
        if (
            new_state == PresenceState.USER_PRESENT
            and old_state in (PresenceState.UNKNOWN, PresenceState.USER_LEFT, PresenceState.PERSON_DETECTED)
        ):
            self._maybe_greet()

        # Callback'leri çağır
        for cb in self._on_state_change_callbacks:
            try:
                cb(old_state, new_state)
            except Exception as e:
                logger.error(f"[PresenceEngine] Callback hatası: {e}")

    # ── Away Timer ──────────────────────────────────────────────────────────

    def _start_away_timer(self) -> None:
        """USER_AWAY → USER_LEFT geçişi için zamanlayıcı başlatır."""
        self._cancel_away_timer()
        self._away_timer = threading.Timer(self._away_timeout, self._away_timeout_handler)
        self._away_timer.daemon = True
        self._away_timer.start()

    def _cancel_away_timer(self) -> None:
        if self._away_timer:
            self._away_timer.cancel()
            self._away_timer = None

    def _away_timeout_handler(self) -> None:
        """Away timeout'u doldu → USER_LEFT."""
        self._trigger("timeout")

    # ── Karşılama ───────────────────────────────────────────────────────────

    def _maybe_greet(self) -> None:
        """Kullanıcı geldiğinde karşılama kontrolü."""
        now = time.time()
        if now - self._last_greeting_time < self._greeting_cooldown:
            logger.debug("[PresenceEngine] Karşılama cooldown aktif — atlanıyor")
            return

        self._last_greeting_time = now

        bus = self._get_bus()
        if bus:
            bus.publish_event(UltronEvent(
                event_type="presence.greeting_due",
                source=EventSource.SYSTEM,
                payload={"state": PresenceState.USER_PRESENT.value},
                priority=EventPriority.HIGH,
            ))
            logger.info("[PresenceEngine] Karşılama event'i fırlatıldı: presence.greeting_due")

    # ── Event Yayını ────────────────────────────────────────────────────────

    def _publish_state_change(self, old_state: PresenceState, new_state: PresenceState, trigger: str) -> None:
        """Durum değişikliğini Event Bus'a yayınlar."""
        bus = self._get_bus()
        if bus:
            bus.publish_event(UltronEvent(
                event_type=f"presence.{new_state.value}",
                source=EventSource.CAMERA,
                payload={
                    "old_state": old_state.value,
                    "new_state": new_state.value,
                    "trigger": trigger,
                    "timestamp": time.time(),
                },
                priority=EventPriority.NORMAL,
            ))

    # ── Public API ──────────────────────────────────────────────────────────

    def get_state(self) -> PresenceState:
        """Mevcut varlık durumunu döner."""
        return self._state

    def get_state_info(self) -> Dict[str, Any]:
        """Detaylı durum bilgisi."""
        return {
            "state": self._state.value,
            "last_change": self._last_state_change,
            "last_person_seen": self._last_person_seen,
            "seconds_in_state": (time.time() - self._last_state_change) if self._last_state_change > 0 else 0,
            "away_timeout": self._away_timeout,
            "greeting_cooldown": self._greeting_cooldown,
        }

    def on_state_change(self, callback: Callable) -> None:
        """Durum değişikliği callback'i kaydeder."""
        self._on_state_change_callbacks.append(callback)

    # ── Yapılandırma ────────────────────────────────────────────────────────

    def configure(
        self,
        away_timeout: Optional[float] = None,
        debounce_interval: Optional[float] = None,
        greeting_cooldown: Optional[float] = None,
    ) -> None:
        """Motor yapılandırmasını günceller."""
        if away_timeout is not None:
            self._away_timeout = away_timeout
        if debounce_interval is not None:
            self._debounce_interval = debounce_interval
        if greeting_cooldown is not None:
            self._greeting_cooldown = greeting_cooldown

    def reset(self) -> None:
        """Test için state sıfırlama."""
        with self._state_lock:
            self._state = PresenceState.UNKNOWN
            self._last_state_change = 0
            self._last_person_seen = 0
            self._last_greeting_time = 0
            self._on_state_change_callbacks.clear()
        self._cancel_away_timer()


# ── Global Singleton ────────────────────────────────────────────────────────
presence_engine = PresenceEngine()
