"""
ULTRON Companion Mode (Oyun ve Eğlence Arkadaşı)
─────────────────────────────────────────────────
• Arka planda çalışarak ekranı izler.
• Oyunlarda, filmlerde veya videolarda dikkat çekici bir olay olduğunda
  kullanıcıyla gerçek bir arkadaş gibi kısa ve esprili yorumlar yapar.
"""

import threading
import time
import logging
import base64
from io import BytesIO
from typing import Callable, Optional

from PIL import ImageGrab
from google import genai
from actions.tts import speak_text
from app_config import get_app_config_value
import os

logger = logging.getLogger("ultron.actions.companion")

class CompanionEngine:
    def __init__(self, interval_sec: int = 15):
        self.interval_sec = interval_sec
        self._running = False
        self._thread: Optional[threading.Thread] = None
    def _notify(self, text: str):
        from core.event_bus import bus
        bus.publish("ui_alert", f"🎮 [COMPANION]: {text}")

    def start(self):
        if self._running:
            return "Companion Modu zaten çalışıyor."
        self._running = True
        self._thread = threading.Thread(target=self._companion_loop, name="UltronCompanion", daemon=True)
        self._thread.start()
        return "Companion Modu başlatıldı. Artık ekranını izleyip seninle sohbet edeceğim!"
        
    def stop(self):
        if not self._running:
            return "Companion Modu aktif değil."
        self._running = False
        return "Companion Modu kapatıldı. Yalnızsın patron."

    def _companion_loop(self):
        logger.info("[Companion] 🎮 Arkadaş modu devrede!")
        api_key = str(get_app_config_value("gemini_api_key", "") or "").strip()
        if not api_key:
            api_key = str(os.environ.get("GEMINI_API_KEY", "") or "").strip()
        client = genai.Client(api_key=api_key)
        
        while self._running:
            time.sleep(self.interval_sec)
            if not self._running:
                break
                
            try:
                # Düşük çözünürlükte hızlı ekran görüntüsü al
                img = ImageGrab.grab()
                img.thumbnail((800, 600))
                buffered = BytesIO()
                img.save(buffered, format="JPEG", quality=50)
                
                # Modeli çağır
                prompt = (
                    "Sen eğlenceli, biraz alaycı ve espritüel bir oyun/film arkadaşısın. "
                    "Şu an yanımda oturmuş ekranımı izliyorsun. Ekranda oyun veya film varsa "
                    "oradaki ilginç bir olaya dair çok kısa (maksimum 1 cümle) ve esprili bir yorum yap. "
                    "Örneğin: 'Abi soldan adam geliyor dikkat et!' veya 'Bu film de amma sıkıcıymış ha.' "
                    "Eğer ekranda sadece kod, masaüstü veya boş bir şey varsa SADECE VE KESİNLİKLE 'SILENCE' yaz."
                )
                
                response = client.models.generate_content(
                    model='gemini-2.0-flash',
                    contents=[
                        {"mime_type": "image/jpeg", "data": buffered.getvalue()},
                        prompt
                    ],
                    config={"temperature": 0.7}
                )
                
                text = response.text.strip()
                if text and "SILENCE" not in text:
                    print(f"[Companion] 💬 Yorum: {text}")
                    # Sesi oku
                    speak_text(text)
                    # UI'a bas
                    self._notify(text)
                        
            except Exception as e:
                logger.debug(f"[Companion] Loop hatası: {e}")

companion_engine = CompanionEngine()
