"""
ULTRON Autonomous Software Engineering, Supervisor & Multi-Agent Network (v16)
─────────────────────────────────────────────────────────────────────────────
• Merkezi Supervisor Engine, Delegasyon & Ajan Sözleşmesi (AgentResult)
• Dinamik Görev Ayrıştırma, Dosya Kilit Yönetimi (FileLockManager)
• Telemetri, Benchmark & Görev Kalıcılık/Devam Ettirme (TaskStateStore)
"""

from orchestrator.agent_registry import (
    AgentRegistry,
    AgentProfile,
    AgentCapabilities,
    agent_registry,
    MAX_SUBAGENT_DEPTH
)

from orchestrator.task_queue import (
    AgentTaskQueue,
    AgentTask,
    agent_task_queue
)

from orchestrator.coding_agent import (
    CodingAgent,
    MAX_AUTOFIX_ATTEMPTS
)

from orchestrator.testing_agent import (
    TestingAgent
)

from orchestrator.reviewer_agent import (
    ReviewerAgent
)

from orchestrator.terminal_agent import (
    TerminalAgent
)

from orchestrator.git_safety import (
    get_git_status,
    get_git_diff,
    create_snapshot,
    rollback_to_snapshot
)

from orchestrator.orchestrator_engine import (
    OrchestratorEngine
)

from orchestrator.agent_lock import (
    FileLockManager,
    file_lock_manager
)

from orchestrator.task_state_store import (
    TaskStateStore,
    task_state_store
)

from orchestrator.telemetry import (
    TelemetryTracker,
    telemetry_tracker
)

from orchestrator.supervisor import (
    SupervisorEngine,
    supervisor_engine,
    AgentResult
)

from orchestrator.supervisor_2 import (
    SupervisorEngine2,
    supervisor_engine_v2,
    MasterTaskDAG,
    SubTaskNode,
    TaskLifecycleState,
)

__all__ = [
    "AgentRegistry",
    "AgentProfile",
    "AgentCapabilities",
    "agent_registry",
    "MAX_SUBAGENT_DEPTH",
    "AgentTaskQueue",
    "AgentTask",
    "agent_task_queue",
    "CodingAgent",
    "MAX_AUTOFIX_ATTEMPTS",
    "TestingAgent",
    "ReviewerAgent",
    "TerminalAgent",
    "get_git_status",
    "get_git_diff",
    "create_snapshot",
    "rollback_to_snapshot",
    "OrchestratorEngine",
    "FileLockManager",
    "file_lock_manager",
    "TaskStateStore",
    "task_state_store",
    "TelemetryTracker",
    "telemetry_tracker",
    "SupervisorEngine",
    "supervisor_engine",
    "AgentResult",
    "SupervisorEngine2",
    "supervisor_engine_v2",
    "MasterTaskDAG",
    "SubTaskNode",
    "TaskLifecycleState",
]

