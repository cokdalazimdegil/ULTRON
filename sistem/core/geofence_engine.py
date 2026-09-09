"""
ULTRON Geofence Engine — Coğrafi Sınır ve Konum Durum Motoru
═════════════════════════════════════════════════════════════
Kullanıcıların GPS koordinatlarını tanımlı bölgelerle (ev, iş vb.) karşılaştırır,
bölgeye giriş/çıkış geçişlerini tespit eder ve Event Bus'a yayınlar.

Event'ler:
    - geofence.enter       (user, zone, distance_m)
    - geofence.exit        (user, zone, distance_m)
    - user.arrived_home    (user, timestamp, address)
    - user.left_home       (user, timestamp)

Kullanım:
    from core.geofence_engine import geofence_engine
    geofence_engine.start()
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass, field
import json
from pathlib import Path

from app_paths import data_path
from core.events import UltronEvent, EventPriority, EventSource

logger = logging.getLogger("ultron.core.geofence")

ZONES_FILE = data_path("config", "geofence_zones.json")


# ── Bölge Tanımı ─────────────────────────────────────────────────────────────

@dataclass
class GeofenceZone:
    """Coğrafi sınır bölgesi."""
    name: str
    lat: float
    lng: float
    radius_meters: float = 150.0
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "lat": self.lat,
            "lng": self.lng,
            "radius_meters": self.radius_meters,
            "description": self.description,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> GeofenceZone:
        return cls(
            name=d.get("name", ""),
            lat=float(d.get("lat", 0.0)),
            lng=float(d.get("lng", 0.0)),
            radius_meters=float(d.get("radius_meters", 150.0)),
            description=d.get("description", ""),
            metadata=d.get("metadata", {}),
        )


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki GPS koordinatı arasındaki mesafeyi metre cinsinden hesaplar."""
    r = 6371000.0  # Dünya yarıçapı (metre)
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return r * c


# ── Geofence Engine ─────────────────────────────────────────────────────────

class GeofenceEngine:
    """
    Kullanıcı coğrafi sınır motoru.
    Gelen konum verilerini değerlendirir, bölgeye giriş ve çıkış event'leri fırlatır.
    """

    _instance: Optional["GeofenceEngine"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "GeofenceEngine":
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

        self._zones: Dict[str, GeofenceZone] = {}
        # user -> set of current zone names
        self._user_zones: Dict[str, set] = {}
        # user -> last location update timestamp
        self._last_update: Dict[str, float] = {}
        # Event Bus
        self._bus = None
        self._started = False
        self._save_to_disk = True
        self._state_lock = threading.Lock()

        # Varsayılan ev bölgesi (varsa config'ten veya koordinatsız)
        self._load_default_zones()

    def _get_bus(self):
        if self._bus is None:
            try:
                from core.event_bus import bus
                self._bus = bus
            except ImportError:
                pass
        return self._bus

    def _save_zones(self) -> None:
        if not getattr(self, "_save_to_disk", True):
            return
        try:
            ZONES_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {k: z.to_dict() for k, z in self._zones.items()}
            ZONES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception as e:
            logger.error(f"[GeofenceEngine] Bölge kaydetme hatası: {e}")

    def _load_default_zones(self) -> None:
        """Kayıtlı bölgeleri ve config dosyasından ev koordinatlarını yükler."""
        # 1. ZONES_FILE'dan oku
        if ZONES_FILE.exists():
            try:
                raw = json.loads(ZONES_FILE.read_text(encoding="utf-8"))
                for k, d in raw.items():
                    self._zones[k] = GeofenceZone.from_dict(d)
            except Exception as e:
                logger.warning(f"[GeofenceEngine] Kayıtlı bölgeler okunamadı: {e}")

        # 2. Config'ten home bölgesini kontrol et/tamamla
        try:
            from app_config import get_app_config_value
            home_lat = get_app_config_value("home_latitude")
            home_lng = get_app_config_value("home_longitude")
            home_radius = float(get_app_config_value("home_radius_meters", 150.0) or 150.0)
            home_desc = str(get_app_config_value("home_address", "Ev") or "Ev")
            if home_lat is not None and home_lng is not None and "home" not in self._zones:
                self.add_zone("home", float(home_lat), float(home_lng), home_radius, home_desc)
        except Exception:
            pass

    # ── Yaşam Döngüsü ──────────────────────────────────────────────────────

    def start(self) -> None:
        """Geofence engine'i başlatır ve Event Bus'a abone olur."""
        if self._started:
            return
        bus = self._get_bus()
        if bus:
            bus.subscribe("user.location.changed", self._on_location_event)
            logger.info("[GeofenceEngine] 'user.location.changed' event'ine abone olundu.")
        self._started = True
        logger.info("[GeofenceEngine] Başlatıldı.")

    def stop(self) -> None:
        """Geofence engine'i durdurur."""
        self._started = False
        logger.info("[GeofenceEngine] Durduruldu.")

    # ── Bölge Yönetimi ──────────────────────────────────────────────────────

    def add_zone(
        self,
        name: str,
        lat: float,
        lng: float,
        radius_meters: float = 150.0,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> GeofenceZone:
        """Yeni bir coğrafi bölge ekler veya günceller."""
        zone = GeofenceZone(
            name=name.lower().strip(),
            lat=float(lat),
            lng=float(lng),
            radius_meters=float(radius_meters),
            description=description,
            metadata=metadata or {},
        )
        with self._state_lock:
            self._zones[zone.name] = zone
            self._save_zones()
        logger.info(f"[GeofenceEngine] Bölge tanımlandı: '{zone.name}' (yarıçap: {zone.radius_meters}m)")
        return zone

    def remove_zone(self, name: str) -> bool:
        """Bölgeyi siler."""
        name = name.lower().strip()
        with self._state_lock:
            if name in self._zones:
                del self._zones[name]
                # Kullanıcı aktif bölgelerinden de temizle
                for u in self._user_zones:
                    self._user_zones[u].discard(name)
                self._save_zones()
                return True
        return False

    def get_zones(self) -> List[Dict[str, Any]]:
        """Tüm tanımlı bölgeleri döner."""
        with self._state_lock:
            return [
                {
                    "name": z.name,
                    "lat": z.lat,
                    "lng": z.lng,
                    "radius_meters": z.radius_meters,
                    "description": z.description,
                }
                for z in self._zones.values()
            ]

    def get_user_zones(self, user: str) -> List[str]:
        """Kullanıcının şu an içinde bulunduğu bölgeleri döner."""
        with self._state_lock:
            return list(self._user_zones.get(user, set()))

    # ── Konum İşleme & Geofence Tespiti ─────────────────────────────────────

    def _on_location_event(self, data: Any) -> None:
        """Event Bus'tan gelen user.location.changed event'ini işler."""
        if not isinstance(data, dict):
            return
        user = str(data.get("user", "YARATICI"))
        lat = data.get("lat")
        lng = data.get("lng")
        accuracy = data.get("accuracy")

        if lat is not None and lng is not None:
            self.process_location(user, float(lat), float(lng), float(accuracy) if accuracy else None)

    def process_location(
        self,
        user: str,
        lat: float,
        lng: float,
        accuracy: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Kullanıcının koordinatlarını bölgelerle karşılaştırır,
        giriş/çıkış geçişlerini tespit eder ve ilgili event'leri yayınlar.
        """
        now = time.time()
        user = user.strip()
        bus = self._get_bus()

        entered_zones = []
        exited_zones = []
        current_active = set()

        with self._state_lock:
            previous_active = set(self._user_zones.get(user, set()))

            for zone_name, zone in self._zones.items():
                distance = haversine_distance_meters(lat, lng, zone.lat, zone.lng)
                if distance <= zone.radius_meters:
                    current_active.add(zone_name)
                    if zone_name not in previous_active:
                        entered_zones.append((zone_name, distance))
                else:
                    if zone_name in previous_active:
                        exited_zones.append((zone_name, distance))

            self._user_zones[user] = current_active
            self._last_update[user] = now

        # Geçiş event'lerini yayınla (lock dışı)
        for zone_name, dist in entered_zones:
            logger.info(f"[GeofenceEngine] 📍 {user} '{zone_name}' bölgesine GİRDİ ({dist:.1f}m)")
            if bus:
                bus.publish_event(UltronEvent(
                    event_type="geofence.enter",
                    source=EventSource.LOCATION,
                    payload={
                        "user": user,
                        "zone": zone_name,
                        "distance": dist,
                        "lat": lat,
                        "lng": lng,
                        "accuracy": accuracy,
                        "timestamp": now,
                    },
                    priority=EventPriority.NORMAL,
                ))

                # Özel ev bölgesi girişi
                if zone_name == "home":
                    bus.publish_event(UltronEvent(
                        event_type="user.arrived_home",
                        source=EventSource.LOCATION,
                        payload={
                            "user": user,
                            "timestamp": now,
                            "lat": lat,
                            "lng": lng,
                        },
                        priority=EventPriority.HIGH,
                    ))

        for zone_name, dist in exited_zones:
            logger.info(f"[GeofenceEngine] 🚶 {user} '{zone_name}' bölgesinden ÇIKTI ({dist:.1f}m)")
            if bus:
                bus.publish_event(UltronEvent(
                    event_type="geofence.exit",
                    source=EventSource.LOCATION,
                    payload={
                        "user": user,
                        "zone": zone_name,
                        "distance": dist,
                        "lat": lat,
                        "lng": lng,
                        "timestamp": now,
                    },
                    priority=EventPriority.NORMAL,
                ))

                # Özel ev bölgesi çıkışı
                if zone_name == "home":
                    bus.publish_event(UltronEvent(
                        event_type="user.left_home",
                        source=EventSource.LOCATION,
                        payload={
                            "user": user,
                            "timestamp": now,
                        },
                        priority=EventPriority.NORMAL,
                    ))

        return {
            "user": user,
            "current_zones": list(current_active),
            "entered": [z for z, _ in entered_zones],
            "exited": [z for z, _ in exited_zones],
            "lat": lat,
            "lng": lng,
        }

    def reset(self) -> None:
        """Test için durum sıfırlama."""
        with self._state_lock:
            self._zones.clear()
            self._user_zones.clear()
            self._last_update.clear()


# Global Singleton
geofence_engine = GeofenceEngine()
