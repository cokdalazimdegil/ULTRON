"""
ULTRON Orchestrator — Agent Registry & Permission System
────────────────────────────────────────────────────────
• Çoklu ajan (Multi-Agent) tanımları, rolleri ve yetenekleri (Capabilities)
• Yetenek bazlı izin modeli (Capability-Based Permissions)
• Alt ajan derinlik sınırı (Sub-Agent Depth Control — Max Depth = 1)
• Ajan durum ve görev geçmişi takibi
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("ultron.orchestrator.agent_registry")

MAX_SUBAGENT_DEPTH = 1


@dataclass
class AgentCapabilities:
    read_files: bool = True
    write_files: bool = False
    execute_code: bool = False
    run_shell: bool = False
    run_tests: bool = False
    inspect_diff: bool = False
    review_code: bool = False
    web_search: bool = False
    screen_control: bool = False
    delete_files: bool = False
    security_audit: bool = False


@dataclass
class AgentProfile:
    agent_id: str
    name: str
    role: str
    description: str
    capabilities: AgentCapabilities
    status: str = "IDLE"  # IDLE, BUSY, PAUSED, ERROR
    current_task_id: str | None = None
    task_history: list[str] = field(default_factory=list)
    success_count: int = 0
    failure_count: int = 0
    depth_level: int = 0  # 0: Root orchestrator, 1: Specialist agent


class AgentRegistry:
    """Merkezi Ajan Kayıt ve Yetki Yönetim Sistemi."""

    def __init__(self):
        self._agents: dict[str, AgentProfile] = {}
        self._lock = threading.RLock()
        self._register_default_specialists()

    def _register_default_specialists(self) -> None:
        """Sistemin varsayılan uzman yapay zeka ajanlarını kaydeder."""
        # 1. Coding Agent (Yazılım Geliştirici)
        self.register_agent(
            AgentProfile(
                agent_id="coding_agent",
                name="Coding Agent",
                role="Software Engineer",
                description="Kod yazar, mevcut dosyaları düzenler, hata ayıklar ve refactor eder.",
                capabilities=AgentCapabilities(
                    read_files=True,
                    write_files=True,
                    execute_code=True,
                    run_shell=False,
                    run_tests=True,
                    delete_files=False
                )
            )
        )

        # 2. Testing Agent (Test Mühendisi)
        self.register_agent(
            AgentProfile(
                agent_id="testing_agent",
                name="Testing Agent",
                role="QA & Test Automation Specialist",
                description="Birim, entegrasyon ve çalışma zamanı testlerini yürütür, logları denetler.",
                capabilities=AgentCapabilities(
                    read_files=True,
                    write_files=False,
                    execute_code=True,
                    run_shell=True,
                    run_tests=True
                )
            )
        )

        # 3. Reviewer Agent (Kod İnceleme & Kalite)
        self.register_agent(
            AgentProfile(
                agent_id="reviewer_agent",
                name="Reviewer Agent",
                role="Senior Code Reviewer & Architect",
                description="Yazılan kodu, git diff farklarını, mantık hatalarını ve regresyon risklerini denetler.",
                capabilities=AgentCapabilities(
                    read_files=True,
                    write_files=False,
                    execute_code=False,
                    inspect_diff=True,
                    review_code=True,
                    security_audit=True
                )
            )
        )

        # 4. Terminal Agent (Sistem & Komut Yürütücü)
        self.register_agent(
            AgentProfile(
                agent_id="terminal_agent",
                name="Terminal Agent",
                role="System & DevOps Engineer",
                description="Terminal komutlarını güvenle çalıştırır, çıktıları yakalar ve paketleri yönetir.",
                capabilities=AgentCapabilities(
                    read_files=True,
                    write_files=False,
                    execute_code=True,
                    run_shell=True,
                    inspect_diff=True
                )
            )
        )

        # 5. Research Agent (Araştırma Uzmanı)
        self.register_agent(
            AgentProfile(
                agent_id="research_agent",
                name="Research Agent",
                role="Web & Knowledge Researcher",
                description="Web araması yapar, API/kütüphane dokümantasyonunu inceler ve sentezler.",
                capabilities=AgentCapabilities(
                    read_files=True,
                    write_files=False,
                    web_search=True
                )
            )
        )

        # 6. Computer Agent (Masaüstü & Arayüz Uzmanı)
        self.register_agent(
            AgentProfile(
                agent_id="computer_agent",
                name="Computer Agent",
                role="Computer-Use Specialist",
                description="Masaüstünü görür, pencereleri, fare ve klavyeyi kontrol eder.",
                capabilities=AgentCapabilities(
                    read_files=True,
                    screen_control=True
                )
            )
        )

        # 7. Security Agent (Güvenlik Denetçisi)
        self.register_agent(
            AgentProfile(
                agent_id="security_agent",
                name="Security Agent",
                role="Security & Compliance Auditor",
                description="Güvenlik açıklarını, izin ihlallerini ve riskli komutları denetler.",
                capabilities=AgentCapabilities(
                    read_files=True,
                    security_audit=True,
                    inspect_diff=True
                )
            )
        )

    def register_agent(self, profile: AgentProfile) -> None:
        with self._lock:
            self._agents[profile.agent_id] = profile

    def get_agent(self, agent_id: str) -> AgentProfile | None:
        with self._lock:
            return self._agents.get(agent_id)

    def list_agents(self) -> list[dict[str, Any]]:
        with self._lock:
            return [
                {
                    "agent_id": a.agent_id,
                    "name": a.name,
                    "role": a.role,
                    "status": a.status,
                    "current_task": a.current_task_id,
                    "success_count": a.success_count,
                    "failure_count": a.failure_count
                }
                for a in self._agents.values()
            ]

    def check_permission(self, agent_id: str, capability: str) -> tuple[bool, str]:
        """Ajanın istenen yeteneğe sahip olup olmadığını doğrular."""
        agent = self.get_agent(agent_id)
        if not agent:
            return False, f"Bilinmeyen ajan: '{agent_id}'"

        caps = agent.capabilities
        allowed = getattr(caps, capability, False)
        if not allowed:
            return False, f"İzin Reddedildi: '{agent.name}' ajanının '{capability}' yetkisi bulunmuyor."
        return True, "İzin verildi."

    def assign_task(self, agent_id: str, task_id: str, depth: int = 1) -> tuple[bool, str]:
        """Ajana görev atar (Derinlik kontrolü ile)."""
        if depth > MAX_SUBAGENT_DEPTH:
            return False, f"Derinlik sınırı aşıldı (Max={MAX_SUBAGENT_DEPTH}, İstenen={depth}). Sonsuz alt-ajan zinciri engellendi."

        with self._lock:
            agent = self._agents.get(agent_id)
            if not agent:
                return False, f"Ajan bulunamadı: '{agent_id}'"

            agent.status = "BUSY"
            agent.current_task_id = task_id
            agent.depth_level = depth
            agent.task_history.append(task_id)
            return True, f"Görev {agent.name} ajanına atandı."

    def release_agent(self, agent_id: str, success: bool = True) -> None:
        with self._lock:
            agent = self._agents.get(agent_id)
            if agent:
                agent.status = "IDLE"
                agent.current_task_id = None
                if success:
                    agent.success_count += 1
                else:
                    agent.failure_count += 1


# Global AgentRegistry Singleton
agent_registry = AgentRegistry()
