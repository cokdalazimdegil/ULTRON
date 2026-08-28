"""
ULTRON Swarm Reporter — Ajan Ağı Şeffaflık Motoru
──────────────────────────────────────────────────
• Tüm otonom ajan görevlerini (coding, testing, review, research) takip eder.
• /ws/swarm WebSocket endpoint'i üzerinden web UI'ya canlı durum bilgisi iter.
• coding_agent, testing_agent ve orchestrator_engine bu modülü çağırır.
"""

from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional

# ── Görev Durumları ──────────────────────────────────────────────────────────
TASK_PENDING   = "pending"
TASK_RUNNING   = "running"
TASK_SUCCESS   = "success"
TASK_FAILED    = "failed"
TASK_CANCELLED = "cancelled"


@dataclass
class AgentTask:
    task_id: str = field(default_factory=lambda: uuid.uuid4().hex[:8])
    agent_name: str = ""
    description: str = ""
    status: str = TASK_PENDING
    progress: int = 0          # 0-100
    started_at: float = field(default_factory=time.time)
    finished_at: Optional[float] = None
    result_summary: str = ""
    parent_task_id: Optional[str] = None

    def to_dict(self) -> dict:
        d = asdict(self)
        d["elapsed"] = round(time.time() - self.started_at, 1)
        return d


class SwarmReporter:
    """
    Thread-safe singleton: Tüm ajan görevlerini takip eden merkezi kayıt.
    """
    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._tasks: Dict[str, AgentTask] = {}
                cls._instance._task_lock = threading.Lock()
                cls._instance._listeners: List = []   # asyncio Queue'lar
        return cls._instance

    # ── Görev yönetimi ────────────────────────────────────────────────────────

    def register_task(
        self,
        agent_name: str,
        description: str,
        parent_task_id: Optional[str] = None,
    ) -> str:
        task = AgentTask(
            agent_name=agent_name,
            description=description[:120],
            status=TASK_RUNNING,
            started_at=time.time(),
            parent_task_id=parent_task_id,
        )
        with self._task_lock:
            self._tasks[task.task_id] = task
        self._push_update(task)
        return task.task_id

    def update_task(self, task_id: str, progress: int = -1, status: str = ""):
        with self._task_lock:
            task = self._tasks.get(task_id)
        if not task:
            return
        if progress >= 0:
            task.progress = min(100, progress)
        if status:
            task.status = status
        self._push_update(task)

    def complete_task(self, task_id: str, success: bool = True, summary: str = ""):
        with self._task_lock:
            task = self._tasks.get(task_id)
        if not task:
            return
        task.status = TASK_SUCCESS if success else TASK_FAILED
        task.progress = 100 if success else task.progress
        task.finished_at = time.time()
        task.result_summary = summary[:200]
        self._push_update(task)

        # Tamamlanan görevleri 60 saniye sonra temizle
        t_id = task_id
        def _cleanup():
            time.sleep(60)
            with self._task_lock:
                self._tasks.pop(t_id, None)
        threading.Thread(target=_cleanup, daemon=True).start()

    def get_all_tasks(self) -> List[dict]:
        with self._task_lock:
            return [t.to_dict() for t in self._tasks.values()]

    def get_active_count(self) -> int:
        with self._task_lock:
            return sum(1 for t in self._tasks.values() if t.status == TASK_RUNNING)

    # ── WebSocket push ────────────────────────────────────────────────────────

    def add_listener(self, queue):
        """asyncio.Queue ekler — server.py WebSocket handler'dan çağrılır."""
        with self._lock:
            self._listeners.append(queue)

    def remove_listener(self, queue):
        with self._lock:
            try:
                self._listeners.remove(queue)
            except ValueError:
                pass

    def _push_update(self, task: AgentTask):
        """Tüm bağlı WebSocket istemcilerine güncel görev verisini iter."""
        payload = {"type": "swarm_update", "task": task.to_dict(), "all_tasks": self.get_all_tasks()}
        with self._lock:
            for q in list(self._listeners):
                try:
                    q.put_nowait(payload)
                except Exception:
                    pass


# Global singleton
swarm_reporter = SwarmReporter()
