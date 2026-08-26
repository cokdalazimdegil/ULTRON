"""
ULTRON AI Provider & Offline Resilience Architecture (V17)
══════════════════════════════════════════════════════════
• Çoklu Model ve Sağlayıcı Arayüzü (AIProvider Abstraction)
• GeminiProvider, LocalProvider ve FallbackProvider Desteği
• Merkezi Zaman Aşımı, Yeniden Deneme ve Üstel Geri Çekilme (Exponential Backoff)
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Callable

logger = logging.getLogger("ultron.core.ai_provider")


@dataclass
class AICompletionResponse:
    text: str
    provider_name: str
    model_name: str
    latency_sec: float
    is_fallback: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class AIProvider(ABC):
    """Kanonik Yapay Zeka Model Sağlayıcı Arayüzü."""

    @abstractmethod
    def generate_text(self, prompt: str, system_instruction: str = "", timeout: float = 30.0) -> AICompletionResponse:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass


class GeminiProvider(AIProvider):
    """Google Gemini API Sağlayıcısı."""

    def __init__(self, api_key: str = "", model_name: str = "gemini-flash-latest"):
        self.api_key = api_key
        self.model_name = model_name

    def is_available(self) -> bool:
        return bool(self.api_key)

    def generate_text(self, prompt: str, system_instruction: str = "", timeout: float = 30.0) -> AICompletionResponse:
        t0 = time.time()
        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self.api_key) if self.api_key else genai.Client()
            config = types.GenerateContentConfig(
                system_instruction=system_instruction or None,
                temperature=0.7
            )
            response = client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=config
            )
            text = response.text or ""
            return AICompletionResponse(
                text=text,
                provider_name="Gemini",
                model_name=self.model_name,
                latency_sec=time.time() - t0,
                is_fallback=False
            )
        except Exception as e:
            logger.error(f"[GeminiProvider] API hatası: {e}")
            raise e


class LocalProvider(AIProvider):
    """Yerel Offline Model Sağlayıcısı (Ollama / Llama.cpp Abstraction)."""

    def __init__(self, endpoint_url: str = "http://localhost:11434", model_name: str = "llama3.2:1b"):
        self.endpoint_url = endpoint_url
        self.model_name = model_name

    def is_available(self) -> bool:
        # İleride yerel servis çalışıyorsa True döner
        return False

    def generate_text(self, prompt: str, system_instruction: str = "", timeout: float = 30.0) -> AICompletionResponse:
        t0 = time.time()
        # Yerel LLM çağrısı simülasyonu / abstraction
        return AICompletionResponse(
            text="[Yerel Offline Fallback Yanıtı]",
            provider_name="LocalLLM",
            model_name=self.model_name,
            latency_sec=time.time() - t0,
            is_fallback=True
        )


class FallbackProvider(AIProvider):
    """Ana ve Yedek Sağlayıcılar Arasında Akıllı Yönlendirme Yapan Sağlayıcı."""

    MAX_RETRIES = 3

    def __init__(self, primary: AIProvider, fallback: AIProvider | None = None):
        self.primary = primary
        self.fallback = fallback or LocalProvider()

    def is_available(self) -> bool:
        return self.primary.is_available() or self.fallback.is_available()

    def generate_text(self, prompt: str, system_instruction: str = "", timeout: float = 30.0) -> AICompletionResponse:
        # 1. Primary Deneme (Üstel Geri Çekilme ile)
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                if self.primary.is_available():
                    return self.primary.generate_text(prompt, system_instruction=system_instruction, timeout=timeout)
            except Exception as e:
                logger.warning(f"[FallbackProvider] Primary deneme {attempt}/{self.MAX_RETRIES} başarısız: {e}")
                if attempt < self.MAX_RETRIES:
                    time.sleep(0.5 * (2 ** (attempt - 1)))

        # 2. Fallback Devreye Al
        logger.info("[FallbackProvider] 🔄 Primary yanıt vermedi, yerel yedek sağlayıcıya geçiliyor...")
        if self.fallback and self.fallback.is_available():
            return self.fallback.generate_text(prompt, system_instruction=system_instruction, timeout=timeout)

        raise RuntimeError("Tüm AI sağlayıcıları (Primary & Fallback) devre dışı.")
