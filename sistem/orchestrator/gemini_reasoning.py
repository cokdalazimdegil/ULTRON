"""
ULTRON Orchestrator — Gemini 2.5 Pro Hybrid Reasoning Engine
─────────────────────────────────────────────────────────────
• Coding Agent, Reviewer Agent ve Supervisor için derin mantık ve kod üretim motoru
• Pro Tier (gemini-2.5-pro) ve Flash Tier (gemini-2.5-flash) dinamik yönlendirmesi
• Otomatik kota/hata yönetimi ve kesintisiz fallback mekanizması
"""

from __future__ import annotations

import base64
import logging
import os
import time
from typing import Any, List, Optional

from google import genai
from google.genai import errors, types

from app_config import get_app_config_value

logger = logging.getLogger("ultron.orchestrator.gemini_reasoning")

PRO_MODELS = (
    "gemini-3.6-flash",
)

FLASH_MODELS = (
    "gemini-3.6-flash",
)


def _get_api_key() -> str:
    """Gemini API anahtarını config veya ortam değişkenlerinden okur."""
    key = str(get_app_config_value("gemini_api_key", "") or "").strip()
    if not key:
        key = str(os.environ.get("GEMINI_API_KEY", "") or "").strip()
    return key


def _extract_text(response: Any) -> str:
    """Gemini yanıtından metin içeriğini temiz şekilde ayıklar."""
    if not response:
        return ""
    text = str(getattr(response, "text", "") or "").strip()
    if text:
        return text

    candidates = getattr(response, "candidates", None) or []
    chunks: List[str] = []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            part_text = str(getattr(part, "text", "") or "").strip()
            if part_text:
                chunks.append(part_text)
    return "\n".join(chunk for chunk in chunks if chunk).strip()


def query_gemini_reasoning(
    prompt: str,
    system_instruction: str = "",
    model_tier: str = "pro",
    temperature: float = 0.2,
    max_output_tokens: Optional[int] = None,
    image_base64: Optional[str] = None,
    image_mime: str = "image/jpeg",
) -> str:
    """
    Belirtilen prompt için Gemini Pro veya Flash akıl yürütme motorunu çağırır.
    
    Args:
        prompt: Modele gönderilecek ana girdi/istek.
        system_instruction: Sistem talimatı / uzman ajan rolü.
        model_tier: 'pro' (gemini-2.5-pro öncelikli) veya 'flash'.
        temperature: Üretim sıcaklığı (kod/mantık için düşük tutulur: 0.2).
        max_output_tokens: Maksimum çıktı token sayısı.
        image_base64: Opsiyonel base64 formatında görsel verisi.
        image_mime: Görselin MIME tipi (örn: image/jpeg).
        
    Returns:
        Üretilen yanıt metni.
    """
    api_key = _get_api_key()
    if not api_key:
        logger.warning("Gemini API anahtari bulunamadi.")
        return ""

    client = genai.Client(api_key=api_key)
    models_to_try = PRO_MODELS if model_tier.lower() == "pro" else FLASH_MODELS
    retry_delays = (1.0, 2.0)

    config_kwargs: dict[str, Any] = {
        "temperature": temperature,
    }
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction
    if max_output_tokens:
        config_kwargs["max_output_tokens"] = max_output_tokens

    config = types.GenerateContentConfig(**config_kwargs)

    contents: list[Any] = [prompt]
    if image_base64:
        image_bytes = base64.b64decode(image_base64)
        contents.append(
            types.Part.from_bytes(data=image_bytes, mime_type=image_mime)
        )

    for model_name in models_to_try:
        for attempt, delay in enumerate(retry_delays, start=1):
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=contents,
                    config=config,
                )
                extracted = _extract_text(response)
                if extracted:
                    logger.info(f"Gemini reasoning basarili [{model_name}] ({len(extracted)} karakter)")
                    return extracted
            except Exception as e:
                logger.debug(f"Gemini reasoning denemesi basarisiz ({model_name}, Deneme {attempt}): {e}")
                time.sleep(delay)

    logger.warning("Tum Gemini reasoning modelleri basarisiz oldu veya bos yanit dondu.")
    return ""
