"""
ULTRON Computer Awareness — Keyboard Controller Module
──────────────────────────────────────────────────────
• Windows yerel ctypes / SendInput & keybd_event klavye kontrolü
• Unicode metin yazma (Türkçe karakter ve sembol desteği)
• Özel tuşlar (Enter, Tab, Esc, Win, Ctrl, Alt, Shift, Oklar)
• Kısayol kombinasyonları (hotkeys: ctrl+c, alt+tab, win+r vb.)
• Pano (Clipboard) korumalı yapıştırma (paste_text)
"""

from __future__ import annotations

import ctypes
from ctypes import wintypes
import logging
import time
from typing import Any

logger = logging.getLogger("ultron.computer.keyboard_controller")

user32 = ctypes.windll.user32

# Win32 Klavye Olay Bayrakları
KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

INPUT_KEYBOARD = 1

# Sanal Tuş Kodları (Virtual-Key Codes)
VK_MAP = {
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "space": 0x20,
    "backspace": 0x08,
    "delete": 0x2E,
    "del": 0x2E,
    "escape": 0x1B,
    "esc": 0x1B,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "win": 0x5B,
    "windows": 0x5B,
    "capslock": 0x14,
    "f1": 0x70,
    "f2": 0x71,
    "f3": 0x72,
    "f4": 0x73,
    "f5": 0x74,
    "f6": 0x75,
    "f7": 0x76,
    "f8": 0x77,
    "f9": 0x78,
    "f10": 0x79,
    "f11": 0x7A,
    "f12": 0x7B,
}


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ('wVk', wintypes.WORD),
        ('wScan', wintypes.WORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_void_p)
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ('uMsg', wintypes.DWORD),
        ('wParamL', wintypes.WORD),
        ('wParamH', wintypes.WORD)
    ]


class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ('dx', wintypes.LONG),
        ('dy', wintypes.LONG),
        ('mouseData', wintypes.DWORD),
        ('dwFlags', wintypes.DWORD),
        ('time', wintypes.DWORD),
        ('dwExtraInfo', ctypes.c_void_p)
    ]


class _INPUTunion(ctypes.Union):
    _fields_ = [
        ('mi', MOUSEINPUT),
        ('ki', KEYBDINPUT),
        ('hi', HARDWAREINPUT)
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ('type', wintypes.DWORD),
        ('union', _INPUTunion)
    ]


def _send_unicode_char(char: str) -> None:
    """Tek bir karakteri SendInput ile unicode olarak basar."""
    code = ord(char)
    inp_down = INPUT()
    inp_down.type = INPUT_KEYBOARD
    inp_down.union.ki.wVk = 0
    inp_down.union.ki.wScan = code
    inp_down.union.ki.dwFlags = KEYEVENTF_UNICODE

    inp_up = INPUT()
    inp_up.type = INPUT_KEYBOARD
    inp_up.union.ki.wVk = 0
    inp_up.union.ki.wScan = code
    inp_up.union.ki.dwFlags = KEYEVENTF_UNICODE | KEYEVENTF_KEYUP

    inputs = (INPUT * 2)(inp_down, inp_up)
    user32.SendInput(2, inputs, ctypes.sizeof(INPUT))


def type_text(text: str, delay_per_char: float = 0.01) -> bool:
    """Metni klavyeden yazılmış gibi güvenle ekrana basar."""
    if not text:
        return False

    for char in text:
        if char == "\n":
            press_key("enter")
        elif char == "\t":
            press_key("tab")
        else:
            _send_unicode_char(char)
        if delay_per_char > 0:
            time.sleep(delay_per_char)
    return True


def press_key(key_name: str) -> bool:
    """Tek bir özel tuşa basıp bırakır."""
    name = key_name.lower().strip()
    vk = VK_MAP.get(name)
    if not vk:
        if len(name) == 1:
            _send_unicode_char(name)
            return True
        return False

    user32.keybd_event(vk, 0, 0, 0)
    time.sleep(0.03)
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    return True


def key_down(key_name: str) -> bool:
    """Tuşa basılı tutar."""
    name = key_name.lower().strip()
    vk = VK_MAP.get(name)
    if not vk:
        return False
    user32.keybd_event(vk, 0, 0, 0)
    return True


def key_up(key_name: str) -> bool:
    """Basılı tuşu bırakır."""
    name = key_name.lower().strip()
    vk = VK_MAP.get(name)
    if not vk:
        return False
    user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
    return True


def hotkey(*keys: str) -> bool:
    """
    Kısayol tuş kombinasyonunu çalıştırır (örn: hotkey('ctrl', 'c') veya hotkey('ctrl', 'shift', 'esc')).
    """
    if not keys:
        return False

    # Tüm tuşları sırayla bas
    pressed = []
    for k in keys:
        name = k.lower().strip()
        vk = VK_MAP.get(name)
        if not vk and len(name) == 1:
            vk = ord(name.upper())
        if vk:
            user32.keybd_event(vk, 0, 0, 0)
            pressed.append(vk)
            time.sleep(0.02)

    time.sleep(0.05)

    # Ters sırayla bırak
    for vk in reversed(pressed):
        user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.01)

    return True


def paste_text(text: str, preserve_clipboard: bool = True) -> bool:
    """
    Metni panoya koyup Ctrl+V ile yapıştırır.
    preserve_clipboard=True ise işlemden sonra orijinal pano içeriğini geri yükler.
    """
    try:
        from actions.clipboard_tools import get_clipboard, set_clipboard
        original = get_clipboard() if preserve_clipboard else ""
    except Exception:
        original = ""

    try:
        from actions.clipboard_tools import set_clipboard
        set_clipboard(text)
        time.sleep(0.05)
        hotkey("ctrl", "v")
        time.sleep(0.08)

        if preserve_clipboard and original:
            set_clipboard(original)
        return True
    except Exception as e:
        logger.error(f"Pano yapistirma hatasi, type_text deneniyor: {e}")
        return type_text(text)
