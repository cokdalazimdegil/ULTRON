"""
ULTRON Supervisor — Compatibility Facade (V17 Consolidated)
───────────────────────────────────────────────────────────
Bu modül geriye dönük uyumluluk (backward compatibility) için sağlanmaktadır.
Canonical Supervisor motoru doğrudan `orchestrator/supervisor_2.py` altındaki
`SupervisorEngine` sınıfı ve `supervisor_engine` singleton nesnesidir.
"""

from __future__ import annotations

from orchestrator.supervisor_2 import (
    SupervisorEngine,
    SupervisorEngine2,
    supervisor_engine,
    supervisor_engine_v2,
    AgentResult,
    TaskLifecycleState,
    SubTaskNode,
    MasterTaskDAG,
    MAX_REASSIGNMENTS,
    MAX_SELF_CORRECTION_ATTEMPTS,
    MAX_PARALLEL_AGENTS,
)

__all__ = [
    "SupervisorEngine",
    "SupervisorEngine2",
    "supervisor_engine",
    "supervisor_engine_v2",
    "AgentResult",
    "TaskLifecycleState",
    "SubTaskNode",
    "MasterTaskDAG",
    "MAX_REASSIGNMENTS",
    "MAX_SELF_CORRECTION_ATTEMPTS",
    "MAX_PARALLEL_AGENTS",
]
