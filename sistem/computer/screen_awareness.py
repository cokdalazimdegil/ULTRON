"""
ULTRON Computer Vision & Screen Awareness 2.0 Engine
════════════════════════════════════════════════════
• 4 Seviyeli Ekran Değişim Sınıflandırması (NO_CHANGE, MINOR_CHANGE, SIGNIFICANT_CHANGE, MAJOR_CHANGE)
• Hiyerarşik Görsel Temsil: SCREEN -> ACTIVE_WINDOW -> REGIONS -> UI_ELEMENTS -> SEMANTIC_CONTEXT
• Yerel OCR & UI Kutu Tespiti (OpenCV + PIL)
• Aksiyon Doğrulama Döngüsü: ACTION -> OBSERVE -> VERIFY
• ULTRON World Model ile canlı senkronizasyon
"""

from __future__ import annotations

import logging
import os
import re
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

import cv2
import numpy as np
from PIL import Image

from computer.screen_capture import capture_screen, compute_image_dhash
from computer.window_manager import get_active_window_info, list_visible_windows
from computer.world_model import world_model, UncertaintyLevel

logger = logging.getLogger("ultron.computer.screen_awareness")


class ChangeSeverity(str, Enum):
    NO_CHANGE          = "NO_CHANGE"          # Değişiklik yok veya ihmal edilebilir (d <= 2)
    MINOR_CHANGE       = "MINOR_CHANGE"       # Küçük hareket, imleç, saat (2 < d <= 8)
    SIGNIFICANT_CHANGE = "SIGNIFICANT_CHANGE" # Menü, form girişi, terminal çıktısı (8 < d <= 20)
    MAJOR_CHANGE       = "MAJOR_CHANGE"       # Pencere değişimi, modal dialog, sayfa yükleme (d > 20)


@dataclass
class UIElementBox:
    element_type: str  # button, input, dialog, text_block, icon, window
    x: int
    y: int
    width: int
    height: int
    center_x: int
    center_y: int
    text: str = ""
    confidence: float = 1.0


@dataclass
class VisualScreenContext:
    timestamp: float
    screen_resolution: tuple[int, int]
    change_severity: ChangeSeverity
    hamming_distance: int
    active_window: dict[str, Any]
    visible_windows: list[dict[str, Any]]
    ui_elements: list[UIElementBox]
    detected_texts: list[str]
    has_modal_dialog: bool
    has_error_box: bool
    summary: str
    dhash: int


class ScreenAwarenessEngine:
    """Ekranı hiyerarşik ve akıllı olarak analiz eden Vision 2.0 Motoru."""

    def __init__(self):
        self._last_hash: int | None = None
        self._last_capture_time: float = 0.0
        self._last_context: VisualScreenContext | None = None

    def calculate_hamming_distance(self, hash1: int, hash2: int) -> int:
        """İki 64-bit perceptual hash arasındaki Hamming mesafesini hesaplar."""
        x = (hash1 ^ hash2) & 0xFFFFFFFFFFFFFFFF
        return bin(x).count("1")

    def classify_screen_change(self, current_hash: int) -> tuple[ChangeSeverity, int]:
        """Ekrandaki değişimin şiddetini sınıflandırır."""
        if self._last_hash is None:
            return ChangeSeverity.MAJOR_CHANGE, 64

        dist = self.calculate_hamming_distance(self._last_hash, current_hash)
        if dist <= 2:
            return ChangeSeverity.NO_CHANGE, dist
        elif dist <= 8:
            return ChangeSeverity.MINOR_CHANGE, dist
        elif dist <= 20:
            return ChangeSeverity.SIGNIFICANT_CHANGE, dist
        else:
            return ChangeSeverity.MAJOR_CHANGE, dist

    def detect_ui_elements(self, image: Image.Image) -> list[UIElementBox]:
        """OpenCV ile ekrandaki buton, giriş kutusu ve pencerelerin konumlarını tespit eder."""
        try:
            img_np = np.array(image.convert("RGB"))
            gray = cv2.cvtColor(img_np, cv2.COLOR_RGB2GRAY)
            blurred = cv2.GaussianBlur(gray, (5, 5), 0)
            edges = cv2.Canny(blurred, 40, 140)

            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            elements: list[UIElementBox] = []

            h, w = gray.shape
            for cnt in contours:
                x, y, bw, bh = cv2.boundingRect(cnt)
                area = bw * bh

                # Filtreleme: Gürültüleri ve tam ekran boyutlarını ayıkla
                if (24 <= bw <= 700) and (14 <= bh <= 250) and (area < (w * h * 0.45)):
                    aspect_ratio = bw / float(bh)
                    if 1.5 <= aspect_ratio <= 8.0 and bh <= 60:
                        elem_type = "button"
                    elif aspect_ratio > 3.0 and bh <= 45:
                        elem_type = "input"
                    elif area > 15000:
                        elem_type = "dialog"
                    else:
                        elem_type = "ui_box"

                    elements.append(UIElementBox(
                        element_type=elem_type,
                        x=int(x),
                        y=int(y),
                        width=int(bw),
                        height=int(bh),
                        center_x=int(x + bw // 2),
                        center_y=int(y + bh // 2),
                        confidence=0.85
                    ))

            # En belirgin 30 öğeyi seç
            elements.sort(key=lambda e: e.width * e.height, reverse=True)
            return elements[:30]
        except Exception as e:
            logger.debug(f"UI element tespit hatası: {e}")
            return []

    def observe_screen(self, force_full_analysis: bool = False) -> VisualScreenContext:
        """
        Ekranı yakalar, değişim seviyesini belirler, aktif pencere ve UI öğelerini yapılandırır.
        World Model'i otomatik günceller.
        """
        img = capture_screen(all_screens=False)
        current_hash = compute_image_dhash(img)
        severity, dist = self.classify_screen_change(current_hash)

        # Aktif pencere ve görünür pencereler
        win_info = get_active_window_info()
        vis_windows = list_visible_windows()

        # UI Elementleri
        ui_elements = self.detect_ui_elements(img)

        # Modal Dialog ve Hata Kontrolü
        active_title = win_info.get("title", "")
        has_modal = any(w in active_title.lower() for w in ("uyarı", "hata", "dialog", "confirm", "alert", "error", "onay"))
        has_error = any(w in active_title.lower() for w in ("error", "hata", "exception", "failed", "crash", "başarısız"))

        # Görsel Özet
        summary = f"Aktif Pencere: '{active_title or 'Masaüstü'}' (Değişim: {severity.value}, Mesafe: {dist})"
        if has_modal:
            summary += " [⚠️ Modal Dialog Açık]"
        if has_error:
            summary += " [🚨 Hata Bildirimi]"

        context = VisualScreenContext(
            timestamp=time.time(),
            screen_resolution=img.size,
            change_severity=severity,
            hamming_distance=dist,
            active_window=win_info,
            visible_windows=vis_windows,
            ui_elements=ui_elements,
            detected_texts=[],
            has_modal_dialog=has_modal,
            has_error_box=has_error,
            summary=summary,
            dhash=current_hash
        )

        # World Model Senkronizasyonu
        self._last_hash = current_hash
        self._last_capture_time = time.time()
        self._last_context = context

        world_model.update_active_window(
            hwnd=win_info.get("hwnd", 0),
            title=active_title,
            process_name=win_info.get("process", ""),
            pid=win_info.get("pid", 0),
            bounds=win_info.get("bounds", (0, 0, img.size[0], img.size[1]))
        )
        world_model.last_screen_hash = current_hash

        return context

    def verify_action_effect(self, expected_change_type: str, target_window_keyword: str = "",
                             timeout: float = 4.0, interval: float = 0.4) -> dict[str, Any]:
        """
        Bir bilgisayar aksiyonunun (uygulama açma, tıklama, pencere odağı vb.) ekranda
        gerçekten beklenen etkiyi yaratıp yaratmadığını doğrular (Action -> Observe -> Verify).
        """
        start = time.time()
        initial_hash = self._last_hash or 0
        initial_window = world_model.active_window.title

        while (time.time() - start) < timeout:
            time.sleep(interval)
            ctx = self.observe_screen(force_full_analysis=True)

            # 1. Pencere Açılma / Odaklanma Doğrulaması
            if target_window_keyword:
                kw = target_window_keyword.lower().strip()
                if kw in ctx.active_window.get("title", "").lower() or kw in ctx.active_window.get("process", "").lower():
                    return {
                        "verified": True,
                        "reason": f"Hedef pencere '{target_window_keyword}' başarıyla ekranda odaklandı.",
                        "severity": ctx.change_severity.value,
                        "elapsed_sec": round(time.time() - start, 2)
                    }

            # 2. Görsel Değişim Doğrulaması
            if expected_change_type == "ANY_CHANGE":
                if ctx.change_severity in (ChangeSeverity.SIGNIFICANT_CHANGE, ChangeSeverity.MAJOR_CHANGE):
                    return {
                        "verified": True,
                        "reason": "Ekranda beklenen görsel değişiklik doğrulandı.",
                        "severity": ctx.change_severity.value,
                        "elapsed_sec": round(time.time() - start, 2)
                    }

        return {
            "verified": False,
            "reason": f"Zaman aşımı ({timeout}s): Beklenen görsel etki ('{expected_change_type}') veya pencere ('{target_window_keyword}') ekranda tespit edilemedi.",
            "severity": ChangeSeverity.NO_CHANGE.value,
            "elapsed_sec": round(time.time() - start, 2)
        }


# Global Screen Awareness 2.0 Singleton
screen_awareness = ScreenAwarenessEngine()
