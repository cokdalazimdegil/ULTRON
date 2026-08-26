"""
ULTRON Orchestrator — File Lock & Conflict Management
─────────────────────────────────────────────────────
• Çoklu ajan (Multi-Agent) dosya kilit sistemi
• Aynı anda birden fazla ajanın aynı dosyayı değiştirmesini engelleme (Concurrency Control)
• Görev tamamlama veya acil durdurma anında tüm kilitleri güvenle serbest bırakma
"""

from __future__ import annotations

import logging
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("ultron.orchestrator.agent_lock")


class FileLockManager:
    """Ajanlar arası dosya çakışmasını engelleyen merkezi kilit yöneticisi."""

    def __init__(self):
        self._locks: dict[str, dict[str, Any]] = {}  # normalized_path -> {"agent": str, "task_id": str, "acquired_at": float}
        self._lock = threading.RLock()

    def _normalize(self, path: str) -> str:
        try:
            return str(Path(path).resolve()).lower()
        except Exception:
            return path.strip().lower()

    def acquire_lock(self, file_path: str, agent_id: str, task_id: str, timeout_sec: float = 2.0) -> bool:
        """Dosya kilidini almaya çalışır. Başarılıysa True döner."""
        norm_path = self._normalize(file_path)
        start_time = time.time()

        while time.time() - start_time < timeout_sec:
            with self._lock:
                current_owner = self._locks.get(norm_path)
                if not current_owner or current_owner["agent"] == agent_id:
                    self._locks[norm_path] = {
                        "agent": agent_id,
                        "task_id": task_id,
                        "acquired_at": time.time()
                    }
                    logger.debug(f"Kilit alındı: {norm_path} -> {agent_id} ({task_id})")
                    return True
            time.sleep(0.05)

        logger.warning(f"Dosya kilitli: {norm_path} halen {self._locks.get(norm_path, {}).get('agent')} tarafından kullanılıyor.")
        return False

    def release_lock(self, file_path: str, agent_id: str | None = None) -> bool:
        """Belirtilen dosyanın kilidini serbest bırakır."""
        norm_path = self._normalize(file_path)
        with self._lock:
            current_owner = self._locks.get(norm_path)
            if current_owner:
                if agent_id is None or current_owner["agent"] == agent_id:
                    del self._locks[norm_path]
                    logger.debug(f"Kilit serbest bırakıldı: {norm_path}")
                    return True
        return False

    def release_all_locks_for_task(self, task_id: str) -> int:
        """Bir göreve ait tüm kilitleri kaldırır."""
        with self._lock:
            to_remove = [p for p, info in self._locks.items() if info.get("task_id") == task_id]
            for p in to_remove:
                del self._locks[p]
            return len(to_remove)

    def release_all(self) -> int:
        """Tüm kilitleri acil durum veya temizlikte serbest bırakır."""
        with self._lock:
            count = len(self._locks)
            self._locks.clear()
            return count

    def get_locked_files(self) -> list[dict[str, Any]]:
        with self._lock:
            return [{"file": p, **info} for p, info in self._locks.items()]


# Global FileLockManager Singleton
file_lock_manager = FileLockManager()
