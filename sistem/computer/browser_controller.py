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


def _find_chrome_exe() -> str | None:
    import os
    import shutil
    candidates = [
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    ]
    for c in candidates:
        if os.path.exists(c):
            return c
    return shutil.which("chrome") or shutil.which("google-chrome")


def browser_open(url: str) -> tuple[bool, str]:
    """Web tarayıcısında (özellikle Google Chrome) belirtilen adresi açar."""
    target_url = url.strip()
    if not target_url.startswith(("http://", "https://")):
        target_url = f"https://{target_url}"

    try:
        chrome_exe = _find_chrome_exe()
        opened = False
        if chrome_exe:
            import subprocess
            flags = subprocess.CREATE_NO_WINDOW if subprocess.os.name == "nt" else 0
            subprocess.Popen([chrome_exe, target_url], creationflags=flags)
            opened = True
        if not opened:
            webbrowser.open(target_url, new=2)

        time.sleep(0.8)
        try:
            from computer.window_manager import focus_window
            focus_window("Chrome") or focus_window("Google Chrome") or focus_window("Browser")
        except Exception:
            pass

        return True, f"Chrome tarayıcısında '{target_url}' başarıyla açıldı."
    except Exception as e:
        logger.error(f"Tarayici acma hatasi: {e}")
        return False, f"Tarayıcı açılamadı: {e}"


def browser_search(query: str, engine: str = "google") -> tuple[bool, str]:
    """Arama motorunda veya e-ticaret sitelerinde arama yapar."""
    clean_q = query.strip()
    clean_lower = clean_q.lower()
    eng = (engine or "google").lower().strip()

    import re
    if eng == "trendyol" or "trendyol" in clean_lower:
        clean_name = re.sub(r'\btrendyol(\'?da|\'de|\'te|\'tan|\'den)?\b', '', clean_q, flags=re.IGNORECASE).strip() or clean_q
        url = f"https://www.trendyol.com/sr?q={urllib.parse.quote_plus(clean_name)}"
    elif eng == "amazon" or "amazon" in clean_lower:
        clean_name = re.sub(r'\bamazon(\'?da|\'de|\'te|\'tan|\'den)?\b', '', clean_q, flags=re.IGNORECASE).strip() or clean_q
        url = f"https://www.amazon.com.tr/s?k={urllib.parse.quote_plus(clean_name)}"
    elif eng == "hepsiburada" or "hepsiburada" in clean_lower:
        clean_name = re.sub(r'\bhepsiburada(\'?da)?\b', '', clean_q, flags=re.IGNORECASE).strip() or clean_q
        url = f"https://www.hepsiburada.com/ara?q={urllib.parse.quote_plus(clean_name)}"
    elif eng == "bing":
        url = f"https://www.bing.com/search?q={urllib.parse.quote_plus(clean_q)}"
    elif eng == "duckduckgo":
        url = f"https://duckduckgo.com/?q={urllib.parse.quote_plus(clean_q)}"
    elif eng == "youtube":
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(clean_q)}"
    else:
        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(clean_q)}"

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
