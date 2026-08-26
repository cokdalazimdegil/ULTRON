"""
ULTRON Computer Awareness — Mouse Controller Module
───────────────────────────────────────────────────
• Windows yerel ctypes / user32 fare kontrolü
• Tıklama (sol, sağ, çift, orta), sürükleme (drag) ve kaydırma (scroll)
• Ekran sınırları güvenliği (Coordinate bounds checking)
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import time
from typing import Any

from computer.screen_capture import get_virtual_screen_bounds

logger = logging.getLogger("ultron.computer.mouse_controller")

user32 = ctypes.windll.user32

# Win32 Fare Olay Bayrakları
MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000


class POINT(ctypes.Structure):
    _fields_ = [('x', ctypes.c_long), ('y', ctypes.c_long)]


def get_mouse_position() -> tuple[int, int]:
    """İmlecin anlık masaüstü koordinatlarını döner (x, y)."""
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def _clamp_coordinates(x: int, y: int) -> tuple[int, int]:
    """Koordinatların ekran sınırları içinde kalmasını sağlar."""
    vl, vt, vw, vh = get_virtual_screen_bounds()
    clamped_x = max(vl, min(vl + vw - 1, x))
    clamped_y = max(vt, min(vt + vh - 1, y))
    return clamped_x, clamped_y


def move_mouse(x: int, y: int, smooth: bool = False) -> bool:
    """İmleci hedef koordinata taşır."""
    target_x, target_y = _clamp_coordinates(x, y)
    if not smooth:
        user32.SetCursorPos(target_x, target_y)
        return True

    # Pürüzsüz taşıma
    curr_x, curr_y = get_mouse_position()
    steps = 15
    for i in range(1, steps + 1):
        step_x = int(curr_x + (target_x - curr_x) * (i / steps))
        step_y = int(curr_y + (target_y - curr_y) * (i / steps))
        user32.SetCursorPos(step_x, step_y)
        time.sleep(0.01)
    user32.SetCursorPos(target_x, target_y)
    return True


def click(x: int | None = None, y: int | None = None, button: str = "left") -> bool:
    """Belirtilen koordinata veya imlecin olduğu yere tıklar."""
    if x is not None and y is not None:
        move_mouse(x, y)
        time.sleep(0.05)

    btn = button.lower().strip()
    if btn in ("left", "sol", "primary"):
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    elif btn in ("right", "sag", "secondary"):
        user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)
    elif btn in ("middle", "orta"):
        user32.mouse_event(MOUSEEVENTF_MIDDLEDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(MOUSEEVENTF_MIDDLEUP, 0, 0, 0, 0)
    else:
        return False
    return True


def double_click(x: int | None = None, y: int | None = None) -> bool:
    """Çift tıklar."""
    if x is not None and y is not None:
        move_mouse(x, y)
        time.sleep(0.05)
    click(button="left")
    time.sleep(0.08)
    click(button="left")
    return True


def right_click(x: int | None = None, y: int | None = None) -> bool:
    """Sağ tıklar."""
    return click(x, y, button="right")


def scroll(amount: int, x: int | None = None, y: int | None = None) -> bool:
    """
    Fare tekerleğini kaydırır. Pozitif = yukarı, negatif = aşağı.
    """
    if x is not None and y is not None:
        move_mouse(x, y)
    # Windows tekerlek adımı genellikle 120 birimdir
    wheel_delta = int(amount * 120)
    user32.mouse_event(MOUSEEVENTF_WHEEL, 0, 0, wheel_delta, 0)
    return True


def drag(start_x: int, start_y: int, end_x: int, end_y: int, duration_sec: float = 0.5) -> bool:
    """Bir noktadan diğerine basılı tutarak sürükler."""
    move_mouse(start_x, start_y)
    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
    time.sleep(0.05)

    steps = max(10, int(duration_sec * 30))
    for i in range(1, steps + 1):
        step_x = int(start_x + (end_x - start_x) * (i / steps))
        step_y = int(start_y + (end_y - start_y) * (i / steps))
        user32.SetCursorPos(step_x, step_y)
        time.sleep(duration_sec / steps)

    time.sleep(0.05)
    user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    return True
