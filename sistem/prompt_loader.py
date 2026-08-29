"""
ULTRON Prompt Loader — Deklaratif Persona Mimarisi (v2)
───────────────────────────────────────────────────────
Sistem promptunu persona/ klasöründeki yaşayan Markdown dosyalarından
birleştirir:
  core/persona/soul.md    → Karakter, kurallar, dream log
  core/persona/user.md    → Kullanıcı profili
  core/persona/agents.md  → Ajan ağı tanımları

Geriye dönük uyumluluk:
  core/prompt.txt hâlâ okunur (soul.md yoksa fallback).
  adapt_prompt() fonksiyonu korunur (server.py uyumluluğu).
"""

from __future__ import annotations

import re
from pathlib import Path

from actions.platform_utils import IS_WIN
from app_paths import resource_path, data_path

# ── Yollar ───────────────────────────────────────────────────────────────────
BASE_DIR    = Path(__file__).resolve().parent
PROMPT_PATH = resource_path("core", "prompt.txt")        # Eski fallback
PERSONA_DIR = resource_path("core", "persona")           # Yeni persona klasörü
SOUL_PATH   = PERSONA_DIR / "soul.md"
USER_PATH   = PERSONA_DIR / "user.md"
AGENTS_PATH = PERSONA_DIR / "agents.md"

# Kullanıcı verisi (memory güncellemeleri user.md'yi buraya yazar)
DATA_USER_PATH = data_path("persona", "user.md")

# ── Windows uyumluluk tablosu (eski prompt.txt için korundu) ─────────────────
WINDOWS_REPLACEMENTS: list[tuple[str, str]] = [
    ("macOS'ta çalışan", "Windows'ta çalışan"),
    ("Apple Calendar takvimini okur", "takvimi okur (Outlook veya ULTRON yerel takvimi)"),
    ("Apple Calendar takvimine yeni etkinlik ekler", "takvime yeni etkinlik ekler"),
    ("Apple Calendar takviminden etkinlik siler", "takvimden etkinlik siler"),
    ("Apple Anımsatıcılar listesini okur", "anımsatıcı listesini okur"),
    ("Apple Anımsatıcılar'a yeni kayıt ekler", "anımsatıcılara yeni kayıt ekler"),
    (
        "play_media: YouTube, Spotify veya Apple Music/Music içinde içerik açar ve mümkünse oynatır",
        "play_media: YouTube veya Spotify içinde içerik açar ve mümkünse oynatır",
    ),
    ("shell_run: Terminal komutu çalıştırır", "shell_run: PowerShell komutu çalıştırır"),
    (
        '- "Masaüstündeki dosyaları listele" → shell_run("ls ~/Desktop")',
        '- "Masaüstündeki dosyaları listele" → shell_run("Get-ChildItem $env:USERPROFILE\\Desktop")',
    ),
    (
        '- "Apple Music\'te Sezen Aksu Gülümse aç" → play_media(query="Sezen Aksu Gülümse", provider="apple_music", autoplay=true)',
        '- "Sezen Aksu Gülümse çal" → play_media(query="Sezen Aksu Gülümse", provider="auto", autoplay=true)',
    ),
]

WINDOWS_NOTE = (
    "\nPLATFORM NOTU (Windows):\n"
    "- Kabuk komutlari PowerShell sozdizimiyle yazilir (ls degil Get-ChildItem, "
    "dosya yollarinda ters bolu).\n"
    "- Takvim ve animsaticilar Outlook yapilandirilmissa Outlook'a, degilse "
    "ULTRON'in kendi yerel takvimine yazilir. Kullanici sormadikca bu ayrimi anlatma.\n"
    "- Apple Music yoktur; muzik istekleri Spotify veya YouTube uzerinden karsilanir.\n"
)

FALLBACK_PROMPT = (
    "Sen ULTRON'sin — {platform}'ta çalışan kişisel AI asistanı. "
    "Türkçe konuş. Kısa ve net yanıtlar ver. "
    "Araçları kullanarak görevleri tamamla, asla taklit etme."
)


# ── Persona okuyucu ───────────────────────────────────────────────────────────

def _read_md(path: Path, fallback: str = "") -> str:
    """Markdown dosyasını okur; hata varsa fallback döner."""
    try:
        if path.exists():
            return path.read_text(encoding="utf-8").strip()
    except Exception:
        pass
    return fallback


def _strip_dream_markers(soul_text: str) -> str:
    """Dream log bölümünü marka yorum satırlarından temizler — prompt'a temiz ekler."""
    # <!-- DREAM_LOG_START --> ... <!-- DREAM_LOG_END --> arasını bul
    match = re.search(
        r"<!-- DREAM_LOG_START -->(.*?)<!-- DREAM_LOG_END -->",
        soul_text,
        re.DOTALL,
    )
    if match:
        log_content = match.group(1).strip()
        if log_content:
            # İşaretçileri kaldır, sadece içeriği bırak
            soul_text = soul_text.replace(match.group(0), f"\n{log_content}\n")
        else:
            soul_text = soul_text.replace(match.group(0), "")
    return soul_text


def _load_user_md() -> str:
    """Önce data klasöründeki (dinamik) user.md'yi, yoksa kaynak user.md'yi yükler."""
    # data_path'teki user.md (memory güncellemeleriyle zenginleşmiş)
    dynamic = _read_md(DATA_USER_PATH)
    if dynamic:
        return dynamic
    return _read_md(USER_PATH)


def _memory_context() -> str:
    """Bellek sisteminden kullanıcıya ait üst öncelikli kayıtları çeker."""
    try:
        from memory.memory_manager import format_memory_for_prompt
        mem = format_memory_for_prompt()
        return mem or ""
    except Exception:
        pass
    try:
        from memory.memory_2 import intelligent_memory
        return intelligent_memory.format_for_prompt(max_entries=10)
    except Exception:
        return ""


# ── Ana fonksiyonlar ──────────────────────────────────────────────────────────

def load_system_prompt() -> str:
    """
    Tam sistem promptunu oluşturur:
    soul.md + user.md + agents.md + memory context + platform notu
    """
    # 1. Soul (karakter + dream log)
    soul = _read_md(SOUL_PATH)
    if soul:
        soul = _strip_dream_markers(soul)
        # Markdown başlıklarını prompt için düzleştir
        soul = soul.replace("# ULTRON — Ruh ve Temel Direktifler (Soul File)\n", "")
        soul = soul.replace(
            "> Bu dosya Ultron'un değiştirilemez karakterini ve temel kurallarını tanımlar.\n"
            "> Dream Engine her gece \"## Dream Log\" bölümüne yeni öğrenimler ekler.\n"
            "> prompt_loader.py bu dosyayı sistem prompt'una birleştirir.\n", ""
        )
    else:
        # Geriye dönük uyumluluk: prompt.txt
        try:
            soul = PROMPT_PATH.read_text(encoding="utf-8")
        except Exception:
            soul = FALLBACK_PROMPT.format(platform="Windows" if IS_WIN else "macOS")

    # 2. Kullanıcı profili
    user_md = _load_user_md()
    if user_md:
        user_section = (
            "\n\n[KULLANICI PROFİLİ — Bu bilgileri zaten biliyorsun, tekrar sorma]\n"
            + user_md.replace("# ULTRON — Kullanıcı Profili (User File)\n", "")
               .replace("> Bu dosya YARATICI hakkında bilinen her şeyi içerir.\n"
                        "> memory_manager.py'deki update_memory() çağrıldığında otomatik güncellenir.\n"
                        "> prompt_loader.py bu dosyayı sistem prompt'una birleştirir.\n", "")
        )
    else:
        user_section = ""

    # 3. Ajan tanımları (kısa özet — tam dosya çok uzun olur)
    agents_md = _read_md(AGENTS_PATH)
    if agents_md:
        agents_section = "\n\n[AJAN AĞI KURALLARI]\n"
        # Sadece seçim kurallarını ekle
        rules_match = re.search(r"## Ajan Seçim Kuralları(.*?)(?:##|$)", agents_md, re.DOTALL)
        if rules_match:
            agents_section += rules_match.group(1).strip()
    else:
        agents_section = ""

    # 4. Bellek bağlamı
    memory_ctx = _memory_context()
    memory_section = f"\n\n{memory_ctx}" if memory_ctx else ""

    # 5. Platform notu (Windows)
    platform_note = WINDOWS_NOTE if IS_WIN else ""

    return soul + user_section + agents_section + memory_section + platform_note


def adapt_prompt(text: str) -> str:
    """
    Geriye dönük uyumluluk: server.py hâlâ bu fonksiyonu çağırıyor.
    prompt.txt tabanlı metni Windows'a uyarlar.
    """
    if not IS_WIN:
        return text
    for mac_text, win_text in WINDOWS_REPLACEMENTS:
        text = text.replace(mac_text, win_text)
    return text + WINDOWS_NOTE
