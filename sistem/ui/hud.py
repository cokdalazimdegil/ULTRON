"""
ULTRON — Desktop HUD ve Pencere Döngüsü (HUD Module)
DesktopHUD penceresi, PyWebView loop entegrasyonu ve Tkinter arayüz köprüsü.
"""

import logging
from typing import Optional

logger = logging.getLogger("ultron.ui.hud")

# DesktopHUD sınıfını computer.desktop_hud üzerinden doğrudan dışa aktar
try:
    from computer.desktop_hud import DesktopHUD, desktop_hud
except ImportError:
    DesktopHUD = None
    desktop_hud = None

# Geriye dönük uyumluluk için UltronUI
try:
    from ui import UltronUI
except ImportError:
    UltronUI = None

__all__ = ["DesktopHUD", "desktop_hud", "UltronUI"]
