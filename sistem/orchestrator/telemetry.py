"""
ULTRON Orchestrator — Telemetry, Benchmarking & Cost Tracker
────────────────────────────────────────────────────────────
• Görev bazlı kaynak kullanımı (CPU, RAM, Süre, Ajan Sayısı, Retry Sayısı)
• Token ve API çağrısı maliyet izleme
• Otonom ajan ağının performans ve başarı oranı (Benchmark) analizi
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any

import psutil

logger = logging.getLogger("ultron.orchestrator.telemetry")


@dataclass
class TaskTelemetry:
    task_id: str
    start_time: float = field(default_factory=time.time)
    end_time: float = 0.0
    duration_ms: int = 0
    agents_used: list[str] = field(default_factory=list)
    api_calls: int = 0
    tokens_estimated: int = 0
    retry_count: int = 0
    cpu_percent_avg: float = 0.0
    ram_mb_peak: float = 0.0
    status: str = "RUNNING"


class TelemetryTracker:
    """Merkezi Telemetri ve Performans Takipçisi."""

    def __init__(self):
        self._records: dict[str, TaskTelemetry] = {}
        self._process = psutil.Process()

    def start_tracking(self, task_id: str) -> TaskTelemetry:
        t = TaskTelemetry(task_id=task_id)
        self._records[task_id] = t
        return t

    def record_agent_usage(self, task_id: str, agent_id: str) -> None:
        t = self._records.get(task_id)
        if t and agent_id not in t.agents_used:
            t.agents_used.append(agent_id)

    def record_api_call(self, task_id: str, estimated_tokens: int = 0) -> None:
        t = self._records.get(task_id)
        if t:
            t.api_calls += 1
            t.tokens_estimated += estimated_tokens

    def record_retry(self, task_id: str) -> None:
        t = self._records.get(task_id)
        if t:
            t.retry_count += 1

    def finish_tracking(self, task_id: str, status: str = "COMPLETED") -> TaskTelemetry | None:
        t = self._records.get(task_id)
        if not t:
            return None

        t.end_time = time.time()
        t.duration_ms = int((t.end_time - t.start_time) * 1000)
        t.status = status
        try:
            t.cpu_percent_avg = round(self._process.cpu_percent(interval=None), 1)
            t.ram_mb_peak = round(self._process.memory_info().rss / (1024 * 1024), 1)
        except Exception:
            pass

        logger.debug(f"Telemetri ({task_id}): Süre={t.duration_ms}ms, Ajanlar={len(t.agents_used)}, API={t.api_calls}")
        return t

    def get_task_telemetry(self, task_id: str) -> dict[str, Any] | None:
        t = self._records.get(task_id)
        if not t:
            return None
        return {
            "task_id": t.task_id,
            "duration_ms": t.duration_ms,
            "agents_count": len(t.agents_used),
            "agents_used": t.agents_used,
            "api_calls": t.api_calls,
            "tokens_estimated": t.tokens_estimated,
            "retry_count": t.retry_count,
            "cpu_percent": t.cpu_percent_avg,
            "ram_mb": t.ram_mb_peak,
            "status": t.status
        }

    def generate_benchmark_summary(self) -> dict[str, Any]:
        """Tüm kayıtlı görevlerin genel performans ve benchmark özetini döner."""
        mem = round(self._process.memory_info().rss / (1024 * 1024), 1)
        if not self._records:
            return {
                "total_tasks": 0,
                "success_rate": 1.0,
                "active_memory_mb": mem,
                "avg_duration_ms": 0,
                "total_api_calls": 0,
                "total_tokens_estimated": 0
            }

        total = len(self._records)
        completed = sum(1 for t in self._records.values() if t.status in ("COMPLETED", "VERIFIED_COMPLETED"))
        total_duration = sum(t.duration_ms for t in self._records.values())
        total_api = sum(t.api_calls for t in self._records.values())
        total_tokens = sum(t.tokens_estimated for t in self._records.values())

        return {
            "total_tasks": total,
            "success_rate": round(completed / total, 2),
            "avg_duration_ms": int(total_duration / total) if total else 0,
            "total_api_calls": total_api,
            "total_tokens_estimated": total_tokens,
            "active_memory_mb": round(self._process.memory_info().rss / (1024 * 1024), 1)
        }


# Global TelemetryTracker Singleton
telemetry_tracker = TelemetryTracker()
