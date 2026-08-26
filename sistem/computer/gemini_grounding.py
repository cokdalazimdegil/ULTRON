"""
ULTRON Gemini Grounding Engine — Piksel Duzeyinde Eleman Tespiti (v1.0)
═══════════════════════════════════════════════════════════════════════
Gemini Vision kullanarak ekranda bir UI elemaninin koordinatini otomatik bulur.
Koordinat bilmeden dogal dil tarifiyle herhangi bir butona/alana tiklanabilir.

Ornek: "Tamam butonuna tikla" → Vision analiz → (x=1024, y=512) → pyautogui.click
"""

from __future__ import annotations

import base64
import json
import logging
import re
import time
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger("ultron.computer.gemini_grounding")


@dataclass
class GroundingResult:
    found: bool
    x: int = 0
    y: int = 0
    confidence: float = 0.0
    element_label: str = ""
    method: str = ""
    error: str = ""


class GeminiGrounder:
    """
    Ekran goruntusundeki bir UI elemanini Gemini Vision ile bulur.
    """

    GROUNDING_PROMPT = (
        "You are a UI element locator. I will give you a screenshot and a description of a UI element.\n"
        "Find the element and return ONLY a JSON object with this exact format:\n"
        '{"found": true, "x": <center_x_pixel>, "y": <center_y_pixel>, "label": "<element label>"}\n'
        "If not found, return: {\"found\": false}\n"
        "Do NOT explain. Return ONLY the JSON.\n\n"
        "Target element: {target_description}"
    )

    def __init__(self):
        self._api_key: str = ""
        self._screen_w: int = 1920
        self._screen_h: int = 1080

    def set_api_key(self, key: str) -> None:
        self._api_key = key.strip()

    def _get_screen_size(self) -> tuple[int, int]:
        try:
            import mss
            with mss.mss() as sct:
                mon = sct.monitors[1]
                return mon["width"], mon["height"]
        except Exception:
            return 1920, 1080

    def _capture_screenshot_b64(self) -> str | None:
        """Ekran goruntusunu base64 PNG olarak yakalar."""
        try:
            import mss
            import mss.tools
            with mss.mss() as sct:
                mon = sct.monitors[1]
                self._screen_w = mon["width"]
                self._screen_h = mon["height"]
                img = sct.grab(mon)
                from PIL import Image
                import io
                pil_img = Image.frombytes("RGB", img.size, img.bgra, "raw", "BGRX")
                # Scale down for faster API call
                max_side = 1280
                if pil_img.width > max_side or pil_img.height > max_side:
                    ratio = min(max_side / pil_img.width, max_side / pil_img.height)
                    new_w = int(pil_img.width * ratio)
                    new_h = int(pil_img.height * ratio)
                    pil_img = pil_img.resize((new_w, new_h))
                    # Store scale factors for coordinate correction
                    self._scale_x = pil_img.width / mon["width"]
                    self._scale_y = pil_img.height / mon["height"]
                else:
                    self._scale_x = 1.0
                    self._scale_y = 1.0
                buf = io.BytesIO()
                pil_img.save(buf, format="PNG", optimize=True)
                return base64.b64encode(buf.getvalue()).decode("utf-8")
        except Exception as e:
            logger.error(f"[Grounding] Screenshot hatasi: {e}")
            return None

    def _parse_response(self, text: str) -> dict[str, Any]:
        """Model yaniti icinden JSON ayristi."""
        # JSON blok icerisinde ara
        match = re.search(r"\{[^{}]+\}", text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group())
            except Exception:
                pass
        # Fallback: x= ve y= degerlerini regex ile ara
        x_match = re.search(r'"?x"?\s*:\s*(\d+)', text)
        y_match = re.search(r'"?y"?\s*:\s*(\d+)', text)
        found_match = re.search(r'"?found"?\s*:\s*(true|false)', text, re.IGNORECASE)
        if x_match and y_match:
            return {
                "found": (found_match.group(1).lower() == "true") if found_match else True,
                "x": int(x_match.group(1)),
                "y": int(y_match.group(1)),
                "label": "",
            }
        return {"found": False}

    def find_element(self, target_description: str,
                     screenshot_b64: str | None = None) -> GroundingResult:
        """
        Ekrandaki bir UI elemanini Gemini Vision ile bulur.

        Args:
            target_description: Aranacak elemanin dogal dil tarifi
                Ornek: "Tamam butonu", "arama kutusu", "kapat X dugmesi"
            screenshot_b64: Opsiyonel — None ise ekran otomatik yakalanir

        Returns:
            GroundingResult (found=True ise x, y gercek piksel koordinatlari)
        """
        if not self._api_key:
            try:
                from app_config import get_app_config_value
                self._api_key = get_app_config_value("gemini_api_key", "") or ""
            except Exception:
                pass

        if not self._api_key:
            return GroundingResult(found=False, error="API anahtari bulunamadi")

        if screenshot_b64 is None:
            screenshot_b64 = self._capture_screenshot_b64()
            if not screenshot_b64:
                return GroundingResult(found=False, error="Ekran goruntusu alinamadi")

        prompt = self.GROUNDING_PROMPT.format(target_description=target_description)

        try:
            from google import genai
            from google.genai import types

            client = genai.Client(api_key=self._api_key)
            response = client.models.generate_content(
                model="gemini-2.0-flash",
                contents=[
                    types.Content(parts=[
                        types.Part(
                            inline_data=types.Blob(
                                data=base64.b64decode(screenshot_b64),
                                mime_type="image/png",
                            )
                        ),
                        types.Part(text=prompt),
                    ])
                ],
                config=types.GenerateContentConfig(
                    temperature=0.0,
                    max_output_tokens=128,
                ),
            )

            raw_text = response.text or ""
            parsed = self._parse_response(raw_text)

            if not parsed.get("found"):
                return GroundingResult(
                    found=False,
                    method="gemini_vision",
                    error=f"Eleman bulunamadi: {target_description!r}"
                )

            # Scale coordinates back to actual screen resolution
            raw_x = int(parsed.get("x", 0))
            raw_y = int(parsed.get("y", 0))
            scale_x = getattr(self, "_scale_x", 1.0)
            scale_y = getattr(self, "_scale_y", 1.0)
            actual_x = round(raw_x / scale_x) if scale_x else raw_x
            actual_y = round(raw_y / scale_y) if scale_y else raw_y

            return GroundingResult(
                found=True,
                x=actual_x,
                y=actual_y,
                confidence=0.85,
                element_label=parsed.get("label", target_description),
                method="gemini_vision",
            )

        except Exception as e:
            logger.error(f"[Grounding] Vision API hatasi: {e}")
            return GroundingResult(found=False, method="gemini_vision", error=str(e))


def ground_and_click(target_description: str, api_key: str = "",
                     double_click: bool = False) -> dict[str, Any]:
    """
    Ekrandaki bir elemani Gemini Vision ile bul ve tikla.

    Args:
        target_description: Tiklanacak elemanin tarifi (dogal dil)
        api_key: Gemini API anahtari
        double_click: Cift tiklama mi?

    Returns:
        {"success": bool, "x": int, "y": int, "message": str}
    """
    grounder = GeminiGrounder()
    if api_key:
        grounder.set_api_key(api_key)

    result = grounder.find_element(target_description)

    if not result.found:
        return {
            "success": False,
            "x": 0,
            "y": 0,
            "message": f"Eleman bulunamadi: {result.error or target_description}"
        }

    try:
        import pyautogui
        pyautogui.FAILSAFE = True

        if double_click:
            pyautogui.doubleClick(result.x, result.y, duration=0.1)
            action_name = "cift tiklama"
        else:
            pyautogui.click(result.x, result.y, duration=0.1)
            action_name = "tiklama"

        logger.info(f"[Grounding] {action_name}: '{result.element_label}' @ ({result.x}, {result.y})")
        return {
            "success": True,
            "x": result.x,
            "y": result.y,
            "message": f"✅ Grounding basarili: '{result.element_label}' ({result.x}, {result.y}) {action_name} yapildi."
        }

    except Exception as e:
        logger.error(f"[Grounding] Click hatasi: {e}")
        return {
            "success": False,
            "x": result.x,
            "y": result.y,
            "message": f"Koordinat bulundu ({result.x},{result.y}) ancak tiklama basarisiz: {e}"
        }


# Global singleton
gemini_grounder = GeminiGrounder()
