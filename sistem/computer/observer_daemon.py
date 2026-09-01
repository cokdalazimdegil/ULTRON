"""
ULTRON Observer Daemon — Çevresel Farkındalık Motoru
────────────────────────────────────────────────────
• Arka planda webcam'den periyodik olarak kare yakalar.
• OpenCV ile yerel yüz tespiti yapar (Gemini API çağrısı YOKTUR — sadece yüz varsa).
• Yüz bulunursa Gemini Vision'a kısa bir "ruh hali analizi" isteği gönderir.
• Oturum açılışı/kapanışı ve ruh hali sonuçları EventBus'a yayınlanır.
• server.py lifespan'ı içinden başlatılır.
"""

from __future__ import annotations

import base64
import logging
import threading
import time
from typing import Optional

import cv2

from core.event_bus import bus

logger = logging.getLogger("ultron.computer.observer")

# Varsayılan ayarlar
DEFAULT_PATROL_INTERVAL   = 30   # saniye — kare yakalama aralığı
MOOD_ANALYSIS_INTERVAL    = 120  # saniye — Gemini çağrı aralığı (API limiti)
PRESENCE_LOST_THRESHOLD   = 3    # kaç ardışık "boş kare" sonrasında "gitti" denir

# Global — lazy init (start() içinde yüklenir)
FACE_CASCADE = None
_CASCADE_FAILED = False

def _get_face_cascade():
    """CascadeClassifier'ı lazy olarak yükler; hata varsa None döner."""
    global FACE_CASCADE, _CASCADE_FAILED
    if FACE_CASCADE is not None:
        return FACE_CASCADE
    if _CASCADE_FAILED:
        return None
    try:
        cascade_path = cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        cascade = cv2.CascadeClassifier(cascade_path)
        if cascade.empty():
            logger.warning("[ObserverDaemon] Haar cascade dosyası boş veya bulunamadı. Yüz algılama devre dışı.")
            _CASCADE_FAILED = True
            return None
        FACE_CASCADE = cascade
        return FACE_CASCADE
    except Exception as exc:
        logger.warning(f"[ObserverDaemon] Yüz algılama modülü yüklenemedi, atlanıyor ({exc})")
        _CASCADE_FAILED = True
        return None




class ObserverDaemon:
    """Webcam üzerinden ortamı izleyen, varlık ve ruh halini raporlayan daemon."""

    def __init__(
        self,
        patrol_interval: float = DEFAULT_PATROL_INTERVAL,
        mood_interval: float = MOOD_ANALYSIS_INTERVAL,
        camera_index: int = 0,
    ):
        self.patrol_interval = patrol_interval
        self.mood_interval = mood_interval
        self.camera_index = camera_index

        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._presence: bool = False          # mevcut varlık durumu
        self._consecutive_empty: int = 0     # ardışık boş kare sayacı
        self._last_mood_time: float = 0.0    # son Gemini çağrısının zamanı
        self._last_mood: str = "bilinmiyor"  # son ruh hali

    # ── Başlat / Durdur ───────────────────────────────────────────────────────

    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop, name="ObserverDaemon", daemon=True
        )
        self._thread.start()
        logger.info("[Observer] 👁️ Çevresel farkındalık devriyesi başlatıldı.")

    def stop(self):
        self._running = False
        logger.info("[Observer] 👁️ Devriye durduruldu.")

    # ── Ana döngü ─────────────────────────────────────────────────────────────

    def _loop(self):
        while self._running:
            try:
                self._tick()
            except Exception as exc:
                logger.debug(f"[Observer] Döngü hatası: {exc}")
            time.sleep(self.patrol_interval)

    def _tick(self):
        frame_b64 = self._capture_frame()
        if frame_b64 is None:
            return  # Kamera açılamadı — sessizce geç

        face_detected = self._detect_face_local(frame_b64)

        if face_detected:
            self._consecutive_empty = 0
            if not self._presence:
                # Kullanıcı yeni geldi
                self._presence = True
                logger.info("[Observer] 👤 Kullanıcı tespit edildi.")
                bus.publish("observer_presence", {"present": True})

            # Ruh hali analizi — API'yi çok sık çağırmamak için throttle
            now = time.time()
            if now - self._last_mood_time >= self.mood_interval:
                self._last_mood_time = now
                mood = self._analyze_mood_gemini(frame_b64)
                if mood:
                    self._last_mood = mood
                    logger.info(f"[Observer] 😊 Ruh hali: {mood}")
                    bus.publish("observer_mood", {"mood": mood})
        else:
            self._consecutive_empty += 1
            if self._presence and self._consecutive_empty >= PRESENCE_LOST_THRESHOLD:
                self._presence = False
                logger.info("[Observer] 🚶 Kullanıcı ayrıldı.")
                bus.publish("observer_presence", {"present": False})

    # ── Kamera yardımcıları ───────────────────────────────────────────────────

    def _capture_frame(self) -> Optional[str]:
        """Webcam'den tek kare yakalar, base64 JPEG döner. Hata varsa None."""
        try:
            cap = cv2.VideoCapture(self.camera_index, cv2.CAP_DSHOW)
            if not cap.isOpened():
                return None
            ret, frame = cap.read()
            cap.release()
            if not ret or frame is None:
                return None
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
            return base64.b64encode(buf.tobytes()).decode("utf-8")
        except Exception as exc:
            logger.debug(f"[Observer] Kare yakalama hatası: {exc}")
            return None

    def _detect_face_local(self, frame_b64: str) -> bool:
        """Lokal Haar cascade ile yüz tespiti — API çağrısı yok, hızlı."""
        try:
            cascade = _get_face_cascade()
            if cascade is None:
                return False
            img_bytes = base64.b64decode(frame_b64)
            import numpy as np
            arr = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
            faces = cascade.detectMultiScale(img, scaleFactor=1.1, minNeighbors=5)
            return len(faces) > 0
        except Exception:
            return False


    def _analyze_mood_gemini(self, frame_b64: str) -> Optional[str]:
        """Yüz varken Gemini Vision'a kısa ruh hali sorusu gönderir."""
        try:
            from orchestrator.gemini_reasoning import query_gemini_reasoning

            prompt = (
                "Bu kişinin yüz ifadesine bakarak ruh halini 3-5 kelimeyle özetle. "
                "Sadece Türkçe sıfat/ifade yaz, başka açıklama ekleme. "
                "Örnek: 'yorgun ve düşünceli', 'mutlu ve enerjik', 'stresli görünüyor'."
            )
            # Bazı versiyonlarda görüntü base64'ü desteklenmeyebilir — text-only fallback
            result = query_gemini_reasoning(
                prompt,
                image_base64=frame_b64,
                image_mime="image/jpeg",
            )
            return result.strip() if result else None
        except Exception as exc:
            logger.debug(f"[Observer] Gemini Vision hatası: {exc}")
            return None

    @property
    def current_presence(self) -> bool:
        return self._presence

    @property
    def current_mood(self) -> str:
        return self._last_mood


# Global singleton
observer_daemon = ObserverDaemon()
