"""
ULTRON Email Scorer — Akıllı E-Posta Önem ve Öncelik Skorlama
═════════════════════════════════════════════════════════════
Gelen e-postaların aciliyet, önem ve aksiyon gereklilik durumunu
kural tabanlı filtreler ve opsiyonel LLM desteğiyle skorlar.

Skor Skalası (0 - 100):
    80 - 100: CRITICAL / HIGH (Doğrulama kodları, banka/finans, acil yöneticiler)
    60 - 79:  NORMAL (Toplantı davetleri, teslimatlar, rezervasyonlar)
    0  - 59:  LOW (Bültenler, pazarlama, otomatik bildirimler)
"""

from __future__ import annotations

import logging
import re
from typing import Any, Dict, Optional, Tuple

from core.events import UltronEvent, EventPriority, EventSource

logger = logging.getLogger("ultron.core.email_scorer")

# ── Kural Tabanlı Kalıplar ve Ağırlıkları ──────────────────────────────────

SECURITY_PATTERNS = [
    r"(doğrulama|dogrulama|onay kodu|otp|verification code|security code|passcode|tek kullanımlık şifre)",
    r"(güvenlik uyarısı|şüpheli giriş|hesabınıza giriş yapıldı|parola sıfırlama|password reset)",
]

FINANCIAL_PATTERNS = [
    r"(fatura|dekont|ödeme alındı|ödeme onay|tahsilat|ekstre|hesap özeti)",
    r"(para transferi|havale|eft|iban|kredi kartı borcu|harcama bildirimi)",
]

URGENT_PATTERNS = [
    r"(acil|urgent|critical|önemli|asap|deadline|son gün|son gun)",
    r"(aksiyon gerekiyor|action required|lütfen onaylayın|onayınızı bekliyor)",
]

MEETING_PATTERNS = [
    r"(toplantı daveti|görüşme daveti|meeting invitation|mülakat|interview)",
    r"(zoom\.us|teams\.microsoft\.com|meet\.google\.com)",
]

SHIPPING_PATTERNS = [
    r"(kargonuz yola çıktı|teslim edildi|siparişiniz onaylandı|kargo takip)",
]

LOW_PRIORITY_PATTERNS = [
    r"(unsubscribe|bültenden ayrıl|abonelikten çık|reklam|kampanya|indirim)",
    r"(no-reply|noreply|donotreply)",
]


def score_email_rule_based(
    subject: str,
    sender: str,
    body: str = "",
) -> Dict[str, Any]:
    """
    Hızlı kural tabanlı e-posta önem skorlama.
    Milisaniyeler içinde tamamlanır, harici API bağımlılığı yoktur.
    """
    combined = f"{subject} {sender} {body}".lower()
    subj_lower = subject.lower()

    # 1. Düşük öncelik kontrolü (Bülten / reklam)
    for pat in LOW_PRIORITY_PATTERNS:
        if re.search(pat, combined):
            # Eğer başlıkta doğrulama veya finans yoksa doğrudan düşük puan
            is_sec = any(re.search(p, subj_lower) for p in SECURITY_PATTERNS)
            if not is_sec:
                return {
                    "is_important": False,
                    "score": 15,
                    "category": "marketing",
                    "reason": "Otomatik bülten veya reklam e-postası",
                    "priority": EventPriority.LOW,
                }

    # 2. Güvenlik / OTP (En yüksek öncelik)
    for pat in SECURITY_PATTERNS:
        if re.search(pat, combined):
            return {
                "is_important": True,
                "score": 95,
                "category": "security",
                "reason": "Güvenlik / Doğrulama Kodu",
                "priority": EventPriority.CRITICAL,
            }

    # 3. Acil / Deadline
    for pat in URGENT_PATTERNS:
        if re.search(pat, combined):
            return {
                "is_important": True,
                "score": 85,
                "category": "urgent",
                "reason": "Yüksek Öncelik / Acil Bildirim",
                "priority": EventPriority.HIGH,
            }

    # 4. Finans / Banka / Fatura
    for pat in FINANCIAL_PATTERNS:
        if re.search(pat, combined):
            return {
                "is_important": True,
                "score": 80,
                "category": "financial",
                "reason": "Finans / Fatura / Banka İşlemi",
                "priority": EventPriority.HIGH,
            }

    # 5. Toplantı / Mülakat
    for pat in MEETING_PATTERNS:
        if re.search(pat, combined):
            return {
                "is_important": True,
                "score": 70,
                "category": "meeting",
                "reason": "Toplantı veya Görüşme Daveti",
                "priority": EventPriority.NORMAL,
            }

    # 6. Kargo / Sipariş
    for pat in SHIPPING_PATTERNS:
        if re.search(pat, combined):
            return {
                "is_important": False,
                "score": 50,
                "category": "shipping",
                "reason": "Sipariş / Kargo Takibi",
                "priority": EventPriority.NORMAL,
            }

    # 7. Normal e-posta
    return {
        "is_important": False,
        "score": 40,
        "category": "general",
        "reason": "Standart E-Posta",
        "priority": EventPriority.LOW,
    }


def score_email_with_llm(
    subject: str,
    sender: str,
    body: str = "",
) -> Optional[Dict[str, Any]]:
    """
    LLM (Gemini) tabanlı gelişmiş önem skorlama.
    Belirsiz durumlarda veya üst seviye analiz istendiğinde çağrılır.
    """
    try:
        from core.ai_provider import ai_provider_manager
        prompt = (
            f"Aşağıdaki e-postayı analiz et ve önem derecesini belirle.\n"
            f"Gönderen: {sender}\n"
            f"Konu: {subject}\n"
            f"İçerik: {body[:500]}\n\n"
            f"Yanıtı SADECE JSON formatında ver:\n"
            f"{{\"score\": 0-100, \"category\": \"security|financial|urgent|meeting|general\", \"reason\": \"kısa açıklama\"}}"
        )
        resp = ai_provider_manager.complete(prompt=prompt, system_instruction="Sen bir e-posta sınıflandırma asistanısın.")
        if resp and resp.text:
            import json
            # JSON bloğu ayıkla
            match = re.search(r"\{.*\}", resp.text, re.DOTALL)
            if match:
                data = json.loads(match.group(0))
                score = int(data.get("score", 50))
                priority = EventPriority.LOW
                if score >= 85:
                    priority = EventPriority.CRITICAL
                elif score >= 70:
                    priority = EventPriority.HIGH
                elif score >= 50:
                    priority = EventPriority.NORMAL

                return {
                    "is_important": score >= 70,
                    "score": score,
                    "category": data.get("category", "general"),
                    "reason": data.get("reason", "LLM Analizi"),
                    "priority": priority,
                }
    except Exception as e:
        logger.debug(f"[EmailScorer] LLM skorlama hatası (fallback kullanılacak): {e}")

    return None


def score_email(
    subject: str,
    sender: str,
    body: str = "",
    use_llm: bool = False,
) -> Dict[str, Any]:
    """
    Ana skorlama fonksiyonu.
    use_llm=True ise kural tabanlı sonuç belirsiz (45-65 aralığı) kaldığında LLM'e danışır.
    """
    result = score_email_rule_based(subject, sender, body)

    if use_llm and 45 <= result["score"] <= 65:
        llm_result = score_email_with_llm(subject, sender, body)
        if llm_result:
            return llm_result

    return result


def create_email_event(email_data: Dict[str, Any]) -> UltronEvent:
    """E-posta verisini standart UltronEvent nesnesine dönüştürür."""
    subject = email_data.get("subject", "")
    sender = email_data.get("sender", "")
    body = email_data.get("body_preview", "") or email_data.get("full_body", "")

    scoring = score_email(subject, sender, body)
    event_type = "email.important" if scoring["is_important"] else "email.received"

    return UltronEvent(
        event_type=event_type,
        source=EventSource.EMAIL,
        payload={
            "id": email_data.get("id", ""),
            "subject": subject,
            "sender": sender,
            "date": email_data.get("date", ""),
            "body_preview": body[:200],
            "score": scoring["score"],
            "category": scoring["category"],
            "reason": scoring["reason"],
            "is_important": scoring["is_important"],
        },
        priority=scoring["priority"],
    )
