"""
ULTRON Orchestrator — Agent Task Queue & Dependency Graph
─────────────────────────────────────────────────────────
• Görev kuyruğu (Task Queue) ve bağımlılık grafı (DAG / Task Dependencies)
• Paralel ve sıralı görev planlama & Artifact referans sistemi
• Ağaç tabanlı görev durumu (Task Tree) ve WebSocket gözlemlenebilirlik olayları
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("ultron.orchestrator.task_queue")


@dataclass
class AgentTask:
    task_id: str
    description: str
    assigned_agent: str
    parent_task_id: str | None = None
    depends_on: list[str] = field(default_factory=list)
    priority: str = "NORMAL"  # LOW, NORMAL, HIGH, CRITICAL
    status: str = "PENDING"   # PENDING, RUNNING, WAITING, VERIFYING, REVIEWING, COMPLETED, VERIFIED_COMPLETED, FAILED, CANCELLED
    input_artifacts: dict[str, Any] = field(default_factory=dict)
    output_artifacts: dict[str, Any] = field(default_factory=dict)
    error_message: str = ""
    retry_count: int = 0
    max_retries: int = 2
    created_at: float = field(default_factory=time.time)
    started_at: float = 0.0
    finished_at: float = 0.0


class AgentTaskQueue:
    """Multi-Agent Görev Kuyruğu ve Bağımlılık Yöneticisi."""

    def __init__(self):
        self._tasks: dict[str, AgentTask] = {}
        self._subscribers: list[Callable[[dict[str, Any]], None]] = []
        self._lock = threading.RLock()
        self._task_counter = 0

    def create_task(
        self,
        description: str,
        assigned_agent: str,
        parent_task_id: str | None = None,
        depends_on: list[str] | None = None,
        priority: str = "NORMAL",
        input_artifacts: dict[str, Any] | None = None
    ) -> AgentTask:
        with self._lock:
            self._task_counter += 1
            task_id = f"AGENT-TASK-{self._task_counter:03d}"
            task = AgentTask(
                task_id=task_id,
                description=description,
                assigned_agent=assigned_agent,
                parent_task_id=parent_task_id,
                depends_on=depends_on or [],
                priority=priority,
                input_artifacts=input_artifacts or {}
            )
            self._tasks[task_id] = task
            self._emit_event("TASK_CREATED", task)
            return task

    def get_task(self, task_id: str) -> AgentTask | None:
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "task_id": t.task_id,
                    "description": t.description,
                    "assigned_agent": t.assigned_agent,
                    "parent_id": t.parent_task_id,
                    "depends_on": t.depends_on,
                    "status": t.status,
                    "retry_count": t.retry_count,
                    "created_at": t.created_at
                }
                for t in self._tasks.values()
            ]

    def update_task_status(
        self,
        task_id: str,
        status: str,
        output_artifacts: dict[str, Any] | None = None,
        error_message: str = ""
    ) -> None:
        with self._lock:
            task = self._tasks.get(task_id)
            if not task:
                return

            task.status = status
            if status == "RUNNING" and task.started_at == 0.0:
                task.started_at = time.time()
            if status in ("COMPLETED", "VERIFIED_COMPLETED", "FAILED", "CANCELLED"):
                task.finished_at = time.time()

            if output_artifacts:
                task.output_artifacts.update(output_artifacts)
            if error_message:
                task.error_message = error_message

            self._emit_event(f"TASK_STATUS_{status}", task)

    def is_ready_to_run(self, task_id: str) -> bool:
        """Görevin tüm öncül bağımlılıklarının tamamlanıp tamamlanmadığını kontrol eder."""
        with self._lock:
            task = self._tasks.get(task_id)
            if not task or task.status != "PENDING":
                return False

            for dep_id in task.depends_on:
                dep_task = self._tasks.get(dep_id)
                if not dep_task or dep_task.status not in ("COMPLETED", "VERIFIED_COMPLETED"):
                    return False
            return True

    def get_ready_tasks(self) -> list[AgentTask]:
        """Çalıştırılmaya hazır tüm bağımsız görevleri döner (Paralel yürütme için)."""
        with self._lock:
            return [t for t in self._tasks.values() if self.is_ready_to_run(t.task_id)]

    def subscribe(self, callback: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            self._subscribers.append(callback)

    def _emit_event(self, event_type: str, task: AgentTask) -> None:
        event = {
            "type": event_type,
            "task_id": task.task_id,
            "agent": task.assigned_agent,
            "status": task.status,
            "timestamp": time.time()
        }
        for sub in self._subscribers:
            try:
                sub(event)
            except Exception:
                pass


# Global Task Queue Singleton
agent_task_queue = AgentTaskQueue()
