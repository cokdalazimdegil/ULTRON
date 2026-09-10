"""
ULTRON — Settings Panel (Ayar Menüleri ve Yapılandırma Paneli)
Sistem ayarları, ses modeli seçimi, tema ve token yönetimi bileşenleri.
"""

from typing import Any, Dict, Optional
import logging

logger = logging.getLogger("ultron.ui.settings")


class SettingsPanel:
    """Masaüstü ve Web arayüz ayar paneli kontrolcüsü."""
    def __init__(self, config_manager=None):
        self.config_manager = config_manager

    def get_available_voices(self) -> list[str]:
        return ["Charon", "Puck", "Aoede", "Kore", "Fenrir", "Leda", "Orus", "Zephyr"]

    def get_settings(self) -> Dict[str, Any]:
        try:
            from config import load_app_config
            return load_app_config()
        except Exception as e:
            logger.warning(f"Ayar yüklenemedi: {e}")
            return {}

    def update_settings(self, updates: Dict[str, Any]) -> bool:
        try:
            from config import save_app_config
            save_app_config(updates)
            return True
        except Exception as e:
            logger.error(f"Ayar kaydedilemedi: {e}")
            return False


__all__ = ["SettingsPanel"]
