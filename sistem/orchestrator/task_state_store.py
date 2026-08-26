"""
ULTRON Orchestrator — Task State Persistence & Resume Store
───────────────────────────────────────────────────────────
• Görev durumunun, bağımlılık grafının ve ara çıktıların diskte kalıcı saklanması
• Sistem yeniden başladığında veya duraksama sonrası göreve devam edebilme (Resume / Abort)
"""

from __future__ import annotations

import json
import logging
import time
from pathlib import Path
from typing import Any

from app_paths import data_path

logger = logging.getLogger("ultron.orchestrator.task_state_store")

TASKS_STORE_DIR = data_path("task_checkpoints")


class TaskStateStore:
    """Görev durumunu kalıcı depolayan ve devam ettiren yönetici."""

    def __init__(self):
        TASKS_STORE_DIR.mkdir(parents=True, exist_ok=True)

    def save_checkpoint(self, task_id: str, data: dict[str, Any]) -> str:
        """Görev durumunu diske yazar."""
        file_path = TASKS_STORE_DIR / f"{task_id}.json"
        payload = {
            "task_id": task_id,
            "updated_at": time.time(),
            **data
        }
        file_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return str(file_path)

    def load_checkpoint(self, task_id: str) -> dict[str, Any] | None:
        """Görev durumunu diskten okur."""
        file_path = TASKS_STORE_DIR / f"{task_id}.json"
        if not file_path.exists():
            return None
        try:
            return json.loads(file_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Checkpoint okuma hatasi ({task_id}): {e}")
            return None

    def list_checkpoints(self) -> list[dict[str, Any]]:
        """Kayıtlı tüm görev anlık durumlarını listeler."""
        res = []
        for p in TASKS_STORE_DIR.glob("*.json"):
            try:
                data = json.loads(p.read_text(encoding="utf-8"))
                res.append({
                    "task_id": data.get("task_id", p.stem),
                    "status": data.get("status", "UNKNOWN"),
                    "updated_at": data.get("updated_at", 0),
                    "description": data.get("description", "")
                })
            except Exception:
                continue
        return sorted(res, key=lambda x: x["updated_at"], reverse=True)

    def delete_checkpoint(self, task_id: str) -> bool:
        """Tamamlanan veya iptal edilen görevin kaydını temizler."""
        file_path = TASKS_STORE_DIR / f"{task_id}.json"
        if file_path.exists():
            try:
                file_path.unlink()
                return True
            except Exception:
                pass
        return False


# Global TaskStateStore Singleton
task_state_store = TaskStateStore()
