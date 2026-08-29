"""
ULTRON Permission & Security Layer 2.0 (Central Policy Engine)
═════════════════════════════════════════════════════════════
• 4 Seviyeli Risk Değerlendirmesi (LOW, MEDIUM, HIGH, CRITICAL)
• Merkezi Yetkilendirme Hattı:
  REQUEST -> IDENTITY -> ACTION_CLASSIFICATION -> RISK_ASSESSMENT -> PERMISSION -> CONFIRMATION -> AUDIT_LOG
• Kesin Güvenlik Kuralı: FAIL-CLOSED (Hata durumunda daima REDDET)
• Yapılandırılmış Güvenlik Denetim Günlüğü (Structured Audit Logging)
"""

from __future__ import annotations

import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass, field, asdict
from enum import Enum
from pathlib import Path
from typing import Any

from app_paths import data_path

logger = logging.getLogger("ultron.core.security_manager")


AUDIT_LOG_FILE = data_path("memory", "security_audit.log")


class RiskLevel(str, Enum):
    LOW      = "LOW"       # Bilgi okuma, ekran yakalama, sistem bilgisi
    MEDIUM   = "MEDIUM"    # Uygulama açma, tarayıcıda gezinme, geçici dosya yazma
    HIGH     = "HIGH"      # Terminal çalıştırma, paket kurma, kod değiştirme
    CRITICAL = "CRITICAL"  # Format, sistem kapatma, kritik silme, kayıt defteri


@dataclass
class AuthorizationRequest:
    action_name: str
    target: str = ""
    actor: str = "YARATICI"
    is_authenticated: bool = True
    params: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


@dataclass
class AuthorizationDecision:
    allowed: bool
    risk_level: RiskLevel
    requires_user_confirmation: bool
    reason: str
    warning_message: str = ""
    audit_id: str = ""


class CentralSecurityEngine:
    """Merkezi Güvenlik ve İzin Yönetim Motoru."""

    # Kritik ve Yıkıcı Komut Desenleri
    CRITICAL_PATTERNS = [
        r"\b(format\s+[a-z]:|diskpart|vssadmin|bspadmin)",
        r"\b(shutdown\s+[/|-][s|r]|init\s+0|reboot)",
        r"\b(reg\s+(delete|add)|regedit)",
        r"\b(rmdir|rd)\b.*c:\\",
        r"\b(del|erase)\b.*c:\\windows",
        r"\b(drop\s+database|delete\s+from\s+users)",
    ]


    # Yüksek Riskli İşlem Desenleri
    HIGH_RISK_PATTERNS = [
        r"\b(pip\s+install|npm\s+install|cargo\s+install)\b",
        r"\b(taskkill|kill\s+-9|stop-process)\b",
        r"\b(git\s+reset\s+--hard|git\s+clean\s+-fd)\b",
        r"\b(set-executionpolicy|chmod\s+777)\b",
        r"\b(del\s+.*\.py|rm\s+-rf)\b",
    ]

    def __init__(self):
        self._lock = threading.RLock()
        self._emergency_stop = False

    def trigger_emergency_stop(self) -> None:
        """Sistemi acil durdurma moduna alır (Tüm aksiyonlar engellenir)."""
        with self._lock:
            self._emergency_stop = True
            logger.critical("[Security] 🚨 ACİL DURDURMA TETİKLENDİ! Tüm işlemler kilitlendi.")

    def reset_emergency_stop(self) -> None:
        with self._lock:
            self._emergency_stop = False
            logger.info("[Security] Acil durdurma kilidi sıfırlandı.")

    def is_emergency_stopped(self) -> bool:
        with self._lock:
            return self._emergency_stop

    def evaluate_risk(self, action_name: str, target: str = "", params: dict[str, Any] | None = None) -> RiskLevel:
        """Bir eylemin ve parametrelerinin risk seviyesini hesaplar."""
        action = action_name.lower().strip()
        target_str = str(target or "").lower()
        param_str = json.dumps(params or {}, ensure_ascii=False).lower()
        combined = f"{action} {target_str} {param_str}"

        # 1. Kritik Seviye Kontrolü
        for pat in self.CRITICAL_PATTERNS:
            if re.search(pat, combined):
                return RiskLevel.CRITICAL

        # 2. Yüksek Seviye Kontrolü
        for pat in self.HIGH_RISK_PATTERNS:
            if re.search(pat, combined):
                return RiskLevel.HIGH

        if any(w in action for w in ("terminal", "shell", "exec", "code", "bash", "powershell", "command", "cmd")):
            return RiskLevel.HIGH
        elif any(w in action for w in ("open_app", "open_url", "write_file", "close_app", "click", "mouse", "type", "keyboard")):
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW


    def authorize(self, req_or_action: AuthorizationRequest | str, params: dict[str, Any] | None = None,
                  target: str = "", user: str = "YARATICI", is_authenticated: bool = True) -> AuthorizationDecision:
        """
        Merkezi yetkilendirme kararı üretir.
        FAIL-CLOSED Kuralı: İstisna durumunda ASLA izin vermez.
        """
        if isinstance(req_or_action, AuthorizationRequest):
            req = req_or_action
        else:
            is_auth = (user.lower() not in {"bilinmeyen", "unknown"}) if user else is_authenticated
            req = AuthorizationRequest(
                action_name=str(req_or_action),
                target=target or (params.get("target", "") if params else ""),
                actor=user,
                is_authenticated=is_auth,
                params=params or {},
                timestamp=time.time()
            )

        audit_id = f"sec_{int(time.time()*1000)}"

        try:
            # 1. Acil Durdurma Kontrolü

            if self._emergency_stop:
                decision = AuthorizationDecision(
                    allowed=False,
                    risk_level=RiskLevel.CRITICAL,
                    requires_user_confirmation=False,
                    reason="Acil durdurma devrede. Hiçbir işlem çalıştırılamaz.",
                    warning_message="🚨 ACİL DURDURMA AKTİF",
                    audit_id=audit_id
                )
                self._write_audit(req, decision)
                return decision

            # 2. Risk Değerlendirmesi
            risk = self.evaluate_risk(req.action_name, req.target, req.params)

            # 3. Kimlik & Politika Doğrulaması
            # Bilinmeyen / Yetkisiz kullanıcılar bilgisayar otomasyonu veya riskli işlem çalıştıramaz
            if not req.is_authenticated or req.actor in ("Bilinmeyen", "Unknown", "UNKNOWN"):
                if risk in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL) or any(w in req.action_name for w in ("click", "type", "mouse", "keyboard", "exec", "open")):
                    decision = AuthorizationDecision(
                        allowed=False,
                        risk_level=risk,
                        requires_user_confirmation=False,
                        reason="Yetkisiz / Tanınmayan kullanıcı bilgisayar kontrolü veya riskli işlem çalıştıramaz.",
                        warning_message="🔒 YETKİSİZ İŞLEM REDDEDİLDİ",
                        audit_id=audit_id
                    )
                    self._write_audit(req, decision)
                    return decision


            # 4. Onay Gereksinimi
            if risk == RiskLevel.CRITICAL:
                decision = AuthorizationDecision(
                    allowed=False,  # Kritik işlemler varsayılan olarak durdurulur ve açık onay bekler
                    risk_level=risk,
                    requires_user_confirmation=True,
                    reason=f"Kritik güvenlik riski tespit edildi ({req.action_name}: {req.target})",
                    warning_message=f"⚠️ DİKKAT: Bu işlem sistem bütünlüğünü etkileyebilir. Onayınız gerekiyor.",
                    audit_id=audit_id
                )
            elif risk == RiskLevel.HIGH:
                decision = AuthorizationDecision(
                    allowed=True,
                    risk_level=risk,
                    requires_user_confirmation=True,
                    reason="Yüksek riskli terminal/kod yürütme.",
                    warning_message="⚡ Yüksek riskli işlem başlatılıyor.",
                    audit_id=audit_id
                )
            else:
                decision = AuthorizationDecision(
                    allowed=True,
                    risk_level=risk,
                    requires_user_confirmation=False,
                    reason="Düşük/Orta riskli güvenli işlem.",
                    audit_id=audit_id
                )

            self._write_audit(req, decision)
            return decision

        except Exception as e:
            logger.error(f"[Security] Yetkilendirme hatası (FAIL-CLOSED devrede): {e}")
            # FAIL CLOSED: Hata varsa daima REDDET
            fallback = AuthorizationDecision(
                allowed=False,
                risk_level=RiskLevel.CRITICAL,
                requires_user_confirmation=False,
                reason=f"Yetkilendirme motorunda iç hata oluştu (Fail-Closed): {e}",
                warning_message="🚨 GÜVENLİK MOTORU HATASI — İŞLEM ENGELLENDİ",
                audit_id=audit_id
            )
            self._write_audit(req, fallback)
            return fallback

    def _write_audit(self, req: AuthorizationRequest, dec: AuthorizationDecision) -> None:
        """Güvenlik günlüğünü diske yapılandırılmış JSONL formatında yazar."""
        try:
            AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "audit_id": dec.audit_id,
                "timestamp": req.timestamp,
                "actor": req.actor,
                "is_authenticated": req.is_authenticated,
                "action": req.action_name,
                "target": req.target,
                "params": req.params,
                "risk_level": dec.risk_level.value,
                "allowed": dec.allowed,
                "requires_confirmation": dec.requires_user_confirmation,
                "reason": dec.reason
            }
            with open(AUDIT_LOG_FILE, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.error(f"Audit log yazma hatası: {e}")


# Global Security Engine Singleton
security_engine = CentralSecurityEngine()
