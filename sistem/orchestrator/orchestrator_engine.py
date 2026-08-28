"""
ULTRON Orchestrator — Central Multi-Agent Orchestration Engine (v15)
───────────────────────────────────────────────────────────────────
• Merkezi Ajan Koordinatörü (Central Orchestrator)
• Görev Karmaşıklık Yönlendirmesi (SIMPLE, MEDIUM, COMPLEX, CRITICAL)
• Paralel ve Sıralı Ajan İş Akışları (Multi-Agent Pipeline)
• Kesin Doğrulama Kapısı (VERIFIED_COMPLETED Gate) ve Hata Kurtarma (Failure Recovery)
"""

from __future__ import annotations

import concurrent.futures
import json
import logging
import os
import time
from typing import Any

from orchestrator.agent_registry import agent_registry
from orchestrator.task_queue import agent_task_queue, AgentTask
from orchestrator.coding_agent import CodingAgent
from orchestrator.testing_agent import TestingAgent
from orchestrator.reviewer_agent import ReviewerAgent
from orchestrator.terminal_agent import TerminalAgent
from orchestrator.git_safety import get_git_diff, create_snapshot, rollback_to_snapshot
from computer.safety_manager import SafetyManager

logger = logging.getLogger("ultron.orchestrator.engine")


class OrchestratorEngine:
    """U.L.T.R.O.N Merkezi Çoklu Ajan ve Yazılım Mühendisliği Orkestratörü."""

    @staticmethod
    def assess_complexity(task_description: str) -> str:
        """Görevin karmaşıklık seviyesini belirler."""
        desc = task_description.lower().strip()
        if any(w in desc for w in ("mimari", "proje", "sistem", "refactor", "yeniden tasarla", "büyük")):
            return "CRITICAL"
        elif any(w in desc for w in ("ekle", "geliştir", "oluştur", "düzenle", "araştır ve kodla")):
            return "COMPLEX"
        elif any(w in desc for w in ("düzelt", "test et", "incele", "hata", "fix")):
            return "MEDIUM"
        return "SIMPLE"

    @classmethod
    def orchestrate_task(cls, task_description: str, user_name: str = "Nuri Can") -> dict[str, Any]:
        """
        Kullanıcı isteğini analiz eder, uzman ajanları koordine eder, yürütür ve doğrular.
        PLAN -> DELEGATE -> EXECUTE -> TEST -> REVIEW -> VERIFY -> REPORT
        """
        # SwarmReporter'a kaydol
        task_id = None
        try:
            from core.swarm_reporter import swarm_reporter
            task_id = swarm_reporter.register_task(
                agent_name="Orchestrator",
                description=task_description[:100],
            )
        except Exception:
            pass

        try:
            from orchestrator.supervisor import supervisor_engine
            result = supervisor_engine.run_supervisor_workflow(task_description, user_name=user_name)
            if task_id:
                try:
                    from core.swarm_reporter import swarm_reporter
                    swarm_reporter.complete_task(task_id, success=True, summary="Görev tamamlandı.")
                except Exception:
                    pass
            return result
        except Exception as e:
            if task_id:
                try:
                    from core.swarm_reporter import swarm_reporter
                    swarm_reporter.complete_task(task_id, success=False, summary=str(e)[:100])
                except Exception:
                    pass
            raise
