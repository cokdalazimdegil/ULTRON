"""
ULTRON Research Engine V2
══════════════════════════
• DuckDuckGo → Wikipedia → Bing HTML fallback zinciri
• Paralel URL getirme (6 thread)
• Otomatik retry (3 deneme, 1s bekleme)
• Gemini 2.0 Flash sentez + API key yoksa kural tabanlı fallback
• Rapor kaydı: memory/research_reports/
"""
from __future__ import annotations

import asyncio
import json
import os
import re
import time
import datetime
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Callable, Optional
from urllib.parse import quote_plus, unquote

logger = logging.getLogger("ultron.actions.research_engine")

REPORTS_DIR = Path(__file__).parent.parent / "memory" / "research_reports"
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

_EXECUTOR = ThreadPoolExecutor(max_workers=6, thread_name_prefix="ultron_research")

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "tr-TR,tr;q=0.9,en;q=0.8",
}


def _clean_html(html: str, max_chars: int = 4000) -> str:
    for tag in ("script", "style", "nav", "footer", "header", "aside", "iframe", "noscript", "svg", "form"):
        html = re.sub(rf"<{tag}[^>]*>.*?</{tag}>", " ", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", html)
    text = re.sub(r"\s+", " ", text).strip()
    text = (text.replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
                .replace("&quot;", '"').replace("&#39;", "'").replace("&nbsp;", " "))
    return text[:max_chars]


# ── Arama Sağlayıcıları ────────────────────────────────────────────────────────

def _duckduckgo_search(query: str, max_results: int = 7) -> list:
    """DuckDuckGo HTML arama (birincil sağlayıcı)."""
    try:
        import requests
        encoded = quote_plus(query)
        url = f"https://html.duckduckgo.com/html/?q={encoded}&kl=tr-tr"
        resp = requests.get(url, headers=_HEADERS, timeout=12)
        resp.raise_for_status()
        html = resp.text
        results = []
        links = re.findall(r'<a[^>]+class="result__a"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.DOTALL | re.IGNORECASE)
        snippets = re.findall(r'<a[^>]+class="result__snippet"[^>]*>(.*?)</a>', html, flags=re.DOTALL | re.IGNORECASE)
        for i, (href, title) in enumerate(links[:max_results]):
            real_url = href
            uddg = re.search(r'uddg=([^&]+)', href)
            if uddg:
                real_url = unquote(uddg.group(1))
            if not real_url.startswith("http"):
                continue
            snippet = _clean_html(snippets[i], 300) if i < len(snippets) else ""
            results.append({"title": _clean_html(title, 120), "url": real_url, "snippet": snippet})
        return results
    except Exception as e:
        logger.warning(f"[Research] DuckDuckGo hatası: {e}")
        return []


def _wikipedia_search(query: str, max_results: int = 5) -> list:
    """Wikipedia API arama (ikincil sağlayıcı)."""
    try:
        import requests
        # Arama sonuçları
        search_url = "https://tr.wikipedia.org/w/api.php"
        params = {
            "action": "query", "list": "search", "srsearch": query,
            "srlimit": max_results, "format": "json", "utf8": 1
        }
        resp = requests.get(search_url, params=params, headers=_HEADERS, timeout=8)
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("query", {}).get("search", [])
        results = []
        for hit in hits:
            title = hit.get("title", "")
            snippet = re.sub(r"<[^>]+>", "", hit.get("snippet", ""))
            page_url = f"https://tr.wikipedia.org/wiki/{quote_plus(title)}"
            results.append({"title": title, "url": page_url, "snippet": snippet})
        # İngilizce Wikipedia'ya da bak
        if len(results) < max_results:
            params["action"] = "query"
            en_resp = requests.get(
                "https://en.wikipedia.org/w/api.php",
                params={**params, "srlimit": max_results - len(results)},
                headers=_HEADERS, timeout=8
            )
            en_data = en_resp.json()
            for hit in en_data.get("query", {}).get("search", []):
                title = hit.get("title", "")
                snippet = re.sub(r"<[^>]+>", "", hit.get("snippet", ""))
                page_url = f"https://en.wikipedia.org/wiki/{quote_plus(title)}"
                results.append({"title": title, "url": page_url, "snippet": snippet})
        return results
    except Exception as e:
        logger.warning(f"[Research] Wikipedia hatası: {e}")
        return []


def _bing_search(query: str, max_results: int = 5) -> list:
    """Bing HTML arama (üçüncül sağlayıcı)."""
    try:
        import requests
        encoded = quote_plus(query)
        url = f"https://www.bing.com/search?q={encoded}&setlang=tr"
        resp = requests.get(url, headers={**_HEADERS, "Accept-Language": "tr-TR,tr;q=0.9"}, timeout=10)
        resp.raise_for_status()
        html = resp.text
        # Bing sonuç bağlantıları
        links = re.findall(r'<h2><a href="(https?://[^"]+)"[^>]*>(.*?)</a>', html, flags=re.DOTALL)
        snippets = re.findall(r'<p class="b_algoSlug[^"]*">(.*?)</p>', html, flags=re.DOTALL | re.IGNORECASE)
        results = []
        for i, (href, title) in enumerate(links[:max_results]):
            snippet = _clean_html(snippets[i], 250) if i < len(snippets) else ""
            results.append({"title": _clean_html(title, 120), "url": href, "snippet": snippet})
        return results
    except Exception as e:
        logger.warning(f"[Research] Bing hatası: {e}")
        return []


def _duckduckgo_lite_search(query: str, max_results: int = 7) -> list:
    """DuckDuckGo Lite HTML arama (ikincil hızlı yedek sağlayıcı)."""
    try:
        import requests
        resp = requests.post(
            "https://lite.duckduckgo.com/lite/",
            data={"q": query, "kl": "tr-tr"},
            headers={**_HEADERS, "Content-Type": "application/x-www-form-urlencoded"},
            timeout=10
        )
        resp.raise_for_status()
        html = resp.text
        results = []
        links = re.findall(r'<a[^>]+class="result-link"[^>]+href="([^"]+)"[^>]*>(.*?)</a>', html, flags=re.DOTALL | re.IGNORECASE)
        snippets = re.findall(r'<td[^>]+class="result-snippet"[^>]*>(.*?)</td>', html, flags=re.DOTALL | re.IGNORECASE)
        for i, (href, title) in enumerate(links[:max_results]):
            real_url = href
            uddg = re.search(r'uddg=([^&]+)', href)
            if uddg:
                real_url = unquote(uddg.group(1))
            if not real_url.startswith("http"):
                continue
            snippet = _clean_html(snippets[i], 300) if i < len(snippets) else ""
            results.append({"title": _clean_html(title, 120), "url": real_url, "snippet": snippet})
        return results
    except Exception as e:
        logger.warning(f"[Research] DuckDuckGo Lite hatası: {e}")
        return []


def _search_with_fallback(query: str, max_results: int = 7) -> list:
    """
    DuckDuckGo → DuckDuckGo-Lite → Wikipedia → Bing fallback zinciri.
    Her birini 2 kez dener, 1s aralıkla.
    """
    providers = [
        ("DuckDuckGo",      _duckduckgo_search),
        ("DuckDuckGo-Lite", _duckduckgo_lite_search),
        ("Wikipedia",       _wikipedia_search),
        ("Bing",            _bing_search),
    ]
    for name, fn in providers:
        for attempt in range(2):
            try:
                results = fn(query, max_results)
                if results:
                    logger.info(f"[Research] {name} sağlayıcısından {len(results)} sonuç alındı (deneme {attempt+1})")
                    return results
            except Exception as e:
                logger.warning(f"[Research] {name} deneme {attempt+1} başarısız: {e}")
            if attempt == 0:
                time.sleep(0.8)
    logger.error(f"[Research] Tüm arama sağlayıcıları başarısız: '{query}'")
    return []


# ── URL İçerik Getirme ─────────────────────────────────────────────────────────

def _fetch_url(url: str, max_chars: int = 3500) -> str:
    """Tek URL'nin içeriğini getirir. Hata durumunda açıklayıcı mesaj döner."""
    for attempt in range(2):
        try:
            import requests
            resp = requests.get(url, headers=_HEADERS, timeout=10)
            resp.raise_for_status()
            return _clean_html(resp.text, max_chars)
        except Exception as e:
            if attempt == 0:
                time.sleep(0.5)
            else:
                return f"[İçerik alınamadı: {url} — {e}]"
    return f"[İçerik alınamadı: {url}]"


async def _fetch_urls_parallel(urls: list, max_chars_each: int = 3000) -> list:
    loop = asyncio.get_event_loop()
    tasks = [loop.run_in_executor(_EXECUTOR, _fetch_url, url, max_chars_each) for url in urls]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    return [str(r) if not isinstance(r, Exception) else f"[Fetch hatası: {r}]" for r in results]


def _save_report(query: str, report_md: str) -> str:
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_name = re.sub(r"[^\w\s-]", "", query[:40]).strip().replace(" ", "_")
    filepath = REPORTS_DIR / f"{timestamp}_{safe_name}.md"
    filepath.write_text(report_md, encoding="utf-8")
    return str(filepath)


# ── Gemini Sentez ─────────────────────────────────────────────────────────────

def _synthesize_with_gemini(query: str, combined_sources: str) -> str:
    """Gemini çoklu model akıl yürütme motoru ile kaynak sentezi. API yoksa boş döner."""
    today_str = datetime.datetime.now().strftime('%d %B %Y')
    synthesis_prompt = (
        f"Aşağıdaki web kaynaklarını kullanarak '{query}' konusunda kapsamlı bir "
        f"Türkçe araştırma raporu oluştur.\n\n"
        f"Rapor formatı:\n"
        f"# {query} — Araştırma Raporu\n"
        f"**Tarih:** {today_str}\n\n"
        f"## Yönetici Özeti\n"
        f"## Temel Bulgular\n"
        f"## Detaylı Analiz\n"
        f"## Sonuç ve Değerlendirme\n"
        f"## Kaynaklar\n\n"
        f"---\nHAM VERİLER:\n{combined_sources[:14000]}"
    )
    try:
        from orchestrator.gemini_reasoning import query_gemini_reasoning
        res = query_gemini_reasoning(synthesis_prompt, model_tier="flash", temperature=0.3)
        if res and len(res.strip()) > 30:
            return res.strip()
    except Exception as e:
        logger.warning(f"[Research] Gemini reasoning sentez hatası: {e}")
    return ""


def _build_fallback_report(query: str, results: list) -> str:
    """Gemini yoksa kural tabanlı rapor oluşturur."""
    today_str = datetime.datetime.now().strftime('%d %B %Y')
    bullets = "\n".join(f"- **{r['title']}**: {r['snippet']}" for r in results)
    urls_list = "\n".join(f"- [{r['title']}]({r['url']})" for r in results)
    return (
        f"# {query} — Araştırma Raporu\n\n"
        f"**Tarih:** {today_str}\n\n"
        f"## Bulunan Kaynaklar\n{bullets}\n\n"
        f"## Kaynaklar\n{urls_list}\n"
    )


# ── Ana Araştırma Akışı ────────────────────────────────────────────────────────

async def run_research(
    query: str,
    num_sources: int = 5,
    save_report: bool = True,
    progress_cb: Optional[Callable] = None
) -> dict:
    """Tam araştırma döngüsü: arama → içerik getirme → sentez → kayıt."""
    t0 = time.time()

    def _progress(msg: str):
        logger.info(f"[Research] {msg}")
        if progress_cb:
            try:
                progress_cb(msg)
            except Exception:
                pass

    _progress(f"Arama başlatıldı: {query}")
    loop = asyncio.get_event_loop()
    search_results = await loop.run_in_executor(
        _EXECUTOR, _search_with_fallback, query, num_sources + 2
    )

    if not search_results:
        elapsed = round(time.time() - t0, 1)
        return {
            "query": query, "sources": [], "elapsed_sec": elapsed,
            "report": f"⚠️ '{query}' için tüm arama sağlayıcıları sonuç döndürmedi.\n\n"
                      f"DuckDuckGo, Wikipedia ve Bing kaynakları denendi ancak sonuç bulunamadı. "
                      f"Lütfen internet bağlantınızı kontrol edin veya farklı anahtar kelimeler deneyin.",
            "saved_path": ""
        }

    top_results = search_results[:num_sources]
    _progress(f"{len(top_results)} kaynak bulundu, içerikler okunuyor...")

    urls = [r["url"] for r in top_results]
    page_contents = await _fetch_urls_parallel(urls, max_chars_each=3000)

    sources_text_parts = []
    for i, (result, content) in enumerate(zip(top_results, page_contents), 1):
        sources_text_parts.append(
            f"### Kaynak {i}: {result['title']}\n"
            f"URL: {result['url']}\n"
            f"Özet: {result['snippet']}\n\n{content}\n"
        )
    combined_sources = "\n---\n".join(sources_text_parts)

    _progress("Kaynaklar analiz ediliyor, rapor hazırlanıyor...")

    report_md = await loop.run_in_executor(
        _EXECUTOR, _synthesize_with_gemini, query, combined_sources
    )

    if not report_md.strip():
        report_md = _build_fallback_report(query, top_results)

    saved_path = ""
    if save_report:
        saved_path = await loop.run_in_executor(_EXECUTOR, _save_report, query, report_md)
        _progress(f"Rapor kaydedildi: {saved_path}")

    elapsed = round(time.time() - t0, 1)
    _progress(f"Araştırma tamamlandı ({elapsed}s, {len(top_results)} kaynak)")

    return {
        "query": query,
        "sources": top_results,
        "report": report_md,
        "saved_path": saved_path,
        "elapsed_sec": elapsed,
        "source_count": len(top_results),
    }


# ── Yardımcı Fonksiyonlar ──────────────────────────────────────────────────────

def simple_web_search(query_or_url: str, max_chars: int = 4000) -> str:
    """Hızlı tek sorgu: URL ise içeriği getir, değilse arama yap."""
    query_clean = (query_or_url or "").strip()
    if not query_clean:
        return "Arama sorgusu boş olamaz."
    if query_clean.startswith(("http://", "https://")):
        return _fetch_url(query_clean, max_chars)
    results = _search_with_fallback(query_clean, max_results=3)
    if not results:
        return f"'{query_clean}' için sonuç bulunamadı."
    parts = []
    for r in results[:3]:
        content = _fetch_url(r["url"], max_chars // 3)
        parts.append(f"**{r['title']}** ({r['url']})\n{r['snippet']}\n{content}")
    return "\n\n---\n\n".join(parts)


def handle_web_search(args: dict) -> str:
    query = args.get("query", args.get("url", "")).strip()
    if not query:
        return "Hata: 'query' parametresi gereklidir."
    return simple_web_search(query, max_chars=int(args.get("max_chars", 4000)))


def handle_deep_research(args: dict) -> str:
    query = args.get("query", args.get("topic", "")).strip()
    if not query:
        return "Hata: 'query' veya 'topic' parametresi gereklidir."
    num_sources = int(args.get("num_sources", 5))
    save = bool(args.get("save_report", True))

    import threading
    result_container: dict = {}

    def _thread_run():
        result_container["r"] = asyncio.run(
            run_research(query, num_sources=num_sources, save_report=save)
        )

    t = threading.Thread(target=_thread_run, daemon=True)
    t.start()
    t.join(timeout=120)
    result = result_container.get("r")
    if not result:
        return "Araştırma zaman aşımına uğradı (120s). Lütfen daha kısa bir konu deneyin."

    report = result.get("report", "")
    elapsed = result.get("elapsed_sec", 0)
    n = result.get("source_count", len(result.get("sources", [])))
    saved = result.get("saved_path", "")

    header = f"Araştırma süresi: {elapsed}s | Kaynak sayısı: {n}"
    if saved:
        header += f" | Rapor: {saved}"
    return f"{header}\n\n{report}"