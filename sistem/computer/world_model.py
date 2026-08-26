"""
ULTRON World Model — Live Dynamic Computer Environment Representation (v3.0)
══════════════════════════════════════════════════════════════════════════════
• Canlı varlık (Entity) ve ilişki (Relationship) grafı
• Zamansal durum değişimleri (Temporal State Transitions & Diffing)
• Belirsizlik derecelendirmesi (CONFIRMED, PROBABLE, UNKNOWN, STALE)
• Aksiyon öncesi/sonrası durum karşılaştırması ile işlem doğrulama
"""

from __future__ import annotations

import copy
import json
import logging
import threading
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any, Callable

logger = logging.getLogger("ultron.computer.world_model")


class UncertaintyLevel(str, Enum):
    CONFIRMED = "CONFIRMED"  # Doğrudan sistem API'si veya görsel teyitle doğrulanmış
    PROBABLE  = "PROBABLE"   # Yüksek olasılıkla geçerli (çıkarım sonucu)
    UNKNOWN   = "UNKNOWN"    # Henüz gözlemlenmemiş veya belirsiz
    STALE     = "STALE"      # Zaman aşımına uğramış, yeniden doğrulanması gereken


@dataclass
class UserEntity:
    name: str = "Nuri Can"
    role: str = "Yaratıcı & Sistem Yöneticisi"
    is_authenticated: bool = True
    active_location: dict[str, Any] = field(default_factory=dict)
    last_interaction_time: float = field(default_factory=time.time)


@dataclass
class WindowEntity:
    hwnd: int = 0
    title: str = ""
    process_name: str = ""
    pid: int = 0
    bounds: tuple[int, int, int, int] = (0, 0, 1920, 1080)
    is_foreground: bool = False
    is_minimized: bool = False
    uncertainty: UncertaintyLevel = UncertaintyLevel.CONFIRMED
    updated_at: float = field(default_factory=time.time)


@dataclass
class ApplicationEntity:
    name: str = ""
    executable_path: str = ""
    pids: list[int] = field(default_factory=list)
    is_running: bool = False
    windows: list[int] = field(default_factory=list)  # list of hwnds
    uncertainty: UncertaintyLevel = UncertaintyLevel.CONFIRMED
    updated_at: float = field(default_factory=time.time)


@dataclass
class SystemMetricsEntity:
    cpu_percent: float = 0.0
    ram_percent: float = 0.0
    ram_available_mb: float = 0.0
    disk_free_gb: float = 0.0
    network_connected: bool = True
    battery_percent: float | None = None
    battery_charging: bool = False
    active_monitors_count: int = 1
    screen_resolution: tuple[int, int] = (1920, 1080)
    updated_at: float = field(default_factory=time.time)


@dataclass
class ActiveTaskContext:
    task_id: str | None = None
    goal: str = ""
    owner: str = "Nuri Can"
    status: str = "IDLE"  # IDLE, PLANNING, RUNNING, VERIFYING, COMPLETED, FAILED
    active_subtask_id: str | None = None
    assigned_agent: str | None = None
    target_application: str | None = None
    target_window_title: str | None = None
    start_time: float = field(default_factory=time.time)
    last_action: str = ""
    last_action_time: float = 0.0
    execution_history: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class WorldStateSnapshot:
    """Belirli bir andaki tam dünya durumunun anlık görüntüsü."""
    timestamp: float
    user: UserEntity
    active_window: WindowEntity
    applications: dict[str, ApplicationEntity]
    metrics: SystemMetricsEntity
    task_context: ActiveTaskContext
    visible_ui_elements_count: int = 0
    screen_hash: int = 0
    notes: str = ""


class UltronWorldModel:
    """
    ULTRON Dünya Modeli (World Model Engine).
    Bilgisayarın anlık durumunu, çalışan uygulamaları, aktif pencereleri ve
    devam eden görevlerin bağlamını canlı ve tutarlı bir şekilde yönetir.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self.user = UserEntity()
        self.active_window = WindowEntity()
        self.applications: dict[str, ApplicationEntity] = {}
        self.metrics = SystemMetricsEntity()
        self.task_context = ActiveTaskContext()
        self.visible_ui_elements: list[dict[str, Any]] = []
        self.last_screen_hash: int = 0
        self.state_history: list[WorldStateSnapshot] = []
        self._listeners: list[Callable[[WorldStateSnapshot, WorldStateSnapshot], None]] = []

    def update_user(self, name: str, role: str = "", authenticated: bool = True) -> None:
        with self._lock:
            self.user.name = name
            if role:
                self.user.role = role
            self.user.is_authenticated = authenticated
            self.user.last_interaction_time = time.time()

    @property
    def active_task(self) -> ActiveTaskContext:
        return self.task_context

    @active_task.setter
    def active_task(self, val: ActiveTaskContext) -> None:
        self.task_context = val

    def set_active_task(self, task: ActiveTaskContext) -> None:
        with self._lock:
            self.task_context = task


    def set_active_window(self, window_or_title: WindowEntity | str) -> None:
        if isinstance(window_or_title, WindowEntity):
            with self._lock:
                self.active_window = window_or_title
        else:
            self.update_active_window(title=str(window_or_title))

    def update_active_window(self, hwnd: int = 0, title: str = "", process_name: str = "",
                             pid: int = 0, bounds: tuple[int, int, int, int] = (0, 0, 1920, 1080)) -> None:
        with self._lock:
            self.active_window = WindowEntity(
                hwnd=hwnd,
                title=title,
                process_name=process_name,
                pid=pid,
                bounds=bounds,
                is_foreground=True,
                uncertainty=UncertaintyLevel.CONFIRMED,
                updated_at=time.time()
            )

            if process_name:
                app_key = process_name.lower().replace(".exe", "")
                if app_key not in self.applications:
                    self.applications[app_key] = ApplicationEntity(
                        name=process_name,
                        pids=[pid] if pid else [],
                        is_running=True,
                        windows=[hwnd] if hwnd else [],
                        uncertainty=UncertaintyLevel.CONFIRMED,
                        updated_at=time.time()
                    )
                else:
                    self.applications[app_key].is_running = True
                    self.applications[app_key].updated_at = time.time()

    def update_application_status(self, app_name: str, is_running: bool, pid: int = 0) -> None:
        with self._lock:
            app_key = app_name.lower().replace(".exe", "")
            if app_key not in self.applications:
                self.applications[app_key] = ApplicationEntity(
                    name=app_name,
                    pids=[pid] if pid else [],
                    is_running=is_running,
                    uncertainty=UncertaintyLevel.CONFIRMED,
                    updated_at=time.time()
                )
            else:
                app = self.applications[app_key]
                app.is_running = is_running
                if pid and pid not in app.pids:
                    app.pids.append(pid)
                app.updated_at = time.time()

    def update_metrics(self, **kwargs: Any) -> None:
        with self._lock:
            for k, v in kwargs.items():
                if hasattr(self.metrics, k):
                    setattr(self.metrics, k, v)
            self.metrics.updated_at = time.time()

    def set_task_context(self, task_id: str | None, goal: str = "", status: str = "RUNNING",
                         agent: str | None = None, target_app: str | None = None) -> None:
        with self._lock:
            self.task_context.task_id = task_id
            if goal:
                self.task_context.goal = goal
            self.task_context.status = status
            if agent:
                self.task_context.assigned_agent = agent
            if target_app:
                self.task_context.target_application = target_app
            self.task_context.start_time = time.time()

    def record_action(self, action_name: str, params: dict[str, Any] | None = None) -> None:
        with self._lock:
            now = time.time()
            self.task_context.last_action = action_name
            self.task_context.last_action_time = now
            self.task_context.execution_history.append({
                "action": action_name,
                "params": params or {},
                "timestamp": now,
                "active_window": self.active_window.title,
                "active_process": self.active_window.process_name
            })
            if len(self.task_context.execution_history) > 100:
                self.task_context.execution_history.pop(0)

    def capture_snapshot(self, notes: str = "") -> WorldStateSnapshot:
        """Dünyanın anlık derin kopyasını oluşturur ve geçmişe kaydeder."""
        with self._lock:
            snap = WorldStateSnapshot(
                timestamp=time.time(),
                user=copy.deepcopy(self.user),
                active_window=copy.deepcopy(self.active_window),
                applications=copy.deepcopy(self.applications),
                metrics=copy.deepcopy(self.metrics),
                task_context=copy.deepcopy(self.task_context),
                visible_ui_elements_count=len(self.visible_ui_elements),
                screen_hash=self.last_screen_hash,
                notes=notes
            )
            self.state_history.append(snap)
            if len(self.state_history) > 50:
                self.state_history.pop(0)
            return snap

    take_snapshot = capture_snapshot

    def diff_snapshots(self, snap_before: WorldStateSnapshot, snap_after: WorldStateSnapshot) -> dict[str, Any]:
        """İki dünya durumu arasındaki farkları (Diff) hesaplar."""
        diff = {
            "time_elapsed_sec": round(snap_after.timestamp - snap_before.timestamp, 3),
            "window_changed": snap_before.active_window.title != snap_after.active_window.title,
            "window_before": snap_before.active_window.title,
            "window_after": snap_after.active_window.title,
            "process_changed": snap_before.active_window.process_name != snap_after.active_window.process_name,
            "process_before": snap_before.active_window.process_name,
            "process_after": snap_after.active_window.process_name,
            "screen_changed": snap_before.screen_hash != snap_after.screen_hash,
            "task_status_changed": snap_before.task_context.status != snap_after.task_context.status,
            "cpu_delta": round(snap_after.metrics.cpu_percent - snap_before.metrics.cpu_percent, 2),
            "ram_delta": round(snap_after.metrics.ram_percent - snap_before.metrics.ram_percent, 2),
            "summary": ""
        }

        changes = []
        if diff["window_changed"]:
            changes.append(f"Aktif pencere değişti: '{diff['window_before']}' -> '{diff['window_after']}'")
        if diff["process_changed"]:
            changes.append(f"Aktif süreç değişti: '{diff['process_before']}' -> '{diff['process_after']}'")
        if diff["screen_changed"]:
            changes.append("Ekran görsel içeriği güncellendi")
        diff["summary"] = "; ".join(changes) if changes else "Dünya durumunda önemli bir değişiklik gözlemlenmedi."
        return diff

    def check_stale_states(self, max_age_seconds: float = 45.0) -> list[str]:
        """Zaman aşımına uğramış (STALE) varlıkları tespit eder."""
        with self._lock:
            stale_items = []
            now = time.time()
            if self.active_window.title and (now - self.active_window.updated_at) > max_age_seconds:
                self.active_window.uncertainty = UncertaintyLevel.STALE
                stale_items.append(f"ActiveWindow ({self.active_window.title})")

            for app_key, app in self.applications.items():
                if app.is_running and (now - app.updated_at) > (max_age_seconds * 2):
                    app.uncertainty = UncertaintyLevel.STALE
                    stale_items.append(f"Application ({app.name})")

            return stale_items

    def get_world_summary(self) -> str:
        """LLM ve Supervisor için zengin, yapılandırılmış dünya özeti üretir."""
        with self._lock:
            win = self.active_window
            task = self.task_context
            met = self.metrics

            running_apps = [a.name for a in self.applications.values() if a.is_running]
            apps_str = ", ".join(running_apps[:6]) if running_apps else "Bilinmiyor"

            lines = [
                f"🌍 ULTRON WORLD MODEL (Canlı Bilgisayar Durumu):",
                f"• Kullanıcı: {self.user.name} ({self.user.role}) [Doğrulandı: {self.user.is_authenticated}]",
                f"• Aktif Pencere: '{win.title or 'Masaüstü'}' (İşlem: {win.process_name or 'N/A'}, PID: {win.pid})",
                f"• Ekran Çözünürlüğü: {met.screen_resolution[0]}x{met.screen_resolution[1]} ({met.active_monitors_count} Monitör)",
                f"• Sistem Kaynakları: CPU %{met.cpu_percent:.1f} | RAM %{met.ram_percent:.1f} | Ağ: {'Bağlı' if met.network_connected else 'Kopuk'}",
                f"• Çalışan Uygulamalar: {apps_str}",
            ]
            if task.task_id and task.status != "IDLE":
                lines.append(f"• Aktif Görev: [{task.task_id}] {task.goal} (Durum: {task.status}, Ajan: {task.assigned_agent or 'Supervisor'})")
            if task.last_action:
                lines.append(f"• Son Gerçekleşen Aksiyon: {task.last_action}")

            return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        with self._lock:
            return {
                "user": asdict(self.user),
                "active_window": asdict(self.active_window),
                "applications": {k: asdict(v) for k, v in self.applications.items()},
                "metrics": asdict(self.metrics),
                "task_context": asdict(self.task_context),
                "ui_elements_count": len(self.visible_ui_elements),
                "last_screen_hash": self.last_screen_hash
            }


# Global World Model Singleton
world_model = UltronWorldModel()
