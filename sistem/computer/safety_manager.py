"""
ULTRON Computer Awareness — Safety & Permission Manager
───────────────────────────────────────────────────────
• Risk sınıflandırma (LOW, MEDIUM, HIGH)
• Geri dönüşü olmayan veya tehlikeli işlemlerde kullanıcı onayı talep etme
• Acil Durum Durdurma (Emergency Stop) yönetimi
"""

from __future__ import annotations

import logging
import re
import threading
from typing import Any

logger = logging.getLogger("ultron.computer.safety_manager")

# Yüksek riskli komut ve kelime desenleri
HIGH_RISK_PATTERNS = [
    r"\b(rm|del|erase|remove)\s+(-[rf]|/s|/q)?\s*([a-z]:\\|/|\*)",
    r"\b(format|diskpart|fdisk)\b",
    r"\b(reg\s+(delete|add)|regedit)\b",
    r"\b(shutdown|reboot|restart-computer)\b",
    r"\b(net\s+user|net\s+localgroup)\b",
    r"\b(rmdir|rd)\s+/[sq]",
    r"\bdrop\s+database\b",
    r"\b(delete|sil)\b.*\b(tüm|her|hepsini|c:\\|sistem)\b"
]

_emergency_stop_event = threading.Event()


class SafetyManager:
    """İşlem güvenliği ve izin onay denetleyicisi."""

    @staticmethod
    def is_emergency_stopped() -> bool:
        return _emergency_stop_event.is_set()

    @staticmethod
    def trigger_emergency_stop() -> str:
        _emergency_stop_event.set()
        logger.warning("🚨 ACİL DURUM DURDURMA TETİKLENDİ! Tüm aktif görevler durduruluyor.")
        return "🚨 Acil Durum Durdurma devreye alındı. Devam eden tüm işlemler ve otomasyonlar derhal durduruldu."

    @staticmethod
    def reset_emergency_stop() -> None:
        _emergency_stop_event.clear()

    @staticmethod
    def evaluate_risk(action: str, target: str = "") -> dict[str, Any]:
        """
        Bir eylemin risk seviyesini ve onay gerekip gerekmediğini değerlendirir.
        Dönen: {"risk": "LOW"|"MEDIUM"|"HIGH", "requires_confirmation": bool, "warning": str}
        """
        act = action.lower().strip()
        tgt = target.lower().strip()
        combined = f"{act} {tgt}"

        # 1. Yüksek Risk Kontrolleri
        for pattern in HIGH_RISK_PATTERNS:
            if re.search(pattern, combined):
                return {
                    "risk": "HIGH",
                    "requires_confirmation": True,
                    "warning": (
                        f"⚠️ YÜKSEK RİSKLİ İŞLEM TESPİT EDİLDİ: '{action} {target}'. "
                        "Bu işlem geri dönüşü olmayan veri kaybına veya sistem değişikliğine yol açabilir. "
                        "Gerçekleştirmek için açıkça onay vermeniz gerekir."
                    )
                }

        # 2. Orta Risk Kontrolleri (Dosya yazma, uygulama kapatma, pano ezme)
        if any(w in act for w in ("delete_file", "dosya_sil", "kill_process", "close_app", "write_file")):
            if "sil" in act or "delete" in act:
                return {
                    "risk": "HIGH",
                    "requires_confirmation": True,
                    "warning": f"⚠️ '{target}' dosyasını kalıcı olarak silmek üzeresiniz. Devam edilsin mi?"
                }
            return {
                "risk": "MEDIUM",
                "requires_confirmation": False,
                "warning": ""
            }

        # 3. Düşük Risk (Okuma, ekran analizi, uygulama açma, arama, fare/klavye)
        return {
            "risk": "LOW",
            "requires_confirmation": False,
            "warning": ""
        }
