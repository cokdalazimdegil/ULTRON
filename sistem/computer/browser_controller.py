"""
ULTRON Computer Awareness — Browser Controller Module
─────────────────────────────────────────────────────
• Web tarayıcı yönetimi, arama, sayfa okuma ve otomasyon
• URL açma, Google/Bing arama, yeni sekme ve sayfa içeriği ayıklama
"""

from __future__ import annotations

import logging
import urllib.parse
import webbrowser
import time
from typing import Any

from computer.keyboard_controller import hotkey
from computer.app_controller import is_app_running

logger = logging.getLogger("ultron.computer.browser_controller")


def browser_open(url: str) -> tuple[bool, str]:
    """Web tarayıcısında belirtilen adresi açar."""
    target_url = url.strip()
    if not target_url.startswith(("http://", "https://")):
        target_url = f"https://{target_url}"

    try:
        webbrowser.open(target_url, new=2)
        time.sleep(1.0)
        # Chrome, Edge veya genel browser çalışıyor mu kontrol et
        running = is_app_running("chrome") or is_app_running("edge") or is_app_running("browser")
        if running:
            return True, f"✓ Tarayıcıda '{target_url}' başarıyla açıldı ve doğrulandı."
        return True, f"✓ '{target_url}' adresi açılmak üzere varsayılan tarayıcıya iletildi."
    except Exception as e:
        logger.error(f"Tarayici acma hatasi: {e}")
        return False, f"Tarayıcı açılamadı: {e}"


def browser_search(query: str, engine: str = "google") -> tuple[bool, str]:
    """Arama motorunda arama yapar."""
    clean_q = query.strip()
    encoded = urllib.parse.quote_plus(clean_q)

    eng = engine.lower()
    if eng == "bing":
        url = f"https://www.bing.com/search?q={encoded}"
    elif eng == "duckduckgo":
        url = f"https://duckduckgo.com/?q={encoded}"
    elif eng == "youtube":
        url = f"https://www.youtube.com/results?search_query={encoded}"
    else:
        url = f"https://www.google.com/search?q={encoded}"

    return browser_open(url)


def browser_read_page(url: str) -> str:
    """Belirtilen URL'nin içeriğini okur ve temiz metin olarak döner."""
    try:
        from actions.web_tools import fetch_webpage_content
        content = fetch_webpage_content(url)
        if content and not content.startswith("Hata:"):
            return content
    except Exception:
        pass

    import urllib.request
    import re
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # Basit html strip
            text = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<style.*?</style>', '', text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r'<.*?>', ' ', text)
            text = re.sub(r'\s+', ' ', text).strip()
            return text[:4000]
    except Exception as e:
        return f"Sayfa içeriği okunamadı: {e}"


def browser_new_tab(url: str = "") -> bool:
    """Tarayıcıda yeni sekme açar (Ctrl+T)."""
    hotkey("ctrl", "t")
    if url:
        time.sleep(0.2)
        from computer.keyboard_controller import type_text, press_key
        type_text(url)
        press_key("enter")
    return True


def browser_back() -> bool:
    """Tarayıcıda bir önceki sayfaya döner (Alt+Left)."""
    return hotkey("alt", "left")
