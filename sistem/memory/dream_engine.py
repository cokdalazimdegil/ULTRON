"""
ULTRON Dream Engine — Bellek Konsolidasyonu ve Meta-Öğrenim Motoru
──────────────────────────────────────────────────────────────────
• Sistem boştayken (gece 02:00-04:00 veya 30+ dk inaktif) tetiklenir.
• Günün episodik bellek kayıtlarını okur.
• Gemini'a toplu "günlük analiz" prompt'u göndererek meta çıkarımlar üretir.
• Çıkarımları SEMANTIC_MEMORY tier'ına kalıcı olarak yazar.
• Ultron'un kişiliğini ve kullanıcı anlayışını zamanla evriltirir.
"""

from __future__ import annotations

import logging
import threading
import time
import json
from datetime import datetime, date
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ultron.memory.dream_engine")

INACTIVITY_THRESHOLD_SEC = 30 * 60   # 30 dakika hareketsizlik
DREAM_COOLDOWN_SEC = 20 * 60 * 60    # Günde bir kez çalışsın (20 saat)
NIGHT_HOURS = (2, 4)                  # Gece 02:00-04:00 arası


class DreamEngine:
    """
    Sistem boşta/geceyarısı bellek konsolidasyonu yapar.
    """

    def __init__(self, check_interval: float = 300.0):  # 5 dakikada bir kontrol
        self.check_interval = check_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._last_activity_time: float = time.time()
        self._last_dream_time: float = 0.0

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, name="DreamEngine", daemon=True
        )
        self._thread.start()
        logger.info("[DreamEngine] 💤 Bellek konsolidasyon motoru başlatıldı.")

    def stop(self):
        self._running = False

    def ping_activity(self):
        """Her kullanıcı etkileşiminde çağrılır — boşta sayacı sıfırlar."""
        self._last_activity_time = time.time()

    def _loop(self):
        while self._running:
            try:
                self._maybe_dream()
            except Exception as exc:
                logger.debug(f"[DreamEngine] Döngü hatası: {exc}")
            time.sleep(self.check_interval)

    def _maybe_dream(self):
        now = time.time()
        since_last_dream = now - self._last_dream_time
        inactivity = now - self._last_activity_time

        if since_last_dream < DREAM_COOLDOWN_SEC:
            return  # Bugün zaten rüya gördük

        # Koşul 1: Gece saati
        hour = datetime.now().hour
        is_night = NIGHT_HOURS[0] <= hour <= NIGHT_HOURS[1]

        # Koşul 2: Uzun süreli inaktif
        is_inactive = inactivity >= INACTIVITY_THRESHOLD_SEC

        if is_night or is_inactive:
            logger.info("[DreamEngine] 💭 Rüya modu başlatılıyor...")
            self._run_dream_cycle()

    def _run_dream_cycle(self):
        """Günlük bellek konsolidasyonu döngüsü."""
        try:
            # 1. Episodik ve semantik bellek kayıtlarını topla
            episodes = self._gather_episodes()
            if not episodes:
                logger.info("[DreamEngine] Bugün analiz edilecek kayıt yok.")
                return

            # 2. Gemini'ya gönder
            meta_insight = self._synthesize_with_gemini(episodes)
            if not meta_insight:
                return

            # 3. SEMANTIC_MEMORY'e kalıcı yaz
            self._store_insight(meta_insight)
            self._last_dream_time = time.time()
            logger.info(f"[DreamEngine] ✅ Meta içgörü yazıldı: {meta_insight[:80]}...")

        except Exception as exc:
            logger.error(f"[DreamEngine] Rüya döngüsü hatası: {exc}")

    def _gather_episodes(self) -> str:
        """Bugünkü bellek kayıtlarını toplu metin olarak getirir."""
        try:
            from memory.memory_2 import intelligent_memory, MemoryTier

            today = date.today().isoformat()
            entries = intelligent_memory.search(
                query="",  # Hepsini getir
                tier=MemoryTier.EPISODIC_MEMORY,
                limit=50,
            )

            # Semantik bellekten de bugünküleri al
            sem_entries = intelligent_memory.search(
                query="",
                tier=MemoryTier.SEMANTIC_MEMORY,
                limit=30,
            )

            all_entries = (entries or []) + (sem_entries or [])
            if not all_entries:
                return ""

            lines = []
            for e in all_entries:
                content = getattr(e, "content", str(e))
                ts = getattr(e, "timestamp", 0)
                try:
                    ts_str = datetime.fromtimestamp(ts).strftime("%H:%M")
                except Exception:
                    ts_str = "?"
                lines.append(f"[{ts_str}] {content[:200]}")

            return "\n".join(lines)

        except Exception as exc:
            logger.debug(f"[DreamEngine] Bellek okuma hatası: {exc}")
            return ""

    def _synthesize_with_gemini(self, episodes: str) -> Optional[str]:
        """Gemini'ya analiz yaptırır, meta-öğrenim çıkarımı döner."""
        try:
            from orchestrator.gemini_reasoning import query_gemini_reasoning

            today_str = date.today().strftime("%d %B %Y")
            prompt = f"""
Sen ULTRON'sun. Aşağıda {today_str} tarihinde Nuri Can ile olan etkileşimlerinin özeti var.

GÜNÜN KAYITLARI:
{episodes}

Görevin:
1. Nuri Can'ın bugünkü davranışlarından, tepkilerinden ve tercihlerinden 3-5 maddelik somut bir KARAKTERİZASYON çıkar.
2. Bunları kalıcı hafızan için kullanışlı, kısa cümleler olarak yaz.
3. Sadece Türkçe yaz. Markdown kullanma. Her madde yeni satırda olsun.
4. Format: "• [öğrenilen şey]"
Sadece bu formatla yanıt ver, giriş/çıkış cümlesi ekleme.
""".strip()

            result = query_gemini_reasoning(prompt)
            return result.strip() if result else None

        except Exception as exc:
            logger.error(f"[DreamEngine] Gemini sentez hatası: {exc}")
            return None

    def _store_insight(self, insight: str):
        """Meta içgörüyü SEMANTIC_MEMORY'e ve soul.md Dream Log'a yazar."""
        today = date.today().isoformat()

        # 1. Memory 2.0'a kaydet
        try:
            from memory.memory_2 import intelligent_memory, MemoryTier
            key = f"meta_insight_{today}"
            intelligent_memory.store(
                tier=MemoryTier.SEMANTIC_MEMORY,
                key=key,
                content=insight,
                importance=0.9,
            )
            logger.info(f"[DreamEngine] 💾 İçgörü '{key}' anahtarıyla kaydedildi.")
        except Exception as exc:
            logger.error(f"[DreamEngine] Kayıt hatası: {exc}")

        # 2. soul.md Dream Log bölümüne ekle
        try:
            from app_paths import resource_path
            soul_path = resource_path("core", "persona", "soul.md")
            if soul_path.exists():
                soul_text = soul_path.read_text(encoding="utf-8")
                log_entry = f"\n**{today}:**\n{insight}\n"
                # <!-- DREAM_LOG_START --> ... <!-- DREAM_LOG_END --> arasına ekle
                if "<!-- DREAM_LOG_START -->" in soul_text:
                    soul_text = soul_text.replace(
                        "<!-- DREAM_LOG_START -->",
                        f"<!-- DREAM_LOG_START -->{log_entry}"
                    )
                    soul_path.write_text(soul_text, encoding="utf-8")
                    logger.info("[DreamEngine] 📝 soul.md Dream Log güncellendi.")
        except Exception as exc:
            logger.debug(f"[DreamEngine] soul.md güncelleme hatası: {exc}")


# Global singleton
dream_engine = DreamEngine()

