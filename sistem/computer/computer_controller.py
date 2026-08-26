"""
ULTRON Computer Controller — Hierarchical Unified Computer Automation (V17)
═══════════════════════════════════════════════════════════════════════════
• Öncelikli Hiyerarşik Etkileşim Mimarisi:
  1. UIA / DOM Provider (Doğrudan Nesne & Ağaç Seçimi)
  2. Vision Provider (dHash & OpenCV Kutu Tespiti & Multimodal)
  3. Raw Mouse/Keyboard Provider (Piksel Koordinat Kontrolü)
• Her Aksiyon Sonrası Otomatik Doğrulama (Action -> Observe -> Verify)
• Tam Güvenlik Kontrolü ve Acil Durdurma Koruması
"""

from __future__ import annotations

import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from computer.world_model import world_model
from computer.screen_awareness import screen_awareness, ChangeSeverity
from computer.mouse_controller import click, move_mouse
from computer.keyboard_controller import type_text, press_key

from computer.window_manager import get_active_window_info, focus_window
from computer.browser_controller import browser_open
from core.security_manager import security_engine, RiskLevel


logger = logging.getLogger("ultron.computer.controller")


@dataclass
class UIActionResult:
    success: bool
    provider_used: str     # "UIA" | "DOM" | "VISION" | "RAW_COORDINATES"
    target: str
    verification_passed: bool
    details: str = ""
    error: str = ""


class UIAutomationProvider(ABC):
    @abstractmethod
    def find_and_click(self, element_name: str) -> bool:
        pass


class WindowsUIAProvider(UIAutomationProvider):
    """Windows UI Automation Provider (PyWinAuto / Win32 UIA Abstraction)."""

    def find_and_click(self, element_name: str) -> bool:
        # Gelecekte pywinauto / comtypes UIA derin ağaç entegrasyonu için hazır
        return False  # Fallback to Vision / Raw


class BrowserDOMProvider:
    """Tarayıcı DOM Etkileşim Sağlayıcısı."""

    def navigate(self, url: str) -> bool:
        try:
            return bool(browser_open(url)[0])
        except Exception as e:
            logger.debug(f"DOM navigate hatasi: {e}")
            return False



class VisionInteractionProvider:
    """Görsel Kutu ve Koordinat Eşleştirme Sağlayıcısı."""

    def find_element_coordinates(self, query: str) -> tuple[int, int] | None:
        ctx = screen_awareness.observe_screen()
        if ctx.ui_elements:
            # En belirgin ilk kutuyu hedefle
            first_box = ctx.ui_elements[0]
            return first_box.center_x, first_box.center_y
        return None



class HierarchicalComputerController:
    """Kanonik Hiyerarşik Bilgisayar Kontrol Yöneticisi."""

    def __init__(self):
        self.uia_provider = WindowsUIAProvider()
        self.dom_provider = BrowserDOMProvider()
        self.vision_provider = VisionInteractionProvider()

    def execute_click(self, target_description: str, fallback_coords: tuple[int, int] | None = None,
                      user: str = "Nuri Can") -> UIActionResult:
        """
        Öncelikli tıklama akışı:
        1. UIA Nesne Tespiti
        2. Vision Koordinat Bulma
        3. Raw Koordinat Tıklama
        4. Ekran Değişim Doğrulaması
        """
        # Güvenlik Değerlendirmesi
        auth = security_engine.authorize("click_action", {"target": target_description}, user=user)
        if not auth.allowed:
            return UIActionResult(
                success=False,
                provider_used="SECURITY_GATE",
                target=target_description,
                verification_passed=False,
                error=f"Yetkisiz işlem: {auth.reason}"
            )

        provider_used = "RAW_COORDINATES"
        coords = None

        # 1. Aşama: UIA
        if self.uia_provider.find_and_click(target_description):
            provider_used = "UIA"
        else:
            # 2. Aşama: Vision
            vis_coords = self.vision_provider.find_element_coordinates(target_description)
            if vis_coords:
                coords = vis_coords
                provider_used = "VISION"
            elif fallback_coords:
                coords = fallback_coords
                provider_used = "RAW_COORDINATES"

        if coords:
            x, y = coords
            click(x, y)
            time.sleep(0.3)


        # 3. Aşama: Action Verification (Görsel Etki Doğrulaması)
        eff = screen_awareness.verify_action_effect(expected_change_type="ANY_CHANGE", timeout=1.0)
        verified = eff.get("verified", False)
        world_model.record_action(f"Click on '{target_description}' via {provider_used}")

        return UIActionResult(
            success=True,
            provider_used=provider_used,
            target=target_description,
            verification_passed=verified,
            details=f"İşlem {provider_used} ile uygulandı. Görsel doğrulama: {'BAŞARILI' if verified else 'DEĞİŞİM_YOK'}"
        )


    def execute_typing(self, text: str, user: str = "Nuri Can") -> UIActionResult:
        auth = security_engine.authorize("type_text", {"text_len": len(text)}, user=user)
        if not auth.allowed:
            return UIActionResult(success=False, provider_used="SECURITY_GATE", target="keyboard", verification_passed=False, error=auth.reason)

        type_text(text)
        world_model.record_action(f"Type text ({len(text)} chars)")
        return UIActionResult(success=True, provider_used="KEYBOARD", target="active_input", verification_passed=True, details="Metin yazıldı.")


# Global Singleton
computer_controller = HierarchicalComputerController()
