"""
ULTRON Semantic Desktop — Ekran Belleği ve Anlık Farkındalık
────────────────────────────────────────────────────────────
Her 5 dakikada bir ekran görüntüsü alır, Gemini Vision ile özetler
ve EPISODIC_MEMORY'e kaydeder. "Dün ne bakıyordum?" sorusunu yanıtlar.

Bağımlılıklar: mss (ekran yakalama) — Gemini Vision (OCR yerine)
"""

from __future__ import annotations

import base64
import logging
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ultron.computer.semantic_desktop")

DEFAULT_CAPTURE_INTERVAL = 300   # 5 dakika
RETENTION_DAYS = 7               # 7 günden eski kayıtlar silinir
MAX_WIDTH = 800                  # Görüntü ölçekleme (API token tasarrufu)


class SemanticDesktop:
    """
    Ekranı periyodik olarak yakalar, Gemini Vision ile özetler,
    zaman damgalı olarak episodik belleğe kaydeder.
    """

    def __init__(self, capture_interval: float = DEFAULT_CAPTURE_INTERVAL):
        self.capture_interval = capture_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self):
        if self._running:
            return
        # mss kurulu mu kontrol et
        if not self._check_mss():
            logger.warning("[SemanticDesktop] 'mss' paketi bulunamadı. pip install mss")
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, name="SemanticDesktop", daemon=True
        )
        self._thread.start()
        logger.info("[SemanticDesktop] 🖥️ Ekran belleği daemon başlatıldı.")

    def stop(self):
        self._running = False
        logger.info("[SemanticDesktop] Ekran belleği daemon durduruldu.")

    def _check_mss(self) -> bool:
        try:
            import mss  # noqa
            return True
        except ImportError:
            return False

    # ── Ana döngü ─────────────────────────────────────────────────────────────

    def _loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as exc:
                logger.debug(f"[SemanticDesktop] Döngü hatası: {exc}")
            time.sleep(self.capture_interval)

    def _tick(self):
        # 1. Ekranı yakala
        screenshot_b64 = self._capture_screen()
        if not screenshot_b64:
            return

        # 2. Gemini Vision ile özetle
        summary = self._summarize_with_gemini(screenshot_b64)
        if not summary:
            return

        # 3. EPISODIC_MEMORY'e zaman damgalı kaydet
        self._save_to_memory(summary)

        # 4. Eski kayıtları temizle (retention policy)
        self._cleanup_old_entries()

    # ── Ekran yakalama ────────────────────────────────────────────────────────

    def _capture_screen(self) -> Optional[str]:
        """mss ile birincil ekranı yakalar, base64 JPEG döner."""
        try:
            import mss
            import mss.tools

            with mss.mss() as sct:
                # Ana monitör
                monitor = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
                screenshot = sct.grab(monitor)

                # Pillow ile ölçekle ve sıkıştır
                try:
                    from PIL import Image
                    import io
                    img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
                    # En-boy oranını koru, MAX_WIDTH'e indir
                    w, h = img.size
                    if w > MAX_WIDTH:
                        ratio = MAX_WIDTH / w
                        img = img.resize((MAX_WIDTH, int(h * ratio)), Image.LANCZOS)
                    buf = io.BytesIO()
                    img.save(buf, format="JPEG", quality=60)
                    return base64.b64encode(buf.getvalue()).decode("utf-8")
                except ImportError:
                    # Pillow yoksa ham PNG
                    import io
                    buf = io.BytesIO()
                    mss.tools.to_png(screenshot.rgb, screenshot.size, output=buf)
                    return base64.b64encode(buf.getvalue()).decode("utf-8")

        except Exception as exc:
            logger.debug(f"[SemanticDesktop] Ekran yakalama hatası: {exc}")
            return None

    # ── Gemini Vision özeti ───────────────────────────────────────────────────

    def _summarize_with_gemini(self, screenshot_b64: str) -> Optional[str]:
        """Gemini Vision'a ekran özetini yaptırır."""
        try:
            from orchestrator.gemini_reasoning import query_gemini_reasoning

            prompt = (
                "Bu ekran görüntüsünde kullanıcı ne yapıyor? "
                "Kısa ve nesnel bir özet yaz (1-2 cümle, Türkçe). "
                "Açık olan uygulama, dosya adı veya web sitesi varsa belirt. "
                "Özel bilgi (şifre, kredi kartı) görüyorsan sadece '[GİZLİ İÇERİK]' yaz."
            )
            result = query_gemini_reasoning(
                prompt,
                image_base64=screenshot_b64,
                image_mime="image/jpeg",
            )
            return result.strip() if result else None
        except Exception as exc:
            logger.debug(f"[SemanticDesktop] Gemini Vision hatası: {exc}")
            return None

    # ── Belleğe kaydetme ──────────────────────────────────────────────────────

    def _save_to_memory(self, summary: str):
        """EPISODIC_MEMORY'e zaman damgalı kayıt ekler."""
        try:
            from memory.memory_2 import intelligent_memory, MemoryTier

            now = datetime.now()
            key = f"screen_{now.strftime('%Y%m%d_%H%M%S')}"
            content = f"[{now.strftime('%Y-%m-%d %H:%M')}] {summary}"

            intelligent_memory.store(
                tier=MemoryTier.EPISODIC_MEMORY,
                key=key,
                content=content,
                importance=0.4,  # Düşük önem — çok kayıt oluşacak
                metadata={"source": "semantic_desktop", "timestamp": now.isoformat()},
            )
            logger.debug(f"[SemanticDesktop] Kayıt: {summary[:60]}...")
        except Exception as exc:
            logger.debug(f"[SemanticDesktop] Bellek kayıt hatası: {exc}")

    # ── Eski kayıt temizliği ──────────────────────────────────────────────────

    def _cleanup_old_entries(self):
        """RETENTION_DAYS günden eski ekran kayıtlarını siler."""
        try:
            from memory.memory_2 import intelligent_memory, MemoryTier

            cutoff = time.time() - (RETENTION_DAYS * 86400)
            entries = intelligent_memory.get_tier(MemoryTier.EPISODIC_MEMORY)

            deleted = 0
            for entry in entries:
                meta_source = entry.metadata.get("source", "")
                if meta_source == "semantic_desktop" and entry.timestamp < cutoff:
                    intelligent_memory.delete(entry.key)
                    deleted += 1

            if deleted:
                logger.info(f"[SemanticDesktop] 🗑️ {deleted} eski ekran kaydı temizlendi.")
        except Exception as exc:
            logger.debug(f"[SemanticDesktop] Temizlik hatası: {exc}")

    def search_screen_history(self, query: str, limit: int = 5) -> str:
        """
        Geçmiş ekran kayıtlarında semantik arama yapar.
        "Dün Python kütüphanesi okuyordum, adı neydi?" gibi sorulara yanıt verir.
        """
        try:
            from memory.memory_2 import intelligent_memory

            results = intelligent_memory.search(query, limit=limit)
            screen_results = [r for r in results if r.metadata.get("source") == "semantic_desktop"]

            if not screen_results:
                return "Ekran geçmişinde bu konuyla ilgili kayıt bulunamadı."

            lines = [f"🖥️ Ekran geçmişi — '{query}':"]
            for r in screen_results:
                lines.append(f"  • {r.content[:150]}")
            return "\n".join(lines)
        except Exception as exc:
            return f"Ekran geçmişi arama hatası: {exc}"


# Global singleton
semantic_desktop = SemanticDesktop()
