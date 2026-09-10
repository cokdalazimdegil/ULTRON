"""
ULTRON Permission & Security Layer 2.0 (Central Policy Engine)
═════════════════════════════════════════════════════════════
• 4 Seviyeli Risk Değerlendirmesi (LOW, MEDIUM, HIGH, CRITICAL)
• Whitelist & Kategori Tabanlı Shell Politika Matrisi
• Prompt Injection & Untrusted Content İzolasyonu
• Merkezi Yetkilendirme Hattı:
  REQUEST -> IDENTITY -> UNTRUSTED_CHECK -> ACTION_CLASSIFICATION -> RISK_ASSESSMENT -> PERMISSION -> AUDIT_LOG
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

UNTRUSTED_TAG_START = "<UNTRUSTED_EXTERNAL_CONTENT>"
UNTRUSTED_TAG_END = "</UNTRUSTED_EXTERNAL_CONTENT>"


def wrap_untrusted_content(text: str, source: str = "external") -> str:
    """
    Web sayfası, gelen e-posta veya harici dosya içeriklerini
    prompt injection saldırılarına karşı 'untrusted' etiketiyle sarmalar.
    """
    clean_text = str(text or "").replace(UNTRUSTED_TAG_START, "").replace(UNTRUSTED_TAG_END, "")
    return f"{UNTRUSTED_TAG_START} [Source: {source}]\n{clean_text}\n{UNTRUSTED_TAG_END}"


def is_untrusted_content(text: str) -> bool:
    """Metnin harici kaynaktan gelen güvenilmeyen içerik olup olmadığını belirler."""
    return UNTRUSTED_TAG_START in str(text or "")


class RiskLevel(str, Enum):
    LOW      = "LOW"       # Bilgi okuma, ekran yakalama, sistem bilgisi, güvenli komutlar
    MEDIUM   = "MEDIUM"    # Uygulama açma, tarayıcıda gezinme, kullanıcı dosya yazımı
    HIGH     = "HIGH"      # Paket kurma, mesaj/e-posta gönderme, kod değiştirme
    CRITICAL = "CRITICAL"  # Format, sistem kapatma, kritik silme, prompt injection, kayıt defteri


@dataclass
class AuthorizationRequest:
    action_name: str
    target: str = ""
    actor: str = "YARATICI"
    is_authenticated: bool = True
    is_untrusted_input: bool = False
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
    """Merkezi Güvenlik, İzin ve Politika Yönetim Motoru."""

    # ── 1. GÜVENLİ SHELL WHITELIST (LOW Risk — Bilgi Alma / Durum Sorgulama) ───
    SHELL_WHITELIST_PATTERNS = [
        r"^\s*(dir|ls)(\s+.*)?$",
        r"^\s*(cd|pwd)(\s+.*)?$",
        r"^\s*echo\b.*$",
        r"^\s*(type|cat|head|tail|Get-Content)\b.*$",
        r"^\s*(grep|findstr|Select-String)\b.*$",
        r"^\s*(where|which|Get-Command)\b.*$",
        r"^\s*git\s+(status|log|diff|branch|remote|show)(\s+.*)?$",
        r"^\s*(python|python3|py)\s+(--version|-V)\s*$",
        r"^\s*(node|npm)\s+(-v|--version)\s*$",
        r"^\s*(whoami|hostname|ipconfig|ifconfig|uptime)\b.*$",
        r"^\s*(ping|tracert|traceroute)\s+[a-zA-Z0-9\.-]+\s*$",
        r"^\s*netstat(\s+.*)?$",
        r"^\s*(date|time|ver|systeminfo)\b.*$",
    ]

    # ── 2. DAİMA AÇIK ONAY GEREKTİREN KRİTİK EYLEMLER (CRITICAL — Fail-Closed) ──
    CRITICAL_PATTERNS = [
        # Disk ve Bölüm Formatlama/Silme
        r"\bformat\s+[a-zA-Z]:",
        r"\b(diskpart|vssadmin|bspadmin|fdisk|mkfs|regedit)\b",
        r"\bdd\s+if=",
        r":\(\)\s*\{\s*:\|:&\s*\};\s*:",  # Forkbomb
        # Sistem Kapatma / Yeniden Başlatma
        r"\b(shutdown\s+[/|-][s|r]|init\s+0|reboot|restart-computer|stop-computer)\b",
        # Kayıt Defteri
        r"\breg\s+(delete|add)\b",
        # Toplu ve Kök Dizin Silme
        r"\b(rmdir|rd)\s+[/|-][s|q]",
        r"\b(del|erase)\s+[/|-][f|s|q]",
        r"\b(del|erase)\b.*[a-zA-Z]:\\windows",
        r"\b(rmdir|rd)\b.*[a-zA-Z]:\\",
        r"\brm\s+-rf\b",
        # Çekirdek Süreçleri Öldürme
        r"\btaskkill\b.*(/f|/t).*(\blsass|\bcsrss|\bwinlogon|\bsvchost|\bexplorer)",
        r"\bkill\s+-9\s+1\b",
        # Veritabanı Yıkımı
        r"\b(drop\s+database|drop\s+table|truncate\s+table)\b",
        # Güvenlik Politikalarını Düşürme
        r"\b(set-executionpolicy\s+unrestricted|chmod\s+777)\b",
    ]

    # ── 3. DENETİMLİ YÜKSEK RİSKLİ EYLEMLER (HIGH Risk — Audit Log + İzin) ───
    HIGH_RISK_PATTERNS = [
        r"\b(pip\s+install|npm\s+install|cargo\s+install|winget\s+install|brew\s+install)\b",
        r"\b(taskkill|kill\s+-9|stop-process)\b",
        r"\b(git\s+reset\s+--hard|git\s+clean\s+-fd|git\s+push\s+--force)\b",
        r"\b(set-executionpolicy|chmod\s+[0-7]+)\b",
        r"\b(del|rm|erase)\b",
    ]

    # Kritik Sistem Klasörleri (Dosya Araçları Koruması)
    CRITICAL_SYSTEM_DIRS = [
        r"^[a-zA-Z]:\\windows",
        r"^[a-zA-Z]:\\program files",
        r"^/etc",
        r"^/usr",
        r"^/bin",
        r"^/sbin",
        r"^/System",
        r"/\.git(/.*)?$",
        r"\\\.git(\\.*)?$",
    ]

    def __init__(self):
        self._lock = threading.RLock()
        self._emergency_stop = False

    def trigger_emergency_stop(self) -> None:
        """Sistemi acil durdurma moduna alır (Tüm aksiyonlar derhal kilitlenir)."""
        with self._lock:
            self._emergency_stop = True
            logger.critical("[Security] 🚨 ACİL DURDURMA TETİKLENDİ! Tüm işlemler kilitlendi.")

    def reset_emergency_stop(self) -> None:
        """Acil durdurma kilidini sıfırlar."""
        with self._lock:
            self._emergency_stop = False
            logger.info("[Security] Acil durdurma kilidi sıfırlandı.")

    def is_emergency_stopped(self) -> bool:
        with self._lock:
            return self._emergency_stop

    def evaluate_risk(self, action_name: str, target: str = "", params: dict[str, Any] | None = None,
                      is_untrusted: bool = False) -> tuple[RiskLevel, str]:
        """
        Bir eylemin ve parametrelerinin risk seviyesini ve gerekçesini hesaplar.
        Returns: (RiskLevel, reason)
        """
        action = action_name.lower().strip()
        target_str = str(target or "").lower().strip()
        params = params or {}
        param_str = json.dumps(params, ensure_ascii=False).lower()
        combined = f"{action} {target_str} {param_str}"

        # 1. Prompt Injection / Untrusted Content Koruması
        if is_untrusted or params.get("is_untrusted") or is_untrusted_content(combined):
            if any(w in action for w in ("shell", "terminal", "exec", "file", "write", "delete", "whatsapp", "email", "win_control", "system")):
                return (
                    RiskLevel.CRITICAL,
                    "Prompt Injection Koruması: Güvenilmeyen harici içerikten kaynaklanan sistem/aksiyon komutları engellendi."
                )

        # 2. Kritik Seviye Kontrolü (Her zaman açık onay)
        for pat in self.CRITICAL_PATTERNS:
            if re.search(pat, combined):
                return (
                    RiskLevel.CRITICAL,
                    f"Kritik yıkıcı desen tespit edildi ({pat}). Bu işlem açık kullanıcı onayı gerektirir."
                )

        # 3. Aksiyon Türüne Göre Politika Matrisi
        # ── SHELL / TERMİNAL EYLEMLERİ ──
        if action in ("shell_run", "terminal", "shell", "execute_command", "run_terminal", "exec"):
            # A) Whitelist kontrolü (Güvenli komutlar -> LOW)
            for white_pat in self.SHELL_WHITELIST_PATTERNS:
                if re.search(white_pat, target_str, re.IGNORECASE):
                    return (RiskLevel.LOW, "Whitelist kapsamında güvenli okuma/tanı komutu.")

            # B) Yüksek riskli komutlar
            for high_pat in self.HIGH_RISK_PATTERNS:
                if re.search(high_pat, target_str, re.IGNORECASE):
                    return (RiskLevel.HIGH, f"Yüksek riskli sistem/paket/silme komutu: {target_str[:50]}")

            # C) Whitelist dışındaki genel komutlar varsayılan HIGH
            return (RiskLevel.HIGH, f"Whitelist dışı shell komutu yürütme: {target_str[:50]}")

        # ── DOSYA EYLEMLERİ (file_tools) ──
        if "file" in action or action == "file_tools":
            sub_act = str(params.get("action", "")).lower()
            # Kritik sistem yolu kontrolü
            norm_target = os.path.normpath(target_str)
            for sys_dir in self.CRITICAL_SYSTEM_DIRS:
                if re.search(sys_dir, norm_target, re.IGNORECASE):
                    if sub_act in ("write", "yaz", "create", "delete", "sil", "append", "ekle"):
                        return (RiskLevel.CRITICAL, f"Kritik sistem dizininde ({norm_target}) değişiklik yapılamaz.")

            if sub_act in ("delete", "sil"):
                return (RiskLevel.HIGH, f"Dosya silme işlemi: {target_str}")
            elif sub_act in ("write", "yaz", "create", "append", "ekle"):
                return (RiskLevel.MEDIUM, f"Dosya oluşturma/yazma işlemi: {target_str}")
            else:
                return (RiskLevel.LOW, f"Güvenli dosya okuma/listeleme/arama: {target_str}")

        # ── WHATSAPP EYLEMLERİ ──
        if "whatsapp" in action:
            if params.get("send_now", False):
                return (RiskLevel.HIGH, f"WhatsApp üzerinden otomatik mesaj gönderimi (Hedef: {target_str})")
            return (RiskLevel.LOW, f"WhatsApp taslağı oluşturma (Hedef: {target_str})")

        # ── E-POSTA GÖNDERME EYLEMLERİ ──
        if "email" in action or action in ("send_email", "email_send"):
            return (RiskLevel.HIGH, f"E-posta gönderimi (Alıcı: {target_str})")

        # ── DONANIM & SİSTEM KONTROLLERİ (win_controls) ──
        if "win_control" in action or action in ("control_system", "system_control"):
            sub_act = target_str or str(params.get("action", "")).lower()
            if sub_act in ("shutdown", "kapat", "reboot", "restart"):
                return (RiskLevel.CRITICAL, "Sistem kapatma veya yeniden başlatma işlemi.")
            elif sub_act in ("lock", "lock_screen", "kilitle", "sleep", "uyut"):
                return (RiskLevel.MEDIUM, f"Sistem kilit/uyku eylemi: {sub_act}")
            return (RiskLevel.LOW, f"Sistem ses/parlaklık ayarı: {sub_act}")

        # ── TARAYICI EYLEMLERİ (browser) ──
        if "browser" in action or action in ("browser_control", "browser_open"):
            if target_str.startswith(("javascript:", "data:", "vbscript:")):
                return (RiskLevel.CRITICAL, f"Şüpheli tarayıcı URL şeması engellendi: {target_str[:30]}")
            return (RiskLevel.LOW, f"Tarayıcıda sayfa açma/arama: {target_str[:50]}")

        # Bilinmeyen genel eylemler
        return (RiskLevel.LOW, f"Standart bilgi veya sorgu eylemi: {action}")

    def authorize(self, req_or_action: AuthorizationRequest | str, params: dict[str, Any] | None = None,
                  target: str = "", user: str = "YARATICI", is_authenticated: bool = True,
                  is_untrusted: bool = False) -> AuthorizationDecision:
        """
        Merkezi yetkilendirme kararı üretir.
        FAIL-CLOSED Kuralı: İstisna veya belirsizlik durumunda ASLA izin vermez.
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
                is_untrusted_input=is_untrusted or (params.get("is_untrusted", False) if params else False),
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
            risk, reason = self.evaluate_risk(
                req.action_name,
                req.target,
                req.params,
                is_untrusted=req.is_untrusted_input
            )

            # 3. Kimlik & Yetki Kontrolü
            if not req.is_authenticated or req.actor.lower() in ("bilinmeyen", "unknown"):
                if risk in (RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL) or any(
                    w in req.action_name for w in ("click", "type", "mouse", "keyboard", "exec", "open", "shell", "file", "send")
                ):
                    decision = AuthorizationDecision(
                        allowed=False,
                        risk_level=risk,
                        requires_user_confirmation=False,
                        reason="Yetkisiz veya tanınmayan aktör riskli işlem yürütemez.",
                        warning_message="🔒 YETKİSİZ İŞLEM REDDEDİLDİ",
                        audit_id=audit_id
                    )
                    self._write_audit(req, decision)
                    return decision

            # 4. Risk Seviyesine Göre Karar
            if risk == RiskLevel.CRITICAL:
                decision = AuthorizationDecision(
                    allowed=False,  # Kritik işlemler varsayılan olarak durdurulur ve açık onay bekler
                    risk_level=risk,
                    requires_user_confirmation=True,
                    reason=reason,
                    warning_message=f"⚠️ DİKKAT: Kritik risk tespit edildi. Onayınız gerekiyor.",
                    audit_id=audit_id
                )
            elif risk == RiskLevel.HIGH:
                decision = AuthorizationDecision(
                    allowed=True,   # HIGH dönerse audit log'a yaz ve devam et
                    risk_level=risk,
                    requires_user_confirmation=False,
                    reason=reason,
                    warning_message="⚡ Yüksek riskli işlem audit log'a kaydedilerek yürütülüyor.",
                    audit_id=audit_id
                )
            else:
                decision = AuthorizationDecision(
                    allowed=True,
                    risk_level=risk,
                    requires_user_confirmation=False,
                    reason=reason,
                    audit_id=audit_id
                )

            self._write_audit(req, decision)
            return decision

        except Exception as e:
            logger.error(f"[Security] Yetkilendirme motoru hatası (FAIL-CLOSED devrede): {e}")
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
        """Güvenlik denetim günlüğünü diske yapılandırılmış JSONL formatında yazar."""
        try:
            AUDIT_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
            record = {
                "audit_id": dec.audit_id,
                "timestamp": req.timestamp,
                "actor": req.actor,
                "is_authenticated": req.is_authenticated,
                "is_untrusted": req.is_untrusted_input,
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
