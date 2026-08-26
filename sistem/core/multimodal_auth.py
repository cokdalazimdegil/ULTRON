"""
ULTRON — Ultra-Hardened Çok Modlu Kimlik Doğrulama & Bayesian Güvenlik Motoru
════════════════════════════════════════════════════════════════════════════
• Bayesian Zamansal İnanç Durumu Takibi (Bayesian Temporal Belief State Tracking)
• 3 Faktörlü Füzyon: Akustik CAM++ & Pitch + Türkçe Morfolojik Stilometri + Liveness Yüz Kamerası
• 3 Kademeli Yetkilendirme Politikası (Tier-1 Guest, Tier-2 User, Tier-3 Root/Admin)
• Fail-Closed Ayrıcalıklı Araç Koruması (Terminal, Kod, Dosya & Bilgisayar Kontrolü)
"""

from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from actions.stylometry_analyzer import stylometry_analyzer, StylometryReport
from actions.visual_biometrics import visual_biometrics, VisualBiometricsReport
from actions.voice_recognition import identify_speaker_from_pcm, default_speaker_tracker

logger = logging.getLogger("ultron.core.multimodal_auth")


class AuthStatus(str, Enum):
    VERIFIED   = "VERIFIED"     # Kesin doğrulanmış yetkili kullanıcı
    UNCERTAIN  = "UNCERTAIN"    # Kararsız / Eşik sınırında (Ek kanıt bekleniyor)
    UNKNOWN    = "UNKNOWN"      # Tanınmayan / Yetkisiz kişi (Sistem kilitli)
    RESTRICTED = "RESTRICTED"   # Kısıtlı misafir modu


class SecurityTier(int, Enum):
    TIER_1_GUEST      = 1  # Yalnızca genel bilgi okuma, saat, hava durumu
    TIER_2_USER       = 2  # Müzik, anımsatıcılar, genel asistan sohbeti (Rabia vb.)
    TIER_3_ADMIN_ROOT = 3  # Terminal, kod çalıştırma, dosya değiştirme, bilgisayar kontrolü (Yalnızca Nuri Can)


@dataclass
class MultimodalAuthDecision:
    user_name: str
    status: AuthStatus
    fused_score: float
    voice_score: float
    style_score: float
    visual_score: Optional[float]
    margin: float
    security_tier: SecurityTier
    verified_factors: list[str] = field(default_factory=list)
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


# Yüksek Riskli Root / Admin Araçları
PRIVILEGED_ROOT_TOOLS: set[str] = {
    "shell", "execute_command", "run_terminal", "file_tools", "write_to_file",
    "replace_file_content", "computer_control", "mouse_controller", "keyboard_controller",
    "code_action", "orchestrate_task", "autonomous_task"
}


class MultimodalAuthEngine:
    """
    Bayesian Zamansal Olasılık Takibi ve 3 Kademeli Yetkilendirme Motoru.
    """

    def __init__(self):
        self._lock = threading.RLock()
        self._current_user = "Bilinmeyen"
        
        # Bayesian İnanç Durumu (Belief State: P(User))
        self._belief_state: dict[str, float] = {
            "Nuri Can": 0.05,
            "Rabia": 0.05,
            "Bilinmeyen": 0.90
        }
        self._decay_factor = 0.88

        self._last_decision: MultimodalAuthDecision = MultimodalAuthDecision(
            user_name="Bilinmeyen",
            status=AuthStatus.UNKNOWN,
            fused_score=0.0,
            voice_score=0.0,
            style_score=0.0,
            visual_score=None,
            margin=0.0,
            security_tier=SecurityTier.TIER_1_GUEST
        )
        self._history: list[MultimodalAuthDecision] = []

    @property
    def current_user(self) -> str:
        with self._lock:
            return self._current_user

    def set_active_user(self, user: str) -> None:
        with self._lock:
            self._current_user = user
            default_speaker_tracker.set_active_user(user)
            # İnanç durumunu resetle / ayarla
            for k in self._belief_state:
                self._belief_state[k] = 0.90 if k == user else 0.05

    def evaluate_identity(
        self,
        pcm_audio: Optional[bytes] = None,
        spoken_text: str = "",
        camera_frame: Optional[bytes] = None
    ) -> MultimodalAuthDecision:
        """
        Gelen ses, metin ve kamera karelerini Bayesian zamansal füzyonla değerlendirir.
        """
        with self._lock:
            # 1. Ses Biyometrisi Likelihood
            voice_speaker = "Bilinmeyen"
            voice_score = 0.0
            voice_meta: dict[str, Any] = {}

            if pcm_audio and len(pcm_audio) >= 1000:
                voice_speaker, voice_score, voice_meta = identify_speaker_from_pcm(pcm_audio)

            # 2. Konuşma Tarzı Likelihood
            style_report: Optional[StylometryReport] = None
            style_score = 0.0
            style_speaker = "Bilinmeyen"

            if spoken_text and spoken_text.strip():
                style_report = stylometry_analyzer.analyze_text(spoken_text)
                style_speaker = style_report.best_match
                style_score = style_report.confidence

            # 3. Görsel Yüz & Canlılık Likelihood
            visual_report: Optional[VisualBiometricsReport] = None
            visual_score: Optional[float] = None
            visual_speaker = "Bilinmeyen"

            if camera_frame:
                visual_report = visual_biometrics.process_camera_frame(
                    camera_frame, active_hint_user=voice_speaker if voice_speaker != "Bilinmeyen" else style_speaker
                )
            else:
                visual_report = visual_biometrics.get_latest_report(max_age_sec=3.0)

            if visual_report and visual_report.is_camera_active and visual_report.face_detected and visual_report.is_live:
                visual_score = visual_report.confidence
                visual_speaker = visual_report.best_match

            # 0. Boş / Sessizlik Durumu (Idle Retention)
            if pcm_audio is None and not spoken_text and camera_frame is None:
                final_user = self._current_user if self._current_user != "Bilinmeyen" else "Bilinmeyen"
                final_status = AuthStatus.UNCERTAIN if final_user != "Bilinmeyen" else AuthStatus.UNKNOWN
                tier = SecurityTier.TIER_3_ADMIN_ROOT if final_user.lower() == "nuri can" else (SecurityTier.TIER_2_USER if final_user != "Bilinmeyen" else SecurityTier.TIER_1_GUEST)
                decision = MultimodalAuthDecision(
                    user_name=final_user,
                    status=final_status,
                    fused_score=self._belief_state.get(final_user, 0.5),
                    voice_score=0.0,
                    style_score=0.0,
                    visual_score=None,
                    margin=0.0,
                    security_tier=tier,
                    verified_factors=[],
                    details={"idle_retention": True}
                )
                self._last_decision = decision
                return decision

            # 4. Aday Puanlama & Bayesian Likelihood Güncellemesi
            candidate_users = ["Nuri Can", "Rabia"]
            breakdowns: dict[str, Any] = {}
            likelihoods: dict[str, float] = {}

            # Ağırlıklar: Kamera varsa %50 Ses + %25 Tarz + %25 Kamera
            if visual_score is not None:
                w_v, w_s, w_c = 0.50, 0.25, 0.25
            else:
                w_v, w_s, w_c = 0.65, 0.35, 0.00

            total_weight = w_v + w_s + w_c

            for user in candidate_users:
                user_key = user.lower().replace(" ", "_")
                
                # Ses skoru
                v_sc = 0.0
                if voice_meta.get("hybrid_breakdown"):
                    v_sc = voice_meta["hybrid_breakdown"].get(user, {}).get("match_score", 0.0)
                elif voice_speaker.lower() == user.lower():
                    v_sc = voice_score

                # Tarz skoru
                s_sc = 0.0
                if style_report and style_report.scores:
                    s_sc = style_report.scores.get(user_key, 0.0)

                # Görsel skor
                c_sc = 0.0
                if visual_report and visual_report.is_camera_active and visual_report.face_detected:
                    c_sc = visual_report.scores.get(user_key, 0.0)

                fused_inst = (w_v * v_sc + w_s * s_sc + (w_c * c_sc if visual_score is not None else 0.0)) / total_weight
                likelihoods[user] = max(0.01, min(1.0, fused_inst))
                breakdowns[user] = {
                    "voice": round(v_sc, 3),
                    "style": round(s_sc, 3),
                    "visual": round(c_sc, 3) if visual_score is not None else None,
                    "instant_fused": round(fused_inst, 3)
                }

            # 5. Bayesian Zamansal Güncelleme (Recursive Update)
            new_belief = {}
            for user in candidate_users:
                prior = (self._belief_state.get(user, 0.05) ** self._decay_factor)
                like = likelihoods[user]
                new_belief[user] = prior * (like ** 1.2)

            # Bilinmeyen / Yetkisiz inancı
            unknown_like = 0.85 if max(likelihoods.values()) < 0.40 else 0.15
            new_belief["Bilinmeyen"] = (self._belief_state.get("Bilinmeyen", 0.5) ** self._decay_factor) * unknown_like

            # Normalize et
            total_prob = sum(new_belief.values()) or 1.0
            for k in new_belief:
                new_belief[k] = new_belief[k] / total_prob
            self._belief_state = new_belief

            # En yüksek adayı ve marjı bul
            candidate_prob_sorted = sorted(candidate_users, key=lambda u: breakdowns[u]["instant_fused"], reverse=True)
            top1_user = candidate_prob_sorted[0]
            top2_user = candidate_prob_sorted[1] if len(candidate_prob_sorted) > 1 else None
            top1_breakdown = breakdowns[top1_user]
            top2_breakdown = breakdowns[top2_user] if top2_user else {}
            
            fused_score = top1_breakdown["instant_fused"]
            margin = fused_score - top2_breakdown.get("instant_fused", 0.0)


            # 6. Doğrulama Kararı & Kademeli Yetkilendirme
            verified_factors = []
            if top1_breakdown.get("voice", 0.0) >= 0.40:
                verified_factors.append("VOICE")
            if top1_breakdown.get("style", 0.0) >= 0.25:
                verified_factors.append("STYLE")
            if top1_breakdown.get("visual") and top1_breakdown["visual"] >= 0.70:
                verified_factors.append("CAMERA")

            final_status = AuthStatus.UNKNOWN
            final_user = "Bilinmeyen"
            tier = SecurityTier.TIER_1_GUEST

            # Anti-Spoofing Katı Kuralı: Ses verilmişse ve akustik olarak Bilinmeyen ise kesin UNKNOWN
            is_stranger_audio = (pcm_audio is not None and len(pcm_audio) >= 1000 and top1_breakdown.get("voice", 0.0) < 0.35)

            if is_stranger_audio:
                final_status = AuthStatus.UNKNOWN
                final_user = "Bilinmeyen"
                self._current_user = "Bilinmeyen"
                default_speaker_tracker.set_active_user("Bilinmeyen")
                tier = SecurityTier.TIER_1_GUEST

            # Doğrulama Kapısı: Fused >= 0.48, ses >= 0.35, marj >= 0.08
            elif fused_score >= 0.48 and (len(verified_factors) >= 1 and top1_breakdown.get("voice", 0.0) >= 0.35):
                final_status = AuthStatus.VERIFIED
                final_user = top1_user
                self._current_user = final_user
                default_speaker_tracker.set_active_user(final_user)

                # Yetki Seviyesi Belirleme
                if final_user.lower() == "nuri can":
                    tier = SecurityTier.TIER_3_ADMIN_ROOT
                else:
                    tier = SecurityTier.TIER_2_USER

                # Başarılı doğrulamada konuşma tarzı kelimelerini öğren
                if spoken_text and len(spoken_text.split()) >= 2:
                    stylometry_analyzer.learn_user_turn(final_user, spoken_text)

            elif fused_score >= 0.35 and pcm_audio is None:
                final_status = AuthStatus.UNCERTAIN
                final_user = self._current_user if self._current_user != "Bilinmeyen" else "Bilinmeyen"
                tier = SecurityTier.TIER_1_GUEST
            else:
                final_status = AuthStatus.UNKNOWN
                final_user = "Bilinmeyen"
                self._current_user = "Bilinmeyen"
                default_speaker_tracker.set_active_user("Bilinmeyen")
                tier = SecurityTier.TIER_1_GUEST

            decision = MultimodalAuthDecision(
                user_name=final_user,
                status=final_status,
                fused_score=fused_score,
                voice_score=top1_breakdown.get("voice", 0.0),
                style_score=top1_breakdown.get("style", 0.0),
                visual_score=top1_breakdown.get("visual"),
                margin=margin,
                security_tier=tier,
                verified_factors=verified_factors,
                details={
                    "breakdowns": breakdowns,
                    "belief_state": {k: round(v, 4) for k, v in self._belief_state.items()},
                    "voice_speaker": voice_speaker,
                    "style_speaker": style_speaker,
                    "visual_speaker": visual_speaker,
                    "camera_active": visual_report.is_camera_active if visual_report else False
                }
            )

            self._last_decision = decision
            self._history.append(decision)
            if len(self._history) > 50:
                self._history.pop(0)

            return decision

    def check_tool_authorization(self, tool_name: str, target: str = "") -> tuple[bool, str]:
        """
        Fail-Closed Güvenlik Yetkilendirmesi:
        Yüksek riskli araçların yalnızca Tier 3 Root (Nuri Can) tarafından çalıştırılmasına izin verir.
        """
        with self._lock:
            dec = self._last_decision
            is_root_tool = tool_name in PRIVILEGED_ROOT_TOOLS or any(w in tool_name for w in ("exec", "shell", "delete", "write", "code"))

            if is_root_tool:
                is_authorized_nuri = (
                    (dec.status == AuthStatus.VERIFIED or self._current_user.lower() == "nuri can") and
                    (dec.user_name.lower() == "nuri can" or self._current_user.lower() == "nuri can") and
                    dec.status != AuthStatus.UNKNOWN
                )
                if not is_authorized_nuri:
                    return False, f"🚨 GÜVENLİK KİLİDİ: '{tool_name}' işlemi Root (Nuri Can) yetkisi gerektirir. Konuşan kişi yetkisizdir ({dec.user_name})."

            return True, "Authorized"

    def get_latest_decision(self) -> MultimodalAuthDecision:
        with self._lock:
            return self._last_decision



# Canonical Global Singleton Instance
multimodal_auth_engine = MultimodalAuthEngine()
