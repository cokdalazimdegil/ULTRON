"""
ULTRON — Kimlik ve Güvenlik Modülü (Voice Recognition Bağımsız)
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger("ultron.core.multimodal_auth")


class AuthStatus(str, Enum):
    VERIFIED   = "VERIFIED"     # Doğrulanmış yetkili kullanıcı
    UNCERTAIN  = "UNCERTAIN"    # Kararsız
    UNKNOWN    = "UNKNOWN"      # Tanınmayan
    RESTRICTED = "RESTRICTED"   # Kısıtlı mod


class SecurityTier(int, Enum):
    TIER_1_GUEST      = 1
    TIER_2_USER       = 2
    TIER_3_ADMIN_ROOT = 3


@dataclass
class MultimodalAuthDecision:
    user_name: str = "YARATICI"
    status: AuthStatus = AuthStatus.VERIFIED
    fused_score: float = 1.0
    voice_score: float = 1.0
    style_score: float = 1.0
    visual_score: Optional[float] = None
    margin: float = 1.0
    security_tier: SecurityTier = SecurityTier.TIER_3_ADMIN_ROOT
    verified_factors: list[str] = field(default_factory=lambda: ["Direct Access"])
    timestamp: float = field(default_factory=time.time)
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "user_name": self.user_name,
            "status": self.status.value,
            "fused_score": round(self.fused_score, 4),
            "voice_score": round(self.voice_score, 4),
            "style_score": round(self.style_score, 4),
            "visual_score": round(self.visual_score, 4) if self.visual_score is not None else None,
            "margin": round(self.margin, 4),
            "security_tier": self.security_tier.value,
            "verified_factors": self.verified_factors,
            "timestamp": self.timestamp,
            "details": self.details
        }


PRIVILEGED_ROOT_TOOLS: set[str] = {
    "shell", "execute_command", "run_terminal", "file_tools", "write_to_file",
    "replace_file_content", "computer_control", "mouse_controller", "keyboard_controller",
    "code_action", "orchestrate_task", "autonomous_task"
}


class MultimodalAuthEngine:
    """
    Sadeleştirilmiş, kesintisiz çalışan kimlik doğrulama motoru.
    Ses profili engeli olmadan tüm komutların akıcı çalışmasını sağlar.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._current_user = "YARATICI"
        self._last_decision: MultimodalAuthDecision = MultimodalAuthDecision(
            user_name=self._current_user,
            status=AuthStatus.VERIFIED,
            fused_score=1.0,
            voice_score=1.0,
            style_score=1.0,
            visual_score=None,
            margin=1.0,
            security_tier=SecurityTier.TIER_3_ADMIN_ROOT,
            verified_factors=["Direct Access"]
        )
        self._history: list[MultimodalAuthDecision] = [self._last_decision]

    @property
    def current_user(self) -> str:
        with self._lock:
            return self._current_user

    def set_active_user(self, user: str) -> None:
        with self._lock:
            self._current_user = user or "YARATICI"
            self._last_decision = MultimodalAuthDecision(
                user_name=self._current_user,
                status=AuthStatus.VERIFIED,
                fused_score=1.0,
                voice_score=1.0,
                style_score=1.0,
                visual_score=None,
                margin=1.0,
                security_tier=SecurityTier.TIER_3_ADMIN_ROOT if self._current_user.lower() == "nuri can" else SecurityTier.TIER_2_USER,
                verified_factors=["Direct Access"]
            )

    def evaluate_identity(
        self,
        pcm_audio: Optional[bytes] = None,
        spoken_text: str = "",
        camera_frame: Optional[bytes] = None
    ) -> MultimodalAuthDecision:
        with self._lock:
            decision = MultimodalAuthDecision(
                user_name=self._current_user,
                status=AuthStatus.VERIFIED,
                fused_score=1.0,
                voice_score=1.0,
                style_score=1.0,
                visual_score=None,
                margin=1.0,
                security_tier=SecurityTier.TIER_3_ADMIN_ROOT if self._current_user.lower() == "nuri can" else SecurityTier.TIER_2_USER,
                verified_factors=["Direct Access"]
            )
            self._last_decision = decision
            return decision

    def check_tool_authorization(self, tool_name: str, target: str = "") -> tuple[bool, str]:
        return True, "Authorized"

    def get_latest_decision(self) -> MultimodalAuthDecision:
        with self._lock:
            return self._last_decision


# Canonical Global Singleton Instance
multimodal_auth_engine = MultimodalAuthEngine()
