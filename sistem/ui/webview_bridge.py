"""
ULTRON — Webview Bridge (JS-Python Haberleşme Köprüsü)
PyWebview JS API köprüsü: Fullscreen, bildirimler ve yerel pencere kontrolleri.
"""

from typing import Any, Optional

_webview_window = None


class PyWebviewApi:
    """PyWebview JS API köprüsü: Fullscreen ve yerel pencere kontrolleri."""
    def __init__(self, window=None):
        global _webview_window
        if window is not None:
            _webview_window = window

    def set_window(self, window):
        global _webview_window
        _webview_window = window

    def toggle_fullscreen(self) -> bool:
        global _webview_window
        try:
            if _webview_window:
                _webview_window.toggle_fullscreen()
                return bool(_webview_window.fullscreen)
            return False
        except Exception:
            return False

    def is_fullscreen(self) -> bool:
        global _webview_window
        try:
            if _webview_window:
                return bool(_webview_window.fullscreen)
            return False
        except Exception:
            return False


__all__ = ["PyWebviewApi"]
