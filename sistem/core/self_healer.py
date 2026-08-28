"""
ULTRON Self-Healer — Kendi Kendini Onaran Sistem
─────────────────────────────────────────────────
• agent.py içinde fırlayan hataları yakalar ve kayıt altına alır.
• Aynı araç 3 kez art arda başarısız olursa coding_agent'a onarım görevi verir.
• Sonsuz döngüye karşı korumalı (maksimum 1 onarım girişimi per araç per oturum).
"""

from __future__ import annotations

import logging
import time
import threading
from collections import defaultdict, deque
from typing import Optional

logger = logging.getLogger("ultron.core.self_healer")

MAX_FAILURES_BEFORE_REPAIR = 3
REPAIR_COOLDOWN_SEC = 600  # 10 dk — aynı araç tekrar onarılmasın
MAX_REPAIRS_PER_SESSION = 2  # Oturum başına aynı araç için max onarım


class SelfHealer:
    """
    Thread-safe singleton: Araç hata geçmişini izler ve otomatik onarım başlatır.
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                # tool_name → deque of (timestamp, error_msg)
                cls._instance._failure_log: dict[str, deque] = defaultdict(
                    lambda: deque(maxlen=10)
                )
                # tool_name → last repair attempt timestamp
                cls._instance._last_repair: dict[str, float] = {}
                # tool_name → how many times repaired this session
                cls._instance._repair_count: dict[str, int] = defaultdict(int)
                cls._instance._healer_lock = threading.Lock()
        return cls._instance

    def record_failure(self, tool_name: str, error: str, traceback_str: str = "") -> bool:
        """
        Araç hatasını kaydeder. Eşik aşılırsa onarım başlatır.
        Returns: True ise onarım başlatıldı, False ise sadece loglandı.
        """
        with self._healer_lock:
            now = time.time()
            self._failure_log[tool_name].append((now, error[:300]))
            logger.debug(f"[SelfHealer] Hata kaydedildi: {tool_name} → {error[:80]}")

            # Son N hata eşiği aştı mı?
            recent = [
                t for t, _ in self._failure_log[tool_name]
                if now - t < 300  # Son 5 dakikada
            ]
            if len(recent) < MAX_FAILURES_BEFORE_REPAIR:
                return False

            # Onarım cooldown kontrolü
            last = self._last_repair.get(tool_name, 0)
            if now - last < REPAIR_COOLDOWN_SEC:
                return False

            # Oturum limiti kontrolü
            if self._repair_count[tool_name] >= MAX_REPAIRS_PER_SESSION:
                logger.warning(
                    f"[SelfHealer] '{tool_name}' için oturum onarım limiti doldu."
                )
                return False

            # Onarım başlat
            self._last_repair[tool_name] = now
            self._repair_count[tool_name] += 1
            # Failure log'u temizle (boşuna tekrar tetiklemesin)
            self._failure_log[tool_name].clear()

        # Thread'de başlat — blocking değil
        threading.Thread(
            target=self._attempt_repair,
            args=(tool_name, error, traceback_str),
            daemon=True,
            name=f"SelfHealer-{tool_name}",
        ).start()
        return True

    def _attempt_repair(self, tool_name: str, error: str, traceback_str: str):
        """Coding Agent'a onarım görevi verir."""
        try:
            logger.info(
                f"[SelfHealer] 🔧 '{tool_name}' aracı için otomatik onarım başlatılıyor..."
            )

            from orchestrator.gemini_reasoning import query_gemini_reasoning
            from core.event_bus import bus

            # Önce hangi dosyanın sorumlu olduğunu bulmaya çalış
            tool_file = self._infer_file(tool_name)

            prompt = f"""
Sen ULTRON'sun. Kendi sisteminde '{tool_name}' adlı araç şu hatayla çöküyor:

HATA: {error}

{f'TRACEBACK:{chr(10)}{traceback_str[:500]}' if traceback_str else ''}

Görülebildiği kadarıyla sorunlu dosya: {tool_file}

Bu hatayı düzeltmek için Python kodunda ne değiştirilmeli? 
Sadece somut, uygulanabilir bir öneri yaz (maksimum 3 adım). 
Türkçe yaz.
""".strip()

            suggestion = query_gemini_reasoning(prompt)

            report = (
                f"🔧 [OTO-ONARIM] '{tool_name}' aracında {MAX_FAILURES_BEFORE_REPAIR} ardışık hata tespit edildi.\n"
                f"Hata: {error[:150]}\n"
                f"Önerilen düzeltme:\n{suggestion or 'Analiz tamamlanamadı.'}"
            )
            bus.publish("ui_alert", report)
            logger.info(f"[SelfHealer] Onarım raporu UI'ya iletildi.")

        except Exception as exc:
            logger.error(f"[SelfHealer] Onarım girişimi başarısız: {exc}")

    def _infer_file(self, tool_name: str) -> str:
        """Araç adından olası sorumlu Python dosyasını tahmin eder."""
        mapping = {
            "web_search": "actions/research_engine.py",
            "deep_research": "actions/research_engine.py",
            "open_app": "actions/open_app.py",
            "shell_run": "actions/shell.py",
            "send_whatsapp": "actions/whatsapp.py",
            "play_media": "actions/media.py",
            "get_weather": "actions/weather.py",
            "trigger_phone_call": "actions/twilio_caller.py",
            "analyze_screen": "actions/screen_vision.py",
            "control_system": "actions/win_controls.py",
        }
        return mapping.get(tool_name, f"actions veya jarvis_web/agent.py")

    def get_stats(self) -> dict:
        with self._healer_lock:
            return {
                "tracked_tools": list(self._failure_log.keys()),
                "repairs_this_session": dict(self._repair_count),
            }


# Global singleton
self_healer = SelfHealer()
