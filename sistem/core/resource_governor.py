"""
ULTRON Resource Governor & Agent Budget Controller (V17)
═════════════════════════════════════════════════════════
• Merkezi Ajan Kaynak Bütçesi (AgentBudget Policy)
• Çalışma Zamanı, Araç Çağrısı ve Yeniden Deneme Sınırları
• BUDGET_EXCEEDED Durum Tespiti, Durdurma ve Üst Kademeye Yönlendirme (Escalation)
• Mevcut Telemetri Tracker ile Kusursuz Entegrasyon
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from orchestrator.telemetry import telemetry_tracker

logger = logging.getLogger("ultron.core.resource_governor")


class BudgetViolationType(str, Enum):
    RUNTIME_EXCEEDED     = "RUNTIME_EXCEEDED"
    TOOL_CALLS_EXCEEDED  = "TOOL_CALLS_EXCEEDED"
    RETRIES_EXCEEDED     = "RETRIES_EXCEEDED"
    CONTEXT_OVERFLOW     = "CONTEXT_OVERFLOW"


@dataclass
class AgentBudget:
    max_runtime_sec: float = 120.0       # Azami çalışma süresi (2 dakika)
    max_retries: int = 3                 # Azami yeniden deneme
    max_tool_calls: int = 25             # Azami araç çalıştırma
    max_context_size: int = 8192         # Azami bağlam boyutu
    priority: int = 1                    # 1 (Normal), 2 (Yüksek), 3 (Kritik)


@dataclass
class AgentUsageState:
    agent_id: str
    task_id: str
    start_time: float = field(default_factory=time.time)
    tool_calls_count: int = 0
    retries_count: int = 0
    is_halted: bool = False
    halt_reason: str = ""


class ResourceGovernor:
    """Merkezi Ajan Kaynak ve Bütçe Yöneticisi."""

    DEFAULT_BUDGETS: dict[str, AgentBudget] = {
        "coding_agent":   AgentBudget(max_runtime_sec=180.0, max_retries=3, max_tool_calls=30, priority=2),
        "testing_agent":  AgentBudget(max_runtime_sec=90.0,  max_retries=2, max_tool_calls=15, priority=2),
        "reviewer_agent": AgentBudget(max_runtime_sec=60.0,  max_retries=2, max_tool_calls=10, priority=1),
        "terminal_agent": AgentBudget(max_runtime_sec=120.0, max_retries=2, max_tool_calls=20, priority=2),
        "research_agent": AgentBudget(max_runtime_sec=150.0, max_retries=3, max_tool_calls=25, priority=1),
        "computer_agent": AgentBudget(max_runtime_sec=90.0,  max_retries=3, max_tool_calls=20, priority=2),
        "supervisor":     AgentBudget(max_runtime_sec=300.0, max_retries=3, max_tool_calls=50, priority=3),
    }

    def __init__(self):
        self._lock = threading.RLock()
        self._active_sessions: dict[str, AgentUsageState] = {}

    def start_session(self, task_id: str, agent_id: str) -> AgentUsageState:
        with self._lock:
            key = f"{task_id}_{agent_id}"
            state = AgentUsageState(agent_id=agent_id, task_id=task_id, start_time=time.time())
            self._active_sessions[key] = state
            return state

    def record_tool_call(self, task_id: str, agent_id: str) -> tuple[bool, str]:
        """Araç çağrısını kaydeder ve bütçe aşımını denetler."""
        with self._lock:
            key = f"{task_id}_{agent_id}"
            state = self._active_sessions.get(key)
            if not state:
                state = self.start_session(task_id, agent_id)

            state.tool_calls_count += 1
            budget = self.DEFAULT_BUDGETS.get(agent_id, AgentBudget())

            # 1. Tool Call Kontrolü
            if state.tool_calls_count > budget.max_tool_calls:
                state.is_halted = True
                state.halt_reason = f"Azami araç çağrı sınırı aşıldı ({state.tool_calls_count}/{budget.max_tool_calls})"
                logger.warning(f"[Governor] 🚨 {agent_id} bütçe aşımı: {state.halt_reason}")
                return False, state.halt_reason

            # 2. Runtime Kontrolü
            elapsed = time.time() - state.start_time
            if elapsed > budget.max_runtime_sec:
                state.is_halted = True
                state.halt_reason = f"Azami çalışma süresi aşıldı ({elapsed:.1f}s / {budget.max_runtime_sec}s)"
                logger.warning(f"[Governor] 🚨 {agent_id} süre aşımı: {state.halt_reason}")
                return False, state.halt_reason

            return True, "OK"

    def record_retry(self, task_id: str, agent_id: str) -> tuple[bool, str]:
        with self._lock:
            key = f"{task_id}_{agent_id}"
            state = self._active_sessions.get(key)
            if not state:
                state = self.start_session(task_id, agent_id)

            state.retries_count += 1
            budget = self.DEFAULT_BUDGETS.get(agent_id, AgentBudget())

            if state.retries_count > budget.max_retries:
                state.is_halted = True
                state.halt_reason = f"Azami yeniden deneme sınırı aşıldı ({state.retries_count}/{budget.max_retries})"
                return False, state.halt_reason

            return True, "OK"

    def end_session(self, task_id: str, agent_id: str) -> None:
        with self._lock:
            key = f"{task_id}_{agent_id}"
            self._active_sessions.pop(key, None)


# Global Singleton
resource_governor = ResourceGovernor()
