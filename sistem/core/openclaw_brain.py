#!/usr/bin/env python3
"""
ULTRON 5.0 — OpenClaw Beyin Modülü (Core Brain Engine)
────────────────────────────────────────────────────
OpenClaw otonom Gateway servisi ile entegre çalışarak sistemin 
ana yapay zeka karar ve ajan orkestrasyon motorunu sağlar.
"""

from __future__ import annotations

import os
import sys
import time
import json
import shutil
import logging
import subprocess
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger("ultron.core.openclaw_brain")

GATEWAY_PORT = 18789
GATEWAY_URL = f"http://127.0.0.1:{GATEWAY_PORT}"

class OpenClawBrain:
    def __init__(self, port: int = GATEWAY_PORT):
        self.port = port
        self.gateway_url = f"http://127.0.0.1:{port}"
        self._process: Optional[subprocess.Popen] = None
        self._enabled = True

    def is_enabled(self) -> bool:
        """OpenClaw'un aktif olup olmadığını kontrol eder. İstenirse çevre değişkeni veya konfig ile devre dışı bırakılabilir."""
        if os.environ.get("ULTRON_DISABLE_OPENCLAW") in ("1", "true", "True"):
            return False
        try:
            from app_config import get_app_config_value
            cfg = get_app_config_value("openclaw_enabled", True)
            if cfg is False:
                return False
        except Exception:
            pass
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def _get_exe(self) -> str:
        """Sistem üzerindeki openclaw çalıştırılabilir yolunu bulur."""
        found = shutil.which("openclaw")
        if found:
            return found
        return "openclaw.cmd" if os.name == "nt" else "openclaw"

    def start_gateway(self) -> bool:
        """OpenClaw Gateway servisini başlatır (çalışmıyorsa)."""
        if not self.is_enabled():
            logger.info("ℹ️ [OpenClaw Brain] OpenClaw devre dışı; ULTRON yerel otonom motor modunda çalışıyor.")
            return True

        if self.ping():
            logger.info("🦞 [OpenClaw Brain] Gateway zaten çalışıyor (Port %d).", self.port)
            return True

        logger.info("🦞 [OpenClaw Brain] Gateway servisi başlatılıyor (Port %d)...", self.port)
        try:
            exe = self._get_exe()
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self._process = subprocess.Popen(
                [exe, "gateway", "--port", str(self.port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            # Gateway'in hazır olması için kısa bir bekleme
            for _ in range(10):
                time.sleep(0.5)
                if self.ping():
                    logger.info("✅ [OpenClaw Brain] Gateway başarıyla başlatıldı.")
                    return True
        except Exception as exc:
            logger.error("[OpenClaw Brain] Gateway başlatılamadı: %s", exc)
        return self.ping()

    def stop_gateway(self):
        """ULTRON tarafından başlatılan Gateway sürecini durdurur."""
        if self._process and self._process.poll() is None:
            try:
                self._process.terminate()
                self._process.wait(timeout=3)
                logger.info("[OpenClaw Brain] Gateway servisi durduruldu.")
            except Exception:
                pass
            self._process = None

    def ping(self) -> bool:
        """Gateway servisinin erişilebilir olup olmadığını kontrol eder."""
        if not self.is_enabled():
            return True
        try:
            req = urllib.request.Request(f"{self.gateway_url}/health", method="GET")
            with urllib.request.urlopen(req, timeout=1.5) as resp:
                return resp.status in (200, 204)
        except Exception:
            # CLI üzerinden yedek durum kontrolü
            try:
                exe = self._get_exe()
                res = subprocess.run(
                    [exe, "health"],
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=3,
                    text=True,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
                )
                return res.returncode == 0
            except Exception:
                return False

    def _get_token(self) -> str:
        """~/.openclaw/openclaw.json dosyasından Gateway tokenini okur."""
        try:
            cfg_path = Path.home() / ".openclaw" / "openclaw.json"
            if cfg_path.exists():
                data = json.loads(cfg_path.read_text(encoding="utf-8"))
                return data.get("gateway", {}).get("auth", {}).get("token", "")
        except Exception:
            pass
        return ""

    def ask(self, prompt: str, session_id: str = "default") -> str:
        """Kullanıcı girdisini OpenClaw Beyni'ne aktarır ve ajan yanıtını döndürür."""
        if not self.is_enabled():
            return ""
        if not prompt or not prompt.strip():
            return ""

        prompt_clean = prompt.strip()
        logger.info("🦞 [OpenClaw Brain] Komut işleniyor: '%s'", prompt_clean[:60])

        # CLI üzerinden OpenClaw Agent Turn çağırma
        try:
            exe = self._get_exe()
            tok = self._get_token()
            env = os.environ.copy()
            if tok:
                env["OPENCLAW_GATEWAY_TOKEN"] = tok
            cmd = [exe, "agent", "--session-id", session_id, "--message", prompt_clean, "--timeout", "25", "--json"]
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            res = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=28,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                creationflags=flags
            )

            if res.returncode == 0 and res.stdout:
                try:
                    data = json.loads(res.stdout)
                    if isinstance(data, dict):
                        # OpenClaw turn output format: result.payloads[0].text or result.meta.finalAssistantVisibleText
                        result_obj = data.get("result", {})
                        if isinstance(result_obj, dict):
                            payloads = result_obj.get("payloads", [])
                            if payloads and isinstance(payloads, list):
                                for p in payloads:
                                    if isinstance(p, dict) and p.get("text"):
                                        return str(p["text"]).strip()
                            meta_obj = result_obj.get("meta", {})
                            if isinstance(meta_obj, dict):
                                txt = meta_obj.get("finalAssistantVisibleText") or meta_obj.get("finalAssistantRawText")
                                if txt:
                                    return str(txt).strip()
                        response_text = data.get("response") or data.get("message") or data.get("text") or ""
                        if response_text:
                            return str(response_text).strip()
                except Exception:
                    pass
                return res.stdout.strip()
            elif res.stderr:
                logger.warning("[OpenClaw Brain] Agent uyarısı/hatası: %s", res.stderr[:200])
        except subprocess.TimeoutExpired:
            logger.error("[OpenClaw Brain] Komut yanıt süresi aşıldı.")
            return "⚠️ [OpenClaw Brain] Yanıt zaman aşımına uğradı."
        except Exception as exc:
            logger.error("[OpenClaw Brain] Komut yürütme hatası: %s", exc)

        return ""

    def ask_with_fallback(self, prompt: str, session_id: str = "default") -> str:
        """
        Kullanıcı isteğini OpenClaw Beyni'ne iletir.
        Eğer OpenClaw devre dışıysa, gecikir veya zaman aşımına uğrarsa,
        otomatik olarak yerel Gemini Pro ve canlı web sentezleme motoru devreye girer.
        """
        if not prompt or not prompt.strip():
            return ""

        if self.is_enabled():
            res = self.ask(prompt, session_id=session_id)
            if res and not res.startswith("⚠️") and len(res.strip()) > 15:
                return res

        logger.info("[OpenClaw Brain] 🔄 Yerel derin analiz ve canlı web araştırma motoru devreye alındı.")
        
        # 1. Canlı web araması (Güncel haberler, ürün özellikleri ve son dakika duyuruları için)
        web_context = ""
        try:
            from actions.research_engine import simple_web_search
            web_context = simple_web_search(prompt[:120], max_chars=3500)
        except Exception as err:
            logger.debug(f"[OpenClaw Brain] Web arama hatası: {err}")

        # 2. Gemini Pro Derin Akıl Yürütme motoru
        try:
            from orchestrator.gemini_reasoning import query_gemini_reasoning
            system_prompt = (
                "Sen ULTRON'un otonom stratejik analiz ve derin araştırma beynisin. "
                "Kullanıcının sorusunu veya araştırma konusunu derinlemesine analiz et. "
                "Eğer güncel web arama sonuçları verildiyse, o verileri eksiksiz kullanarak "
                "yapılandırılmış, teknik, tarafsız ve kapsamlı bir stratejik rapor sun."
            )
            full_prompt = f"{prompt}\n\n[GÜNCEL WEB ARAŞTIRMA VERİLERİ]:\n{web_context}" if web_context else prompt
            fallback_res = query_gemini_reasoning(full_prompt, system_instruction=system_prompt, model_tier="pro", temperature=0.5)
            if fallback_res and len(fallback_res.strip()) > 20:
                return fallback_res
        except Exception as e:
            logger.debug(f"[OpenClaw Brain] Gemini Pro fallback hatası: {e}")

        if web_context:
            return f"🔍 [Canlı Web Araştırma Bulguları]:\n\n{web_context}"

        return "İstenen konu hakkında detaylı araştırma tamamlanamadı. Lütfen internet bağlantınızı kontrol edip tekrar deneyin."

# Global singleton örneği
openclaw_brain = OpenClawBrain()

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Testing OpenClaw Brain ping...")
    is_ok = openclaw_brain.ping()
    print(f"Ping result: {is_ok}")
