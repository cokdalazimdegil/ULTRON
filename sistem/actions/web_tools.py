"""
ULTRON — Web İçeriği Okuma ve Çıkarma Aracı
───────────────────────────────────────────
Herhangi bir web sayfasının veya makalenin metnini çeker ve okur.
"""

from __future__ import annotations

import re
import requests


def fetch_webpage_content(url: str, max_chars: int = 3000) -> str:
    """
    Belirtilen URL adresindeki web sayfasının metin içeriğini temizleyip okur.
    Haber, makale, dokümantasyon veya arama sonuçları okumak için kullanılır.
    """
    if not url or not url.startswith(("http://", "https://")):
        return "Geçerli bir URL giriniz (http:// veya https:// ile başlamalı)."

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        res = requests.get(url, headers=headers, timeout=10)
        res.raise_for_status()
        
        # HTML temizleme (script, style, etiketler)
        html = res.text
        html = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<nav.*?</nav>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<footer.*?</footer>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<header.*?</header>', '', html, flags=re.DOTALL | re.IGNORECASE)
        
        # Etiketleri kaldır
        text = re.sub(r'<[^>]+>', ' ', html)
        text = re.sub(r'\s+', ' ', text).strip()
        
        if len(text) > max_chars:
            text = text[:max_chars] + f"\n... [İçerik kısaltıldı. Toplam: {len(text)} karakter]"
            
        return f"🌐 Web Sayfası İçeriği ({url}):\n\n{text}"
    except Exception as e:
        return f"Web sayfası okunurken hata: {e}"
