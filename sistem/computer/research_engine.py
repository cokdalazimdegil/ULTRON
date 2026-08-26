"""
ULTRON Autonomous Engine — Research Mode Module
───────────────────────────────────────────────
• Çok kaynaklı otonom araştırma ve bilgi sentezi
• Arama planı oluşturma, web sayfalarını okuma, bilgileri karşılaştırma
• Sonuç raporlama ve kullanıcıya net özet sunma
"""

from __future__ import annotations

import json
import logging
import re
import time
import urllib.parse
import urllib.request
from typing import Any

from computer.safety_manager import SafetyManager
from computer.computer_state import current_computer_state

logger = logging.getLogger("ultron.computer.research_engine")


def _fetch_page_clean_text(url: str, timeout: int = 8) -> str:
    """Web sayfasını indirir ve HTML'den arındırılmış temiz metin döner."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7",
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read()
            html = raw.decode("utf-8", errors="ignore")
            # Script, style, nav, footer ve header temizle
            cleaned = re.sub(r'<script.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
            cleaned = re.sub(r'<style.*?</style>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
            cleaned = re.sub(r'<nav.*?</nav>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
            cleaned = re.sub(r'<footer.*?</footer>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
            cleaned = re.sub(r'<header.*?</header>', '', cleaned, flags=re.DOTALL | re.IGNORECASE)
            cleaned = re.sub(r'<.*?>', ' ', cleaned)
            cleaned = re.sub(r'&[a-zA-Z0-9#]+;', ' ', cleaned)
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()
            return cleaned[:3500]
    except Exception as e:
        logger.debug(f"Sayfa okuma hatasi ({url}): {e}")
        return ""


def _search_duckduckgo_lite(query: str, max_results: int = 5) -> list[dict[str, str]]:
    """DuckDuckGo HTML POST ve Wikipedia üzerinden güvenilir canlı web araması yapar."""
    encoded = urllib.parse.quote_plus(query)
    results: list[dict[str, str]] = []

    # 1. DuckDuckGo HTML POST Araması
    try:
        data = urllib.parse.urlencode({'q': query}).encode('utf-8')
        req = urllib.request.Request(
            'https://html.duckduckgo.com/html/',
            data=data,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Language': 'tr-TR,tr;q=0.9,en-US;q=0.8,en;q=0.7',
                'Referer': 'https://html.duckduckgo.com/'
            }
        )
        with urllib.request.urlopen(req, timeout=7) as resp:
            html = resp.read().decode('utf-8', errors='ignore')

        titles_and_links = re.findall(r'<a rel="nofollow" class="result__a" href="([^"]+)">(.*?)</a>', html, re.DOTALL)
        snippets = re.findall(r'<a class="result__snippet"[^>]*>(.*?)</a>', html, re.DOTALL)

        for i, (raw_link, raw_title) in enumerate(titles_and_links[:max_results]):
            link_m = re.search(r'uddg=([^&]+)', raw_link)
            actual_url = urllib.parse.unquote(link_m.group(1)) if link_m else raw_link
            title = re.sub(r'<.*?>', '', raw_title).strip()
            snippet = re.sub(r'<.*?>', '', snippets[i]).strip() if i < len(snippets) else ""

            if actual_url.startswith("http") and not "duckduckgo.com" in actual_url:
                results.append({
                    "title": title,
                    "url": actual_url,
                    "snippet": snippet
                })
    except Exception as e:
        logger.debug(f"Duckduckgo POST arama hatasi: {e}")

    # 2. Wikipedia Arama Fallback
    if len(results) < 2:
        try:
            wiki_url = f"https://tr.wikipedia.org/w/api.php?action=query&list=search&srsearch={encoded}&format=json&utf8="
            req = urllib.request.Request(wiki_url, headers={'User-Agent': 'ULTRON/1.0 (https://ultron.ai)'})
            with urllib.request.urlopen(req, timeout=5) as resp:
                w_data = json.loads(resp.read().decode('utf-8'))
                items = w_data.get('query', {}).get('search', [])
                for it in items[:3]:
                    w_title = it.get('title', '')
                    w_snip = re.sub(r'<.*?>', '', it.get('snippet', '')).strip()
                    w_url = f"https://tr.wikipedia.org/wiki/{urllib.parse.quote(w_title)}"
                    results.append({
                        "title": w_title,
                        "url": w_url,
                        "snippet": w_snip
                    })
        except Exception as e:
            logger.debug(f"Wiki arama hatasi: {e}")

    return results


def execute_research_plan(topic: str, max_sources: int = 4, cancel_token: Any = None) -> dict[str, Any]:
    """
    Belirtilen konu hakkında otonom çok kaynaklı derin araştırma (Deep Research) yürütür.
    Bunu yapmak için ana TaskEngine ReAct döngüsünü kullanır, böylece ajan kendi kararlarını
    vererek arama yapar, sayfalara girer ve sonuçları sentezler.
    """
    clean_topic = topic.strip()
    print(f"[Research Mode] 🧠 Otonom Derin Araştırma başlatıldı: '{clean_topic}'...", flush=True)
    current_computer_state.set_research_mode(True)

    if SafetyManager.is_emergency_stopped():
        current_computer_state.set_research_mode(False)
        return {"status": "CANCELLED", "summary": "Araştırma acil durdurma nedeniyle iptal edildi."}

    from computer.task_executor import TaskEngine
    
    prompt = (
        f"Şu konu hakkında derin ve otonom bir internet araştırması yap (Deep Research): '{clean_topic}'.\n"
        f"1. 'web_search' aracını kullanarak konuyu araştır.\n"
        f"2. Gerekirse bulduğun ilgi çekici linkleri 'fetch_webpage_content' ile oku.\n"
        f"3. Bilgileri sentezleyerek dev, kapsamlı ve profesyonel bir rapor oluştur.\n"
        f"Görevi 'FINISH' ile sonlandırırken message alanına hazırladığın bu detaylı raporu yaz."
    )
    
    task = TaskEngine.create_task(prompt, owner="ULTRON Deep Research Agent")
    # Ajanı çalıştır (bu fonksiyon ReAct döngüsünü işletip final string dönecektir)
    report = TaskEngine.execute_task_sync(task)
    
    current_computer_state.set_research_mode(False)

    return {
        "status": "COMPLETED",
        "topic": clean_topic,
        "sources_count": -1, # Dinamik ajan kullandığı için sayıyı saymıyoruz
        "sources": [],
        "summary": report
    }

