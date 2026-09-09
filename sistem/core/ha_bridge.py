"""
ULTRON Home Assistant Bridge — Çift Yönlü Akıllı Ev Köprüsü
════════════════════════════════════════════════════════════
Home Assistant ile ULTRON Event Bus arasında çift yönlü entegrasyon:
1. HA → ULTRON: Webhook veya Event Bus üzerinden gelen HA sensör/kişi durumlarını işler.
2. ULTRON → HA: Kullanıcı eve geldiğinde/ayrıldığında otomatik HA servis çağrısı yapar.
3. NotificationEngine 'ha' kanalı: Kritik bildirimleri HA persistent_notification olarak basar.

Kullanım:
    from core.ha_bridge import ha_bridge
    ha_bridge.start()
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, Optional

import requests

from app_config import get_app_config_value
from core.events import UltronEvent, EventPriority, EventSource

logger = logging.getLogger("ultron.core.ha_bridge")


class HomeAssistantBridge:
    """Home Assistant çift yönlü entegrasyon köprüsü."""

    _instance: Optional["HomeAssistantBridge"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "HomeAssistantBridge":
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

        self._bus = None
        self._started = False
        self._on_arrive_actions: list = []
        self._on_leave_actions: list = []

    def _get_bus(self):
        if self._bus is None:
            try:
                from core.event_bus import bus
                self._bus = bus
            except ImportError:
                pass
        return self._bus

    def _get_ha_config(self) -> tuple[str, str]:
        """HA URL ve token bilgilerini config'ten alır."""
        url = str(get_app_config_value("home_assistant_url", "") or "").rstrip("/")
        token = str(get_app_config_value("home_assistant_token", "") or "")
        return url, token

    # ── Yaşam Döngüsü ──────────────────────────────────────────────────────

    def start(self) -> None:
        """HA Bridge'i başlatır, Event Bus ve NotificationEngine'e kaydeder."""
        if self._started:
            return

        bus = self._get_bus()
        if bus:
            # Gelen HA event'leri dinle
            bus.subscribe("ha.*", self._on_ha_event)
            # Konum geofence event'lerini dinle
            bus.subscribe("user.arrived_home", self._on_user_arrived_home)
            bus.subscribe("user.left_home", self._on_user_left_home)
            # Doğrudan servis çağırma event'ini dinle
            bus.subscribe("ha.service.call", self._on_service_call_request)
            logger.info("[HABridge] Event Bus abonelikleri kuruldu.")

        # NotificationEngine'e HA kanalını kaydet
        try:
            from core.notification_engine import notification_engine, NotificationChannel
            notification_engine.register_channel_handler(
                NotificationChannel.HOME_ASSISTANT,
                self._notification_handler,
            )
            logger.info("[HABridge] NotificationEngine HA kanalı kaydedildi.")
        except Exception as e:
            logger.debug(f"[HABridge] NotificationEngine kaydı atlandı: {e}")

        self._started = True
        logger.info("[HABridge] Başlatıldı.")

    def stop(self) -> None:
        """HA Bridge'i durdurur."""
        self._started = False
        logger.info("[HABridge] Durduruldu.")

    # ── Event Handler'ları ──────────────────────────────────────────────────

    def _on_ha_event(self, data: Any) -> None:
        """Home Assistant'tan gelen event'leri işler."""
        if not isinstance(data, dict):
            return
        entity_id = str(data.get("entity_id", ""))
        new_state = str(data.get("state", ""))

        # HA person entity 'home' olduysa PresenceEngine'e bildir
        if entity_id.startswith("person.") and new_state.lower() == "home":
            try:
                from core.presence_engine import presence_engine
                presence_engine._trigger("user_identified")
                logger.info(f"[HABridge] HA person '{entity_id}' evde → PresenceEngine güncellendi.")
            except Exception:
                pass

    def _on_user_arrived_home(self, data: Any) -> None:
        """Kullanıcı eve vardığında (geofence) HA otomasyonlarını tetikler."""
        logger.info("[HABridge] 🏠 Kullanıcı eve vardı — karşılama senaryosu kontrol ediliyor.")
        url, token = self._get_ha_config()
        if not url or not token:
            return

        # Varsa configured arrive scene/action çağır
        arrive_scene = str(get_app_config_value("ha_arrive_scene", "") or "").strip()
        if arrive_scene:
            self.call_service("scene", "turn_on", {"entity_id": arrive_scene})

    def _on_user_left_home(self, data: Any) -> None:
        """Kullanıcı evden ayrıldığında HA otomasyonlarını tetikler."""
        logger.info("[HABridge] 🚶 Kullanıcı evden ayrıldı — ayrılış senaryosu kontrol ediliyor.")
        url, token = self._get_ha_config()
        if not url or not token:
            return

        leave_scene = str(get_app_config_value("ha_leave_scene", "") or "").strip()
        if leave_scene:
            self.call_service("scene", "turn_on", {"entity_id": leave_scene})

    def _on_service_call_request(self, data: Any) -> None:
        """Event Bus üzerinden HA servis çağırma isteği."""
        if not isinstance(data, dict):
            return
        domain = data.get("domain", "homeassistant")
        service = data.get("service", "")
        service_data = data.get("service_data", {})
        if service:
            self.call_service(domain, service, service_data)

    # ── Outbound REST Servis Çağrısı ────────────────────────────────────────

    def call_service(self, domain: str, service: str, service_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Home Assistant REST API üzerinden servis çağırır."""
        url, token = self._get_ha_config()
        if not url or not token:
            return {"status": "error", "message": "Home Assistant URL veya token yapılandırılmamış."}

        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        endpoint = f"{url}/api/services/{domain}/{service}"
        try:
            res = requests.post(endpoint, headers=headers, json=service_data or {}, timeout=5)
            if res.status_code in (200, 201):
                logger.info(f"[HABridge] Servis çağrısı başarılı: {domain}.{service}")
                return {"status": "ok", "status_code": res.status_code}
            logger.warning(f"[HABridge] Servis çağrısı başarısız ({res.status_code}): {res.text[:100]}")
            return {"status": "error", "status_code": res.status_code, "message": res.text[:200]}
        except Exception as e:
            logger.error(f"[HABridge] Servis çağrısı hatası: {e}")
            return {"status": "error", "message": str(e)}

    # ── NotificationEngine Kanal Handler'ı ──────────────────────────────────

    def _notification_handler(self, notification) -> bool:
        """NotificationEngine'den gelen bildirimi HA persistent_notification olarak gönderir."""
        url, token = self._get_ha_config()
        if not url or not token:
            return False

        res = self.call_service(
            domain="persistent_notification",
            service="create",
            service_data={
                "title": f"ULTRON [{notification.priority.name}]: {notification.title}",
                "message": notification.message,
                "notification_id": f"ultron_{notification.notification_id[:8]}",
            },
        )
        return res.get("status") == "ok"


# Global Singleton
ha_bridge = HomeAssistantBridge()
