"""
ULTRON Computer State — Compatibility Facade (V17 Consolidated)
───────────────────────────────────────────────────────────────
Bu modül geriye dönük uyumluluk (backward compatibility) için sağlanmaktadır.
Canonical veri kaynağı doğrudan `computer/world_model.py` altındaki `world_model`
nesnesidir ve tüm durum güncellemeleri dünya modeline yönlendirilir.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any

from computer.world_model import (
    world_model,
    WindowEntity,
    ApplicationEntity,
    SystemMetricsEntity,
    ActiveTaskContext,
)


@dataclass
class UIElement:
    """Ekrandaki tespit edilmiş buton/girdi/bağlantı öğesi."""
    text: str
    x: int
    y: int
    width: int = 0
    height: int = 0
    element_type: str = "button"
    confidence: float = 1.0


@dataclass
class ComputerState:
    """Anlık bilgisayar durumunu temsil eden veri sınıfı (Canonical World Model ile senkronize)."""
    active_window: str = ""
    active_process: str = ""
    active_pid: int = 0
    screen_resolution: tuple[int, int] = (1920, 1080)
    monitors: list[dict[str, Any]] = field(default_factory=list)
    visible_text: str = ""
    visible_buttons: list[dict[str, Any]] = field(default_factory=list)
    visible_errors: list[str] = field(default_factory=list)
    browser_url: str = ""
    browser_title: str = ""
    focused_element: str = ""
    last_screen_change_time: float = 0.0
    last_action: str = ""
    last_action_time: float = 0.0
    current_task_id: str | None = None
    current_task_status: str = "IDLE"  # IDLE, RUNNING, COMPLETED, FAILED, WAITING_FOR_USER, CANCELLED
    current_task_progress: str = ""
    research_mode_active: bool = False
    last_analysis_summary: str = ""
    updated_at: float = field(default_factory=time.time)


class ComputerStateManager:
    """Thread-safe ComputerState yöneticisi (World Model Facade)."""

    def __init__(self):
        self._state = ComputerState()
        self._lock = threading.RLock()

    def get_state(self) -> ComputerState:
        with self._lock:
            # Canonical world_model'den anlık değerleri senkronize et
            win = world_model.active_window
            self._state.active_window = win.title
            self._state.active_process = win.process_name
            self._state.active_pid = win.pid
            self._state.screen_resolution = world_model.metrics.screen_resolution
            self._state.current_task_id = world_model.active_task.task_id
            self._state.current_task_status = world_model.active_task.status
            self._state.last_action = world_model.active_task.last_action
            self._state.last_action_time = world_model.active_task.last_action_time
            self._state.updated_at = time.time()
            return self._state

    def update(self, **kwargs: Any) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self._state, k):
                    setattr(self._state, k, v)
            self._state.updated_at = time.time()

            # Canonical world_model'e yansıt
            if "screen_resolution" in kwargs:
                world_model.metrics.screen_resolution = kwargs["screen_resolution"]
            if "last_action" in kwargs:
                world_model.record_action(kwargs["last_action"])

    def set_active_window(self, title: str, process: str = "", pid: int = 0) -> None:
        with self._lock:
            self._state.active_window = title
            self._state.active_process = process
            self._state.active_pid = pid
            self._state.updated_at = time.time()

            # World Model senkronizasyonu
            world_model.set_active_window(WindowEntity(
                title=title,
                process_name=process,
                pid=pid,
                is_foreground=True
            ))

    def set_task(self, task_id: str | None, status: str = "RUNNING", progress: str = "") -> None:
        with self._lock:
            self._state.current_task_id = task_id
            self._state.current_task_status = status
            self._state.current_task_progress = progress
            self._state.updated_at = time.time()

            # World Model senkronizasyonu
            world_model.set_active_task(ActiveTaskContext(
                task_id=task_id,
                status=status,
                goal=progress
            ))

    def set_research_mode(self, active: bool) -> None:
        with self._lock:
            self._state.research_mode_active = active
            self._state.updated_at = time.time()

    def record_action(self, action_name: str) -> None:
        with self._lock:
            self._state.last_action = action_name
            self._state.last_action_time = time.time()
            self._state.updated_at = time.time()
            world_model.record_action(action_name)

    def get_summary(self) -> str:
        return world_model.get_world_summary()


# Global Singleton Instance (Backward-Compatible)
current_computer_state = ComputerStateManager()
