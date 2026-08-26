"""
ULTRON Computer Awareness — Screen Capture Module
─────────────────────────────────────────────────
• Yüksek verimli yerel Windows GDI / MSS / PIL ekran yakalama hiyerarşisi
• Çoklu monitör ve DPI farkındalığı (DPI-Aware)
• Bölge (Region) ve Pencere (Window) kırpma desteği
• Perceptual Hash (dHash) ile yerel ekran değişim tespiti (Local Change Detection)
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import io
import logging
import os
import time
from typing import Any

import numpy as np
from PIL import Image

logger = logging.getLogger("ultron.computer.screen_capture")

_dpi_initialized = False
_last_screen_hash: int | None = None
_last_capture_time: float = 0.0


def _init_dpi_awareness() -> None:
    global _dpi_initialized
    if _dpi_initialized:
        return
    _dpi_initialized = True
    try:
        # PER_MONITOR_AWARE_V2
        ctypes.windll.user32.SetProcessDpiAwarenessContext(-4)
        return
    except Exception:
        pass
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
        return
    except Exception:
        pass
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


def get_screen_resolution() -> tuple[int, int]:
    """Birincil ekran çözünürlüğünü döner (width, height)."""
    _init_dpi_awareness()
    try:
        user32 = ctypes.windll.user32
        w = user32.GetSystemMetrics(0)  # SM_CXSCREEN
        h = user32.GetSystemMetrics(1)  # SM_CYSCREEN
        return int(w), int(h)
    except Exception:
        return 1920, 1080


def get_virtual_screen_bounds() -> tuple[int, int, int, int]:
    """Çoklu monitör virtual desktop sınırlarını döner (left, top, width, height)."""
    _init_dpi_awareness()
    try:
        user32 = ctypes.windll.user32
        left = user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
        top = user32.GetSystemMetrics(77)   # SM_YVIRTUALSCREEN
        width = user32.GetSystemMetrics(78) # SM_CXVIRTUALSCREEN
        height = user32.GetSystemMetrics(79)# SM_CYVIRTUALSCREEN
        return int(left), int(top), int(width), int(height)
    except Exception:
        w, h = get_screen_resolution()
        return 0, 0, w, h


def get_monitors() -> list[dict[str, Any]]:
    """Bağlı monitörlerin listesini döner."""
    monitors = []
    try:
        import mss
        with mss.mss() as sct:
            for idx, m in enumerate(sct.monitors):
                monitors.append({
                    "id": idx,
                    "left": m["left"],
                    "top": m["top"],
                    "width": m["width"],
                    "height": m["height"],
                    "is_all": idx == 0
                })
        if monitors:
            return monitors
    except Exception:
        pass

    # GDI fallback
    w, h = get_screen_resolution()
    vl, vt, vw, vh = get_virtual_screen_bounds()
    return [
        {"id": 0, "left": vl, "top": vt, "width": vw, "height": vh, "is_all": True},
        {"id": 1, "left": 0, "top": 0, "width": w, "height": h, "is_all": False}
    ]


def _capture_gdi_native(left: int, top: int, width: int, height: int) -> Image.Image:
    """Windows GDI native BitBlt ile en hızlı ve doğrudan bellek ekran görüntüsü alma."""
    _init_dpi_awareness()
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32

    hdesktop = user32.GetDesktopWindow()
    desktop_dc = user32.GetWindowDC(hdesktop)
    img_dc = gdi32.CreateCompatibleDC(desktop_dc)
    mem_bitmap = gdi32.CreateCompatibleBitmap(desktop_dc, width, height)
    old_bitmap = gdi32.SelectObject(img_dc, mem_bitmap)

    # SRCCOPY = 0x00CC0020
    gdi32.BitBlt(img_dc, 0, 0, width, height, desktop_dc, left, top, 0x00CC0020)

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [
            ('biSize', wintypes.DWORD),
            ('biWidth', wintypes.LONG),
            ('biHeight', wintypes.LONG),
            ('biPlanes', wintypes.WORD),
            ('biBitCount', wintypes.WORD),
            ('biCompression', wintypes.DWORD),
            ('biSizeImage', wintypes.DWORD),
            ('biXPelsPerMeter', wintypes.LONG),
            ('biYPelsPerMeter', wintypes.LONG),
            ('biClrUsed', wintypes.DWORD),
            ('biClrImportant', wintypes.DWORD)
        ]

    bmi = BITMAPINFOHEADER()
    bmi.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    bmi.biWidth = width
    bmi.biHeight = -height  # top-down DIB
    bmi.biPlanes = 1
    bmi.biBitCount = 32
    bmi.biCompression = 0

    buffer = ctypes.create_string_buffer(width * height * 4)
    gdi32.GetDIBits(img_dc, mem_bitmap, 0, height, buffer, ctypes.byref(bmi), 0)

    # Temizlik
    gdi32.SelectObject(img_dc, old_bitmap)
    gdi32.DeleteObject(mem_bitmap)
    gdi32.DeleteDC(img_dc)
    user32.ReleaseDC(hdesktop, desktop_dc)

    return Image.frombuffer('RGBA', (width, height), buffer, 'raw', 'BGRA', 0, 1).convert('RGB')


def capture_screen(all_screens: bool = False) -> Image.Image:
    """
    Ekran görüntüsü alır.
    all_screens=False ise birincil ekranı, True ise tüm monitörleri kapsar.
    """
    global _last_capture_time
    _init_dpi_awareness()

    if all_screens:
        left, top, width, height = get_virtual_screen_bounds()
    else:
        width, height = get_screen_resolution()
        left, top = 0, 0

    # 1. Native Windows GDI
    try:
        img = _capture_gdi_native(left, top, width, height)
        _last_capture_time = time.time()
        return img
    except Exception as e:
        logger.debug(f"Native GDI capture hatasi, fallback deneniyor: {e}")

    # 2. MSS Fallback
    try:
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[0] if all_screens else sct.monitors[1]
            shot = sct.grab(mon)
            img = Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
            _last_capture_time = time.time()
            return img
    except Exception as e:
        logger.debug(f"MSS capture hatasi, PIL deneniyor: {e}")

    # 3. PIL ImageGrab Fallback
    try:
        from PIL import ImageGrab
        img = ImageGrab.grab(all_screens=all_screens)
        _last_capture_time = time.time()
        return img
    except Exception as e:
        logger.error(f"Tum ekran yakalama yontemleri basarisiz: {e}")
        # En kotu durumda siyah placeholder
        return Image.new("RGB", (width or 1920, height or 1080), (0, 0, 0))


def capture_region(x: int, y: int, width: int, height: int) -> Image.Image:
    """Belirtilen koordinat ve boyuttaki ekran bölgesini kırparak yakalar."""
    if width <= 0 or height <= 0:
        width, height = max(1, width), max(1, height)

    try:
        return _capture_gdi_native(x, y, width, height)
    except Exception:
        full_img = capture_screen(all_screens=True)
        # Koordinatlara gore crop
        vl, vt, _, _ = get_virtual_screen_bounds()
        crop_x = x - vl
        crop_y = y - vt
        return full_img.crop((crop_x, crop_y, crop_x + width, crop_y + height))


# ═══════════════════════════════════════════════════════════════════════════
# Local Change Detection (Perceptual Hash - dHash)
# ═══════════════════════════════════════════════════════════════════════════

def compute_image_dhash(image: Image.Image, hash_size: int = 8) -> int:
    """
    Ekran görüntüsünün 64-bit fark özetini (dHash) hesaplar.
    Aşırı hızlıdır (< 2ms) ve renk/piksel gürültüsüne karşı dayanıklıdır.
    """
    try:
        # Grayscale ve (hash_size + 1, hash_size) boyutlandırma
        resized = image.convert("L").resize((hash_size + 1, hash_size), Image.Resampling.BILINEAR)
        pixels = np.array(resized)
        # Yan yana piksellerin farkı
        diff = pixels[:, 1:] > pixels[:, :-1]
        # 64-bit tamsayıya dönüştür
        hash_val = 0
        for bit in diff.flatten():
            hash_val = (hash_val << 1) | int(bit)
        return hash_val
    except Exception:
        return 0


def has_screen_changed(new_image: Image.Image, hamming_threshold: int = 3) -> bool:
    """
    Ekranın son analize göre değişip değişmediğini kontrol eder.
    Hamming mesafesi eşiğin altındaysa False döner (ekran değişmedi).
    """
    global _last_screen_hash
    current_hash = compute_image_dhash(new_image)

    if _last_screen_hash is None:
        _last_screen_hash = current_hash
        return True

    # Hamming mesafesi (farklı bit sayısı)
    xor_val = current_hash ^ _last_screen_hash
    diff_bits = bin(xor_val).count("1")

    if diff_bits >= hamming_threshold:
        _last_screen_hash = current_hash
        return True
    return False


def reset_screen_change_cache() -> None:
    """Ekran değişim önbelleğini sıfırlar."""
    global _last_screen_hash
    _last_screen_hash = None
