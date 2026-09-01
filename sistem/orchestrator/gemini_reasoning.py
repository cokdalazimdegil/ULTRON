"""
ULTRON Orchestrator — Gemini & OpenClaw Hybrid Reasoning Engine
"""

from __future__ import annotations

import base64
import logging
import os
import time
import asyncio
from typing import Any, List, Optional

from google import genai
from google.genai import errors, types
from google.antigravity import Agent, LocalAgentConfig, CapabilitiesConfig

from app_config import get_app_config_value

logger = logging.getLogger("ultron.orchestrator.gemini_reasoning")

PRO_MODELS = ("gemini-3.6-flash",)
FLASH_MODELS = ("gemini-3.6-flash",)

def _get_api_key() -> str:
    key = str(get_app_config_value("gemini_api_key", "") or "").strip()
    if not key:
        logger.warning("gemini_api_key eksik, reasoning basarisiz olabilir.")
    return key

def _extract_text(response: Any) -> str:
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

async def _run_antigravity_agent(prompt: str, sys_prompt: str) -> str:
    """OpenClaw (Antigravity) motoru uzerinden agentic reasoning calistirir."""
    api_key = _get_api_key()
    if api_key:
        os.environ["GEMINI_API_KEY"] = api_key
    
    config = LocalAgentConfig(
        system_instructions=sys_prompt or "You are ULTRON core reasoning engine.",
        capabilities=CapabilitiesConfig(enable_write_tools=True)
    )
    
    async with Agent(config) as agent:
        response = await agent.chat(prompt)
        text = await response.text()
        return text

def query_gemini_reasoning(
    prompt: str,
    system_instruction: str = "",
    model_tier: str = "pro",
    temperature: float = 0.7,
    image_bytes: Optional[bytes] = None,
    image_mime: str = "image/jpeg"
) -> str:
    # Eger gorsel analiz yoksa ve OpenClaw ajan yonetimi cagirildiysa, yeni motoru dene.
    if not image_bytes:
        try:
            # Yeni bir olay dongusu (event loop) icinde Antigravity agent'i cagir
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(_run_antigravity_agent(prompt, system_instruction))
            loop.close()
            return result
        except Exception as e:
            logger.warning(f"OpenClaw (Antigravity) motoru basarisiz oldu, fallback devrede: {e}")

    # Fallback: Mevcut saf Gemini REST orkestrasyonu (Resim destekli)
    api_key = _get_api_key()
    if not api_key:
        return ""

    contents = [types.Part.from_text(text=prompt)]
    if image_bytes:
        contents.insert(
            0,
            types.Part.from_bytes(data=image_bytes, mime_type=image_mime)
        )

    client = genai.Client(api_key=api_key)
    models_to_try = PRO_MODELS if model_tier.lower() == "pro" else FLASH_MODELS
    retry_delays = (1.0, 2.0)

    config = types.GenerateContentConfig(
        temperature=temperature,
        system_instruction=system_instruction if system_instruction else None,
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
                    logger.info(f"Gemini reasoning basarili [{model_name}]")
                    return extracted
            except Exception as e:
                logger.debug(f"Reasoning hatasi ({model_name}, Deneme {attempt}): {e}")
                time.sleep(delay)

    logger.warning("Tum reasoning modelleri basarisiz oldu veya bos yanit dondu.")
    return ""
