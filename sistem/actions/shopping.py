"""
ULTRON E-Commerce & Shopping Assistant
──────────────────────────────────────
Trendyol, Amazon ve Hepsiburada üzerinde ürün arama, Chrome'da açma
ve sepete ekleme otomasyonu.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import subprocess
import threading
import time
import urllib.parse
from typing import Optional

logger = logging.getLogger("ultron.actions.shopping")

CHROME_PATHS = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
]

def find_chrome() -> Optional[str]:
    for p in CHROME_PATHS:
        if os.path.exists(p):
            return p
    return shutil.which("chrome") or shutil.which("google-chrome")


def open_in_browser(url: str) -> bool:
    """Belirtilen URL'yi öncelikle Chrome'da, yoksa varsayılan tarayıcıda açar ve öne getirir."""
    chrome_exe = find_chrome()
    opened = False
    
    if chrome_exe:
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            subprocess.Popen([chrome_exe, url], creationflags=flags)
            opened = True
            logger.info(f"[Shopping] Chrome ile açıldı: {url}")
        except Exception as e:
            logger.warning(f"[Shopping] Chrome açılamadı, varsayılana geçiliyor: {e}")

    if not opened:
        import webbrowser
        try:
            webbrowser.open(url, new=2)
            opened = True
        except Exception as e:
            logger.error(f"[Shopping] Tarayıcı açılamadı: {e}")

    # Pencereyi öne getir
    time.sleep(1.0)
    try:
        from computer.window_manager import focus_window
        focus_window("Chrome") or focus_window("Google Chrome") or focus_window("Browser")
    except Exception:
        pass

    return opened


def _auto_add_to_cart_worker(platform: str, product_name: str):
    """Arama sonuçları açıldıktan sonra ilk ürüne ve ardından 'Sepete Ekle' butonuna tıklar."""
    logger.info(f"[Shopping Automation] Otomatik sepete ekleme başlatıldı: {platform} - {product_name}")
    # Arama sayfasının yüklenmesini bekle
    time.sleep(3.5)

    try:
        from computer.gemini_grounding import ground_and_click
        from computer.keyboard_controller import press_key
        from computer.mouse_controller import scroll

        # 1. İlk ürünü bul ve tıkla
        logger.info("[Shopping Automation] İlk ürün aranıyor...")
        first_product_clicked = False

        res = ground_and_click("arama sonucundaki ilk ürün kartı veya ürün resmi", double_click=False)
        if res.get("success"):
            first_product_clicked = True
            logger.info("[Shopping Automation] İlk ürün tıklandı.")
        else:
            # Fallback: Biraz aşağı kaydır ve dene
            scroll(-3)
            time.sleep(1.0)
            res2 = ground_and_click("ürün görseli veya ürün başlığı", double_click=False)
            if res2.get("success"):
                first_product_clicked = True

        if first_product_clicked:
            # Ürün detay sayfasının açılmasını bekle
            time.sleep(3.5)
            # 2. 'Sepete Ekle' veya 'Sepete At' butonunu bul ve tıkla
            logger.info("[Shopping Automation] 'Sepete Ekle' butonu aranıyor...")
            cart_res = ground_and_click("Sepete Ekle butonu", double_click=False)
            if not cart_res.get("success"):
                # Sayfayı biraz kaydırıp tekrar dene
                scroll(-3)
                time.sleep(1.0)
                cart_res = ground_and_click("Sepete Ekle veya Sepet butonu", double_click=False)

            if cart_res.get("success"):
                logger.info("[Shopping Automation] ✅ Ürün başarıyla sepete eklendi!")
            else:
                logger.info("[Shopping Automation] 'Sepete Ekle' butonu ekranda bulunamadı; sayfa kullanıcının önünde açık.")
    except Exception as e:
        logger.error(f"[Shopping Automation] Hata: {e}")


def search_product_and_open(product_name: str, platform: str = "auto", add_to_cart: bool = False) -> str:
    """
    Trendyol, Amazon veya Hepsiburada üzerinde ürün arar, Chrome'da açar.
    add_to_cart=True ise ilk ürünü seçip sepete ekleme adımlarını ekranda yürütür.
    """
    if not product_name or not product_name.strip():
        return "Aramak istediğin ürünün adını belirtmedin."

    p_raw = product_name.strip()
    p_lower = p_raw.lower()
    plat = (platform or "auto").lower().strip()

    # Otomatik platform tespiti
    if "trendyol" in p_lower or plat == "trendyol":
        target_platform = "trendyol"
    elif "amazon" in p_lower or plat == "amazon":
        target_platform = "amazon"
    elif "hepsiburada" in p_lower or plat == "hepsiburada":
        target_platform = "hepsiburada"
    else:
        target_platform = "trendyol"  # Varsayılan Türk e-ticaret

    # Ürün adından platform isimlerini ve komut kelimelerini temizle
    clean_name = re.sub(r'\b(trendyol|amazon|hepsiburada)(\'?da|\'de|\'te|\'tan|\'den)?\b', '', p_raw, flags=re.IGNORECASE)
    clean_name = re.sub(r'\b(ara|bul|sepete|sepetime|ekle|al|fiyatı|fiyatına|bak|satın)\b', '', clean_name, flags=re.IGNORECASE)
    clean_name = clean_name.strip() or p_raw

    encoded_query = urllib.parse.quote_plus(clean_name)

    if target_platform == "trendyol":
        platform_name = "Trendyol"
        url = f"https://www.trendyol.com/sr?q={encoded_query}"
    elif target_platform == "amazon":
        platform_name = "Amazon Türkiye"
        url = f"https://www.amazon.com.tr/s?k={encoded_query}"
    elif target_platform == "hepsiburada":
        platform_name = "Hepsiburada"
        url = f"https://www.hepsiburada.com/ara?q={encoded_query}"
    else:
        platform_name = "Google Alışveriş"
        url = f"https://www.google.com/search?tbm=shop&q={encoded_query}"

    opened = open_in_browser(url)
    if not opened:
        return f"Tarayıcı açılamadı, lütfen Chrome'un kurulu olduğunu kontrol et."

    if add_to_cart:
        # Arka planda sepete ekleme adımlarını yürüt
        threading.Thread(
            target=_auto_add_to_cart_worker,
            args=(target_platform, clean_name),
            daemon=True,
            name="shopping-automation"
        ).start()
        return f"{platform_name} üzerinde '{clean_name}' arandı, Chrome'da açıldı ve sepete ekleme süreci başlatıldı."

    return f"{platform_name} üzerinde '{clean_name}' için arama yapıldı ve Chrome'da açıldı."
