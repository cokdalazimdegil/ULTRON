"""
ULTRON Event Schema — Standart Olay Zarfı (Event Envelope)
═══════════════════════════════════════════════════════════
Tüm ULTRON bileşenleri arasında dolaşan olayların standart
veri yapısını tanımlar.

Kullanım:
    from core.events import UltronEvent, EventPriority

    event = UltronEvent(
        event_type="user.arrived_home",
        source="location_tracker",
        payload={"lat": 41.01, "lon": 28.97},
        priority=EventPriority.HIGH,
    )
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field, asdict
from enum import IntEnum
from typing import Any, Dict, Optional


# ── Öncelik Seviyeleri ──────────────────────────────────────────────────────

class EventPriority(IntEnum):
    """Olay öncelik seviyeleri. Düşük sayı = düşük öncelik."""
    LOW = 10
    NORMAL = 50
    HIGH = 80
    CRITICAL = 100


# ── Bilinen Event Kaynakları ────────────────────────────────────────────────

class EventSource:
    """Standart kaynak sabitleri. Yeni modüller kendi string'lerini de kullanabilir."""
    SYSTEM       = "system"
    USER         = "user"
    OBSERVER     = "observer"
    LOCATION     = "location"
    HOME_ASSIST  = "home_assistant"
    EMAIL        = "email"
    WORKSPACE    = "workspace"
    HEARTBEAT    = "heartbeat"
    PROACTIVE    = "proactive"
    WEBHOOK      = "webhook"
    CAMERA       = "camera"
    DAEMON       = "daemon"
    CLI          = "cli"
    AGENT        = "agent"


# ── Standart Olay Zarfı ────────────────────────────────────────────────────

@dataclass
class UltronEvent:
    """
    ULTRON Event Envelope — Tüm olaylar için standart zarf.

    Alanlar:
        event_type : Nokta-ayrılmış olay türü (örn: "user.arrived_home", "camera.face_detected")
        source     : Olayı fırlatan modül/bileşen adı
        payload    : Olaya özgü veri (serbest dict)
        priority   : EventPriority enum değeri
        event_id   : Otomatik üretilen benzersiz kimlik (UUID4)
        timestamp  : Olayın oluşturulma zamanı (Unix epoch float)
        metadata   : Ek kontrol bilgileri (cooldown_key, ttl, vb.)
    """
    event_type: str
    source: str = EventSource.SYSTEM
    payload: Dict[str, Any] = field(default_factory=dict)
    priority: EventPriority = EventPriority.NORMAL
    event_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serileştirilebilir sözlük döner."""
        d = asdict(self)
        d["priority"] = int(self.priority)
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "UltronEvent":
        """Sözlükten UltronEvent oluşturur."""
        data = dict(data)  # shallow copy
        if "priority" in data:
            data["priority"] = EventPriority(int(data["priority"]))
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    @property
    def domain(self) -> str:
        """Olay türünün ilk segmentini döner (örn: 'user.arrived_home' → 'user')."""
        return self.event_type.split(".")[0] if "." in self.event_type else self.event_type

    def __repr__(self) -> str:
        return (
            f"UltronEvent(type={self.event_type!r}, src={self.source!r}, "
            f"prio={self.priority.name}, id={self.event_id})"
        )
