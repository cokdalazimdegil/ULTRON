"""
ULTRON Transcript Store — JSONL Tabanlı Episodik Hafıza (OpenClaw Mimarisi)
──────────────────────────────────────────────────────────────────────────
OpenClaw'ın yaptığı gibi konuşma geçmişini ve olayları append-only JSONL
dosyalarına yazar. Sınırsız hafıza kapasitesi ve hızlı okuma sağlar.

Dosya düzeni:
  data/transcripts/YYYY-MM-DD.jsonl  — günlük konuşmalar
  data/transcripts/events.jsonl       — sistem olayları (heartbeat, dream, vb.)

Her satır bağımsız bir JSON nesnesidir (JSONL formatı).
"""

from __future__ import annotations

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path

from app_paths import data_path

logger = logging.getLogger("ultron.memory.transcript_store")

_TRANSCRIPTS_DIR = data_path("transcripts")
_LOCK = threading.Lock()


def _ensure_dir():
    _TRANSCRIPTS_DIR.mkdir(parents=True, exist_ok=True)


def _today_file() -> Path:
    """Bugünün konuşma dosyasını döner."""
    today = datetime.now().strftime("%Y-%m-%d")
    return _TRANSCRIPTS_DIR / f"{today}.jsonl"


def _events_file() -> Path:
    return _TRANSCRIPTS_DIR / "events.jsonl"


# ── Yazma (Append-only) ────────────────────────────────────────────────────

def append_turn(who: str, text: str, metadata: dict | None = None) -> None:
    """
    Konuşma geçmişine bir tur (user veya jarvis mesajı) ekler.

    Args:
        who:      "user" veya "jarvis"
        text:     Mesaj metni
        metadata: Opsiyonel ek bilgi (lang, session_id vb.)
    """
    _ensure_dir()
    record = {
        "ts": time.time(),
        "dt": datetime.now().isoformat(timespec="seconds"),
        "who": who,
        "text": text.strip(),
    }
    if metadata:
        record["meta"] = metadata

    _append_line(_today_file(), record)


def append_event(event_type: str, data: dict | None = None) -> None:
    """
    Sistem olayı kaydeder (heartbeat, dream_engine, tool_call vb.)

    Args:
        event_type: Olay tipi (ör: "heartbeat_task", "dream_insight")
        data:       Olayla ilgili ek veri
    """
    _ensure_dir()
    record = {
        "ts": time.time(),
        "dt": datetime.now().isoformat(timespec="seconds"),
        "type": event_type,
        "data": data or {},
    }
    _append_line(_events_file(), record)


def _append_line(path: Path, record: dict) -> None:
    """Thread-safe satır ekleme."""
    line = json.dumps(record, ensure_ascii=False)
    with _LOCK:
        try:
            with open(path, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as exc:
            logger.error(f"[TranscriptStore] Yazma hatası ({path.name}): {exc}")


# ── Okuma ──────────────────────────────────────────────────────────────────

def read_today(limit: int = 100) -> list[dict]:
    """Bugünün konuşma kayıtlarının son `limit` kadarını döner."""
    return _read_tail(_today_file(), limit)


def read_date(date_str: str, limit: int = 200) -> list[dict]:
    """Belirli bir tarihin kayıtlarını okur (YYYY-MM-DD formatı)."""
    path = _TRANSCRIPTS_DIR / f"{date_str}.jsonl"
    return _read_tail(path, limit)


def read_recent_events(limit: int = 50) -> list[dict]:
    """Son `limit` kadar sistem olayını döner."""
    return _read_tail(_events_file(), limit)


def _read_tail(path: Path, limit: int) -> list[dict]:
    """Dosyanın son `limit` satırını JSON olarak döner."""
    if not path.exists():
        return []
    records = []
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        pass
    except Exception as exc:
        logger.error(f"[TranscriptStore] Okuma hatası ({path.name}): {exc}")
    return records[-limit:]


# ── Özet Çıkarma ──────────────────────────────────────────────────────────

def get_context_window(turns: int = 20) -> str:
    """
    Son `turns` kadar konuşmayı düz metin olarak döner.
    Gemini'ye bağlam sağlamak için kullanılır.
    """
    records = read_today(turns)
    if not records:
        return ""
    lines = []
    for r in records:
        who = "Kullanıcı" if r.get("who") == "user" else "ULTRON"
        lines.append(f"[{r.get('dt', '')}] {who}: {r.get('text', '')}")
    return "\n".join(lines)


def cleanup_old_files(keep_days: int = 30) -> int:
    """30 günden eski JSONL dosyalarını siler. Silinen dosya sayısını döner."""
    _ensure_dir()
    cutoff = time.time() - (keep_days * 86400)
    removed = 0
    for f in _TRANSCRIPTS_DIR.glob("*.jsonl"):
        if f.name == "events.jsonl":
            continue  # Olayları silme
        if f.stat().st_mtime < cutoff:
            try:
                f.unlink()
                removed += 1
            except Exception:
                pass
    if removed:
        logger.info(f"[TranscriptStore] {removed} eski transcript dosyası temizlendi.")
    return removed


# Singleton referansı
transcript_store = type("TranscriptStore", (), {
    "append_turn": staticmethod(append_turn),
    "append_event": staticmethod(append_event),
    "read_today": staticmethod(read_today),
    "read_date": staticmethod(read_date),
    "read_recent_events": staticmethod(read_recent_events),
    "get_context_window": staticmethod(get_context_window),
    "cleanup_old_files": staticmethod(cleanup_old_files),
})()
