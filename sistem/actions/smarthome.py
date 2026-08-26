"""
ULTRON — Akıllı Ev Entegrasyonu (Smart Home / Home Assistant)
─────────────────────────────────────────────────────────────
Işıklar, prizler, klimalar, sahneler ve sensör durumlarını kontrol eder.
"""

from __future__ import annotations

import json
import requests
from app_config import get_app_config_value


def _get_ha_config() -> tuple[str, str]:
    url = str(get_app_config_value("home_assistant_url", "") or "").rstrip("/")
    token = str(get_app_config_value("home_assistant_token", "") or "")
    return url, token


def control_home_device(
    device_name: str,
    action: str = "toggle",
    brightness: int | None = None,
    color: str | None = None,
    temperature: float | None = None,
) -> str:
    """
    Akıllı ev cihazını açar, kapatır, parlaklığını veya sıcaklığını ayarlar.
    action: turn_on | turn_off | toggle | set_temperature | activate_scene
    """
    url, token = _get_ha_config()
    action = str(action or "toggle").lower()
    device = str(device_name or "").strip()

    if not url or not token:
        # Konfigürasyon henüz yapılmamışsa rehberlik sağla ve komutu anla
        return (
            f"Akıllı ev servisi ({device} -> {action}) algılandı. "
            "Home Assistant bağlantısı için config/api_keys.json içerisine "
            "'home_assistant_url' ve 'home_assistant_token' ekleyebilirsiniz."
        )

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    # Domain tespiti (light, switch, climate, scene)
    domain = "light"
    if "klima" in device.lower() or "termostat" in device.lower() or temperature is not None:
        domain = "climate"
    elif "priz" in device.lower() or "anahtar" in device.lower():
        domain = "switch"
    elif "sahne" in device.lower() or "modu" in device.lower():
        domain = "scene"

    service = "toggle"
    if action in ("turn_on", "ac", "yak", "aç"):
        service = "turn_on"
    elif action in ("turn_off", "kapat", "sondur", "söndür"):
        service = "turn_off"

    payload: dict = {}
    if brightness is not None and domain == "light":
        payload["brightness_pct"] = max(0, min(100, int(brightness)))
    if temperature is not None and domain == "climate":
        payload["temperature"] = float(temperature)

    try:
        req_url = f"{url}/api/services/{domain}/{service}"
        res = requests.post(req_url, headers=headers, json=payload, timeout=5)
        if res.status_code in (200, 201):
            return f"Akıllı ev komutu başarılı: {device} ({service})."
        return f"Home Assistant yanıtı ({res.status_code}): {res.text[:100]}"
    except Exception as e:
        return f"Akıllı ev cihazına bağlanırken hata: {e}"


def get_home_status(query: str = "all") -> str:
    """Evdeki cihazların, lambaların ve sensörlerin anlık durumunu özetler."""
    url, token = _get_ha_config()
    if not url or not token:
        return (
            "Home Assistant bilgileri henüz tanımlanmamış. "
            "Ayarlardan home_assistant_url ve token ekleyerek akıllı ev durumunu görebilirsiniz."
        )

    headers = {"Authorization": f"Bearer {token}"}
    try:
        res = requests.get(f"{url}/api/states", headers=headers, timeout=5)
        if res.status_code == 200:
            states = res.json()
            active_lights = [s["attributes"].get("friendly_name", s["entity_id"]) 
                             for s in states if s["entity_id"].startswith("light.") and s["state"] == "on"]
            summary = f"Açık Lambalar ({len(active_lights)}): " + (", ".join(active_lights) if active_lights else "Tüm lambalar kapalı.")
            return summary
        return f"Home Assistant durum sorgusu başarısız: {res.status_code}"
    except Exception as e:
        return f"Home Assistant durum kontrolü hatası: {e}"
