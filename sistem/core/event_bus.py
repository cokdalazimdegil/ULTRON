"""
ULTRON Event Bus (Olay Yöneticisi)
───────────────────────────────────
Arka plan ajanları (CyberDog, Companion vb.) ile Ana Thread (Web UI)
arasındaki iletişimi sağlayan Pub/Sub (Yayıncı/Abone) mekanizması.
"""

import threading
import logging
from typing import Callable, Dict, List, Any

logger = logging.getLogger("ultron.core.event_bus")

class EventBus:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(EventBus, cls).__new__(cls)
                cls._instance.subscribers = {}
        return cls._instance

    def subscribe(self, event_type: str, callback: Callable[[Any], None]):
        """Belirli bir olay türüne abone olur."""
        with self._lock:
            if event_type not in self.subscribers:
                self.subscribers[event_type] = []
            if callback not in self.subscribers[event_type]:
                self.subscribers[event_type].append(callback)

    def publish(self, event_type: str, data: Any):
        """Tüm abonelere olayı fırlatır."""
        with self._lock:
            subs = self.subscribers.get(event_type, []).copy()
            
        for callback in subs:
            try:
                callback(data)
            except Exception as e:
                logger.error(f"[EventBus] '{event_type}' abonesinde hata: {e}")

# Global Singleton
bus = EventBus()
