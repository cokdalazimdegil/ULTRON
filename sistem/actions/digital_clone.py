"""
ULTRON Digital Clone — Kullanıcı Stilini Taklit Eden Yanıt Taslak Motoru
─────────────────────────────────────────────────────────────────────────
• learned_stylometry.json dosyasındaki yazım tarzı verisini kullanır.
• Gelen mesajlara kullanıcının tarzıyla yanıt TASLAĞI üretir (göndermez!).
• Taslak EventBus üzerinden UI'ya iletilir; kullanıcı onaylayana kadar bekler.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ultron.actions.digital_clone")


def _load_stylometry() -> dict:
    """learned_stylometry.json verisini yükler."""
    try:
        from app_paths import data_path
        path = data_path("memory", "learned_stylometry.json")
    except Exception:
        path = Path(__file__).parent.parent / "memory" / "learned_stylometry.json"

    try:
        if Path(str(path)).exists():
            return json.loads(Path(str(path)).read_text(encoding="utf-8"))
    except Exception as exc:
        logger.debug(f"[DigitalClone] Stilometri yüklenemedi: {exc}")
    return {}


def _stylometry_to_prompt(style: dict) -> str:
    """Stilometri verisini Gemini prompt'una dönüştürür."""
    if not style:
        return "Kısa ve samimi bir Türkçe yanıt ver."

    lines = ["Kullanıcının yazım tarzı özellikleri:"]
    for k, v in style.items():
        if isinstance(v, (str, int, float, bool)):
            lines.append(f"  - {k}: {v}")
        elif isinstance(v, list) and v:
            lines.append(f"  - {k}: {', '.join(str(x) for x in v[:5])}")
    return "\n".join(lines)


def generate_clone_reply(
    original_message: str,
    platform: str = "genel",
    sender_name: str = "Biri",
) -> dict:
    """
    Kullanıcının yazım tarzıyla bir yanıt taslağı üretir.

    Returns:
        dict: {
            "draft": str,          # taslak yanıt metni
            "platform": str,
            "original_message": str,
            "sender": str,
            "requires_approval": True  # her zaman onay gerekli
        }
    """
    style = _load_stylometry()
    style_prompt = _stylometry_to_prompt(style)

    try:
        from orchestrator.gemini_reasoning import query_gemini_reasoning

        prompt = f"""
Sen ULTRON'sun. Kullanıcı YARATICI şu anda meşgul.
{sender_name} adlı kişi {platform} üzerinden şu mesajı gönderdi:

"{original_message}"

{style_prompt}

Görevin: YARATICI'ın YAZIM TARZIYLA (aynı kısaltmalar, aynı enerji, aynı Türkçe/İngilizce karışım oranı) bu mesaja kısa ve doğal bir yanıt taslağı yaz.
- Sadece taslak yanıtı yaz, açıklama veya giriş/çıkış cümlesi EKLEME.
- Taslak 1-3 cümleyi geçmesin.
- Yanıt samimi ve özgün olsun, robot gibi değil.
""".strip()

        draft = query_gemini_reasoning(prompt)
        if not draft:
            draft = "Mesajını aldım, birazdan döneceğim."

        return {
            "draft": draft.strip(),
            "platform": platform,
            "original_message": original_message,
            "sender": sender_name,
            "requires_approval": True,
        }

    except Exception as exc:
        logger.error(f"[DigitalClone] Taslak üretim hatası: {exc}")
        return {
            "draft": "Şu an meşgulüm, daha sonra yazarım.",
            "platform": platform,
            "original_message": original_message,
            "sender": sender_name,
            "requires_approval": True,
        }


def notify_pending_reply(draft_result: dict) -> str:
    """
    Taslağı EventBus üzerinden UI'ya bildirir ve kullanıcıdan onay ister.
    Asla otomatik göndermez.
    """
    from core.event_bus import bus

    sender = draft_result.get("sender", "Biri")
    platform = draft_result.get("platform", "")
    draft = draft_result.get("draft", "")
    original = draft_result.get("original_message", "")

    alert_text = (
        f"📨 [{platform.upper()}] {sender} yazdı: \"{original[:80]}...\"\n"
        f"💬 Taslak Yanıt: \"{draft}\"\n"
        f"✅ Onaylamak için 'yanıtı gönder' deyin."
    )
    bus.publish("ui_alert", alert_text)

    return (
        f"Taslak yanıt hazırlandı. Kullanıcı arayüzünde onay bekleniyor.\n"
        f"Taslak: \"{draft}\""
    )
