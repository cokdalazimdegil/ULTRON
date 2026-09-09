"""
ULTRON Companion Mode (Oyun ve Eğlence Arkadaşı Motoru)
═══════════════════════════════════════════════════════
• Arka planda çalışarak ekranı periyodik olarak izler.
• Oyunlarda, filmlerde veya videolarda dikkat çekici, heyecanlı bir an olduğunda
  kullanıcıyla gerçek bir oyun arkadaşı gibi canlı, esprili ve kısa yorumlar yapar.
• Ekran durağanken veya kodlama/okuma yapılırken sessiz kalır (Token & Kota Tasarrufu).
"""

from __future__ import annotations

import io
import logging
import os
import threading
import time
from typing import Any, Dict, Optional, Tuple

from PIL import Image, ImageChops, ImageGrab, ImageStat
from google import genai
from google.genai import types

from actions.tts import speak_text
from app_config import get_app_config_value
from core.event_bus import bus
from core.events import EventPriority, EventSource, UltronEvent
from core.notification_engine import NotificationRequest, notification_engine

logger = logging.getLogger("ultron.actions.companion")

# Desteklenen Gemini Vision modelleri
COMPANION_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.0-flash",
)


class CompanionEngine:
    """
    ULTRON Companion Engine — Singleton.
    Kullanıcı oyun oynarken veya video izlerken ekranı izleyip sesli yorumlar yapan arkadaş modu.
    """

    def __init__(self, interval_sec: int = 12):
        self.interval_sec = max(5, interval_sec)
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        self._last_frame_small: Optional[Image.Image] = None
        self._last_comment: str = ""
        self._last_comment_time: float = 0.0
        self._comment_count: int = 0
        self._last_error: str = ""

    def is_running(self) -> bool:
        return self._running

    def get_status(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "interval_sec": self.interval_sec,
                "last_comment": self._last_comment,
                "last_comment_time": self._last_comment_time,
                "comment_count": self._comment_count,
                "last_error": self._last_error,
            }

    def start(self, interval_sec: Optional[int] = None) -> str:
        """Companion modunu arka planda başlatır."""
        with self._lock:
            if self._running:
                return "Companion Modu zaten devrede patron. Ekranını izlemeye devam ediyorum!"

            if interval_sec and interval_sec >= 5:
                self.interval_sec = interval_sec

            self._running = True
            self._last_frame_small = None
            self._last_error = ""
            self._thread = threading.Thread(
                target=self._companion_loop,
                name="UltronCompanionThread",
                daemon=True,
            )
            self._thread.start()

        # Event Bus ve bildirim motoruna haber ver
        try:
            bus.publish("ui_alert", "🎮 [COMPANION]: Arkadaş modu devrede! Ekranını seninle birlikte izliyorum.")
            bus.publish_event(
                UltronEvent(
                    event_type="companion.started",
                    payload={"interval_sec": self.interval_sec},
                    source=EventSource.SYSTEM,
                    priority=EventPriority.NORMAL,
                )
            )
        except Exception:
            pass

        return "Companion Modu başlatıldı. Artık ekranını izliyorum; oyun veya videolarda sana eşlik edeceğim!"

    def stop(self) -> str:
        """Companion modunu durdurur."""
        with self._lock:
            if not self._running:
                return "Companion Modu şu anda aktif değil."

            self._running = False

        # Event Bus yayını
        try:
            bus.publish("ui_alert", "🎮 [COMPANION]: Arkadaş modu durduruldu.")
            bus.publish_event(
                UltronEvent(
                    event_type="companion.stopped",
                    payload={"total_comments": self._comment_count},
                    source=EventSource.SYSTEM,
                    priority=EventPriority.NORMAL,
                )
            )
        except Exception:
            pass

        return "Companion Modu kapatıldı. İyi dinlenmeler patron."

    # ── Ekran Yakalama ve Değişim Tespiti ───────────────────────────────────

    def _capture_screen(self) -> Optional[Tuple[bytes, Image.Image]]:
        """
        Ekran görüntüsü alır, düşük çözünürlüklü JPEG baytları ve
        karşılaştırma için küçük gri tonlamalı imaj döner.
        """
        try:
            screenshot = ImageGrab.grab()
            if screenshot.mode in ("RGBA", "P"):
                screenshot = screenshot.convert("RGB")

            # Karşılaştırma için 64x36 küçük gri imaj
            small_gray = screenshot.resize((64, 36), Image.Resampling.BILINEAR).convert("L")

            # LLM analizi için optimize edilmiş 960x540 görsel
            screenshot.thumbnail((960, 540), Image.Resampling.LANCZOS)
            buffer = io.BytesIO()
            screenshot.save(buffer, format="JPEG", quality=65, optimize=True)
            jpeg_bytes = buffer.getvalue()

            return jpeg_bytes, small_gray
        except Exception as e:
            logger.debug(f"[Companion] Ekran yakalama hatası: {e}")
            return None

    def _has_screen_changed(self, current_small: Image.Image) -> bool:
        """
        Son kare ile şimdiki kare arasında anlamlı bir hareket/değişim var mı kontrol eder.
        Durağan ekranlarda gereksiz token tüketimini engeller.
        """
        if self._last_frame_small is None:
            self._last_frame_small = current_small
            return True

        try:
            diff = ImageChops.difference(current_small, self._last_frame_small)
            stat = ImageStat.Stat(diff)
            mean_diff = stat.mean[0] if stat.mean else 0.0
            self._last_frame_small = current_small

            # Eğer ortalama piksel farkı %2.0'den büyükse ekran hareketli demektir
            return mean_diff > 2.0
        except Exception:
            self._last_frame_small = current_small
            return True

    # ── Döngü ve LLM İletişimi ──────────────────────────────────────────────

    def _companion_loop(self) -> None:
        """Arka plan ana izleme döngüsü."""
        logger.info("[Companion] 🎮 Arkadaş modu döngüsü başladı.")

        api_key = str(get_app_config_value("gemini_api_key", "") or "").strip()
        if not api_key:
            api_key = str(os.environ.get("GEMINI_API_KEY", "") or "").strip()

        if not api_key:
            self._last_error = "Gemini API anahtarı bulunamadı."
            logger.warning("[Companion] Gemini API anahtarı eksik, döngü sonlanıyor.")
            self._running = False
            return

        try:
            client = genai.Client(api_key=api_key)
        except Exception as e:
            self._last_error = f"Gemini Client oluşturulamadı: {e}"
            logger.error(f"[Companion] {self._last_error}")
            self._running = False
            return

        prompt = (
            "Sen ULTRON'un 'Companion' (Oyun ve Eğlence Arkadaşı) modülsün.\n"
            "Kullanıcı oyun oynarken, video, maç veya film izlerken ekrana bakan zeki, espritüel, sempatik ve eğlenceli bir arkadaşsın.\n\n"
            "Görseli incele:\n"
            "1. Ekranda aktif bir oyun, video, film, spor karşılaşması veya eğlenceli bir içerik varsa:\n"
            "   Gelişen olaya dair canlı, çok kısa (maksimum 1-2 cümle) ve esprili bir yorum yap.\n"
            "   Örnekler:\n"
            "   - 'Mükemmel vuruş patron, affetmedin!'\n"
            "   - 'Arkadaki adama dikkat et, pusu kurmuş bekliyor.'\n"
            "   - 'Bu film sahnesindeki detay gerçekten inanılmaz.'\n"
            "2. Eğer ekranda sadece kod düzenleyici, masaüstü, terminal, durağan bir tarayıcı sayfası veya sıradan bir iş akışı varsa:\n"
            "   Hiçbir şey söyleme, SADECE ve KESİNLİKLE 'SILENCE' yaz.\n\n"
            "Yanıtını doğrudan Türkçe ve samimi bir dille ver. Tırnak işareti veya rol yapma etiketleri ekleme."
        )

        while self._running:
            # Hemen çıkış yapabilmek için küçük adımlarla bekle
            elapsed = 0
            while elapsed < self.interval_sec and self._running:
                time.sleep(0.5)
                elapsed += 0.5

            if not self._running:
                break

            # 1. Ekranı yakala
            capture_res = self._capture_screen()
            if not capture_res:
                continue

            jpeg_bytes, small_gray = capture_res

            # 2. Değişim tespiti (Durağan ekranlarda API çağırma)
            if not self._has_screen_changed(small_gray):
                logger.debug("[Companion] Ekran durağan, API çağrısı atlandı.")
                continue

            # 3. Gemini Vision ile analiz et
            comment = self._analyze_frame(client, jpeg_bytes, prompt)
            if not comment or "SILENCE" in comment.upper():
                continue

            # 4. Yorumu yayınla ve seslendir
            self._dispatch_comment(comment)

        logger.info("[Companion] 🎮 Arkadaş modu döngüsü tamamlandı.")

    def _analyze_frame(self, client: genai.Client, jpeg_bytes: bytes, prompt: str) -> Optional[str]:
        """Gemini vision modeline görseli gönderip yorum alır."""
        image_part = types.Part.from_bytes(data=jpeg_bytes, mime_type="image/jpeg")

        for model_name in COMPANION_MODELS:
            try:
                response = client.models.generate_content(
                    model=model_name,
                    contents=[image_part, prompt],
                    config=types.GenerateContentConfig(
                        temperature=0.75,
                        max_output_tokens=120,
                    ),
                )
                text = str(getattr(response, "text", "") or "").strip()
                if text:
                    return text
            except Exception as e:
                err_str = str(e)
                if "429" in err_str or "quota" in err_str.lower():
                    logger.debug(f"[Companion] Model {model_name} kota/hız limiti, bekleniyor.")
                    time.sleep(2.0)
                else:
                    logger.debug(f"[Companion] Model {model_name} hata: {e}")
                continue

        return None

    def _dispatch_comment(self, comment: str) -> None:
        """Yorumu TTS ve UI kanallarına fırlatır."""
        with self._lock:
            self._last_comment = comment
            self._last_comment_time = time.time()
            self._comment_count += 1

        logger.info(f"[Companion] 💬 Yorum: {comment}")

        # 1. Yerel TTS ile seslendir (non-blocking)
        try:
            speak_text(comment)
        except Exception as e:
            logger.debug(f"[Companion] TTS hatası: {e}")

        # 2. Event Bus üzerinden Web UI'a alert yayınla
        try:
            bus.publish("ui_alert", f"🎮 [COMPANION]: {comment}")
            bus.publish_event(
                UltronEvent(
                    event_type="companion.comment",
                    payload={"text": comment},
                    source=EventSource.SYSTEM,
                    priority=EventPriority.NORMAL,
                )
            )
        except Exception as e:
            logger.debug(f"[Companion] EventBus hatası: {e}")

        # 3. Notification Engine ile bildirim gönder
        try:
            notification_engine.notify(
                NotificationRequest(
                    title="🎮 ULTRON Companion",
                    message=comment,
                    priority=EventPriority.NORMAL,
                    source="companion",
                    channels=["web_ui"],
                    cooldown_key="companion_comment",
                )
            )
        except Exception:
            pass


# ── Global Singleton ────────────────────────────────────────────────────────
companion_engine = CompanionEngine()
