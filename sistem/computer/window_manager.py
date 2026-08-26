"""
ULTRON Computer Awareness — Window Manager Module
─────────────────────────────────────────────────
• Windows yerel pencere yönetimi (Win32 & ctypes)
• Aktif pencere ve çalışan görsel uygulamaların tespiti
• Pencere odaklama (focus), küçültme (minimize), büyütme (maximize) ve kapatma
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import re
from typing import Any

import psutil

logger = logging.getLogger("ultron.computer.window_manager")

user32 = ctypes.windll.user32


class RECT(ctypes.Structure):
    _fields_ = [
        ('left', wintypes.LONG),
        ('top', wintypes.LONG),
        ('right', wintypes.LONG),
        ('bottom', wintypes.LONG)
    ]


def get_active_window_info() -> dict[str, Any]:
    """Şu anda odakta olan (foreground) pencerenin detaylı bilgilerini döner."""
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return {"hwnd": 0, "title": "", "process": "", "pid": 0, "rect": None}

    # Başlık al
    length = user32.GetWindowTextLengthW(hwnd)
    title = ""
    if length > 0:
        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value.strip()

    # PID ve Process al
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    process_name = ""
    try:
        if pid.value > 0:
            process_name = psutil.Process(pid.value).name()
    except Exception:
        process_name = "unknown"

    # Koordinat sınırları
    rect = RECT()
    user32.GetWindowRect(hwnd, ctypes.byref(rect))
    rect_tuple = (rect.left, rect.top, rect.right, rect.bottom)

    return {
        "hwnd": hwnd,
        "title": title,
        "process": process_name,
        "pid": pid.value,
        "rect": rect_tuple
    }


def list_visible_windows() -> list[dict[str, Any]]:
    """Masaüstündeki tüm görünür üst düzey pencereleri listeler."""
    windows: list[dict[str, Any]] = []

    WNDENUMPROC = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    def enum_proc(hwnd: int, lparam: int) -> bool:
        if not user32.IsWindowVisible(hwnd):
            return True

        length = user32.GetWindowTextLengthW(hwnd)
        if length <= 0:
            return True

        buff = ctypes.create_unicode_buffer(length + 1)
        user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value.strip()

        # Sistem içi boş veya özel pencereleri ele
        if not title or title in ("Program Manager", "Settings", "Windows Input Experience"):
            return True

        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_name = ""
        try:
            if pid.value > 0:
                process_name = psutil.Process(pid.value).name()
        except Exception:
            process_name = "unknown"

        rect = RECT()
        user32.GetWindowRect(hwnd, ctypes.byref(rect))
        w = rect.right - rect.left
        h = rect.bottom - rect.top

        # Çok küçük veya gizli pencereleri ele
        if w > 30 and h > 30:
            windows.append({
                "hwnd": hwnd,
                "title": title,
                "process": process_name,
                "pid": pid.value,
                "rect": (rect.left, rect.top, rect.right, rect.bottom),
                "width": w,
                "height": h
            })
        return True

    user32.EnumWindows(WNDENUMPROC(enum_proc), 0)
    return windows


def find_window(query: str) -> dict[str, Any] | None:
    """Başlık veya işlem adına göre en uygun pencereyi bulur."""
    query_clean = query.lower().strip()
    windows = list_visible_windows()

    # 1. Tam eşleşme
    for w in windows:
        if query_clean == w["title"].lower() or query_clean == w["process"].lower().replace(".exe", ""):
            return w

    # 2. İçerir eşleşmesi
    for w in windows:
        if query_clean in w["title"].lower() or query_clean in w["process"].lower():
            return w

    return None


def focus_window(title_or_query: str) -> bool:
    """Belirtilen pencereyi öne getirir ve odaklar."""
    target = find_window(title_or_query)
    if not target:
        return False

    hwnd = target["hwnd"]
    try:
        # SW_RESTORE = 9, SW_SHOW = 5
        user32.ShowWindow(hwnd, 9)
        user32.SetForegroundWindow(hwnd)
        return True
    except Exception as e:
        logger.error(f"Pencere odaklama hatasi: {e}")
        return False


def minimize_window(title_or_query: str) -> bool:
    """Belirtilen pencereyi simge durumuna küçültür."""
    target = find_window(title_or_query)
    if not target:
        return False
    # SW_MINIMIZE = 6
    return bool(user32.ShowWindow(target["hwnd"], 6))


def maximize_window(title_or_query: str) -> bool:
    """Belirtilen pencereyi ekranı kaplayacak şekilde büyütür."""
    target = find_window(title_or_query)
    if not target:
        return False
    # SW_MAXIMIZE = 3
    return bool(user32.ShowWindow(target["hwnd"], 3))


def close_window(title_or_query: str) -> bool:
    """Belirtilen pencereyi kapatır (WM_CLOSE)."""
    target = find_window(title_or_query)
    if not target:
        return False
    # WM_CLOSE = 0x0010
    return bool(user32.PostMessageW(target["hwnd"], 0x0010, 0, 0))
