"""
ULTRON Computer Awareness — Screen Analyzer Module
──────────────────────────────────────────────────
• Yerel ekran analizi, UI öğesi tespiti ve hata algılama
• Ekran değişmediğinde gereksiz AI/Vision çağrısı yapmama (Local Change Gating)
• OCR / Yerel Metin çıkarma ve ComputerState senkronizasyonu
"""

from __future__ import annotations

import logging
import os
import re
import time
from typing import Any

import cv2
import numpy as np
from PIL import Image

from computer.screen_capture import capture_screen, has_screen_changed, compute_image_dhash
from computer.window_manager import get_active_window_info, list_visible_windows
from computer.computer_state import current_computer_state, UIElement

logger = logging.getLogger("ultron.computer.screen_analyzer")

_last_analyzed_hash: int | None = None
_cached_screen_analysis: dict[str, Any] = {}


def detect_ui_bounding_boxes(image: Image.Image) -> list[dict[str, Any]]:
    """
    OpenCV ile ekrandaki buton, giriş kutusu ve pencerelerin yaklaşık sınırlarını yerel tespit eder.
    Aşırı hızlıdır (< 10ms), API token tüketmez.
    """
    try:
        img_np = np.array(image.convert("RGB"))
        gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        edges = cv2.Canny(blurred, 50, 150)

        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        elements = []

        h, w = gray.shape
        for cnt in contours:
            x, y, bw, bh = cv2.boundingRect(cnt)
            # Küçük gürültüleri ve devasa ekran boyutunu filtrele
            if (30 <= bw <= 600) and (15 <= bh <= 200) and (bw * bh < (w * h * 0.5)):
                elements.append({
                    "x": int(x),
                    "y": int(y),
                    "width": int(bw),
                    "height": int(bh),
                    "center_x": int(x + bw // 2),
                    "center_y": int(y + bh // 2)
                })

        # En belirgin 25 kutuyu döndür
        elements.sort(key=lambda b: b["width"] * b["height"], reverse=True)
        return elements[:25]
    except Exception as e:
        logger.debug(f"UI kutusu tespiti hatasi: {e}")
        return []


def analyze_current_screen(user_question: str = "", force_vision: bool = False) -> dict[str, Any]:
    """
    Ekranı yakalar, yerel değişiklikleri kontrol eder ve özetler.
    Gereksiz durumlarda Vision çağrısı yapmaz.
    """
    global _last_analyzed_hash, _cached_screen_analysis

    # 1. Ekranı ve aktif pencereyi al
    img = capture_screen(all_screens=False)
    win_info = get_active_window_info()
    current_hash = compute_image_dhash(img)

    # 2. Değişim ve önbellek kontrolü
    is_changed = (current_hash != _last_analyzed_hash)
    if not is_changed and not force_vision and _cached_screen_analysis and not user_question:
        logger.info("[Computer] Ekran değişmedi, önbellekteki analiz kullanılıyor.")
        return _cached_screen_analysis

    _last_analyzed_hash = current_hash

    # 3. Yerel UI Kutu Tespiti
    ui_boxes = detect_ui_bounding_boxes(img)

    # 4. ComputerState Güncelle
    current_computer_state.set_active_window(
        title=win_info.get("title", ""),
        process=win_info.get("process", ""),
        pid=win_info.get("pid", 0)
    )
    current_computer_state.update(
        screen_resolution=img.size,
        visible_buttons=ui_boxes,
        last_screen_change_time=time.time()
    )

    # 5. Görsel / Vision İhtiyacı Kontrolü
    # Kullanıcı açıkça 'ekranda ne var', 'oku', 'görsel incele' dediyse veya force_vision ise
    needs_deep_vision = force_vision or bool(re.search(
        r"(ne\s+var|gorunuyor|ekrani\s+gor|oku|incele|grafik|hata\s+var\s+mi)",
        user_question.lower()
    ))

    analysis_text = ""
    if needs_deep_vision:
        try:
            from actions.screen_vision import analyze_screen
            prompt = user_question or (
                "Ekrandaki ana uygulamayı, görünür metinleri, başlıkları ve varsa hata mesajlarını "
                "kısa ve net bir şekilde 2-3 cümleyle özetle."
            )
            print(f"[Computer] 👁️ Ekran analizi için derin görsel analiz çağrılıyor...", flush=True)
            vision_result = analyze_screen(query=prompt)
            if vision_result and not vision_result.startswith("Hata:"):
                analysis_text = vision_result
        except Exception as e:
            logger.error(f"Vision analizi sirasinda hata: {e}")

    if not analysis_text:
        # Yerel sentez (Zero-Token / Local)
        active_title = win_info.get("title", "")
        active_proc = win_info.get("process", "")
        analysis_text = f"Şu anda ekranda '{active_title or active_proc or 'Masaüstü'}' açık."
        if active_proc:
            analysis_text += f" (Uygulama: {active_proc})"

    result = {
        "active_window": win_info,
        "ui_boxes_count": len(ui_boxes),
        "summary": analysis_text,
        "is_changed": is_changed,
        "timestamp": time.time()
    }

    _cached_screen_analysis = result
    current_computer_state.update(last_analysis_summary=analysis_text)
    return result
