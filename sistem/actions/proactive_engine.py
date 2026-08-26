"""
ULTRON — Proaktif Hatırlatıcı, Zamanlayıcı & Cron Motoru
────────────────────────────────────────────────────────
Geri sayım sayaçları, dakikalık/saatlik alarmlar ve zamanı gelen hatırlatıcıları
arka planda sürekli kontrol ederek kullanıcılara sesli/ekran uyarısı gönderir.
"""

from __future__ import annotations

import datetime as dt
import json
import time
import uuid
from pathlib import Path
from app_paths import data_path

TIMERS_FILE = data_path("memory", "active_timers.json")


def _load_timers() -> list[dict]:
    try:
        if TIMERS_FILE.exists():
            return json.loads(TIMERS_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []


def _save_timers(timers: list[dict]) -> None:
    try:
        TIMERS_FILE.parent.mkdir(parents=True, exist_ok=True)
        TIMERS_FILE.write_text(json.dumps(timers, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def set_proactive_timer(
    title: str,
    minutes: float = 0,
    seconds: float = 0,
    due_iso: str = "",
    user: str = "Nuri Can",
) -> str:
    """
    Belirli bir süre veya tarih için proaktif hatırlatıcı/alarm kurar.
    Zamanı geldiğinde Ultron arayüze ve hoparlöre otomatik olarak seslenir.
    """
    if not title or not title.strip():
        return "Hata: Hatırlatıcı konusu belirtilmedi."

    now = time.time()
    due_ts = 0.0

    if minutes > 0 or seconds > 0:
        total_sec = (float(minutes or 0) * 60) + float(seconds or 0)
        due_ts = now + total_sec
    elif due_iso:
        try:
            # Parse ISO or natural time
            due_clean = due_iso.strip()
            if "T" in due_clean:
                target_dt = dt.datetime.fromisoformat(due_clean)
            else:
                # E.g. "14:30" or "2026-08-17 14:30"
                if len(due_clean) <= 5 and ":" in due_clean:
                    today = dt.date.today()
                    h, m = map(int, due_clean.split(":"))
                    target_dt = dt.datetime(today.year, today.month, today.day, h, m)
                    if target_dt.timestamp() < now:
                        target_dt += dt.timedelta(days=1)
                else:
                    target_dt = dt.datetime.strptime(due_clean, "%Y-%m-%d %H:%M")
            due_ts = target_dt.timestamp()
        except Exception as e:
            return f"Geçersiz zaman formatı ({due_iso}): {e}. Lütfen dakika (örn. minutes=1) veya ISO tarih belirtin."
    else:
        return "Lütfen kaç dakika sonra hatırlatılacağını (örn. minutes=1) veya hedef saati belirtin."

    diff_sec = max(1, int(due_ts - now))
    due_time_str = time.strftime("%H:%M:%S", time.localtime(due_ts))

    timer_id = str(uuid.uuid4())[:8]
    timer_item = {
        "id": timer_id,
        "title": title.strip(),
        "user": user or "Nuri Can",
        "created_at": now,
        "due_ts": due_ts,
        "due_time_str": due_time_str,
        "triggered": False,
        "notified": False,
    }

    timers = _load_timers()
    timers.append(timer_item)
    _save_timers(timers)

    if diff_sec < 60:
        duration_desc = f"{diff_sec} saniye sonra"
    elif diff_sec < 3600:
        mins = round(diff_sec / 60, 1)
        duration_desc = f"{mins} dakika sonra ({due_time_str})"
    else:
        hours = round(diff_sec / 3600, 1)
        duration_desc = f"{hours} saat sonra ({due_time_str})"

    return f"⏰ Hatırlatıcı kuruldu: '{title}' için {duration_desc} ({user} adına) sana hatırlatacağım."


def get_active_timers() -> str:
    """Aktif bekleyen hatırlatıcıları ve alarmları listeler."""
    timers = _load_timers()
    now = time.time()
    pending = [t for t in timers if not t.get("notified") and t.get("due_ts", 0) > (now - 60)]

    if not pending:
        return "Şu anda bekleyen aktif bir hatırlatıcı veya sayaç bulunmuyor."

    lines = [f"⏰ Aktif Hatırlatıcılar ({len(pending)}):"]
    for t in pending:
        rem_sec = int(t["due_ts"] - now)
        if rem_sec > 0:
            m, s = divmod(rem_sec, 60)
            rem_str = f"{m} dk {s} sn kaldı" if m > 0 else f"{s} sn kaldı"
        else:
            rem_str = "şimdi çalıyor"
        lines.append(f"- [{t['id']}] {t['title']} ({t.get('user', 'Kullanıcı')}) → {t['due_time_str']} ({rem_str})")

    return "\n".join(lines)


def cancel_timer(query: str) -> str:
    """Belirtilen hatırlatıcıyı iptal eder."""
    timers = _load_timers()
    if not query:
        return "İptal edilecek hatırlatıcı belirtilmedi."

    q = query.lower().strip()
    remaining = []
    cancelled = []

    for t in timers:
        if not t.get("notified") and (q in t["id"].lower() or q in t["title"].lower() or q == "all" or q == "hepsi"):
            t["notified"] = True
            cancelled.append(t["title"])
        else:
            remaining.append(t)

    _save_timers(remaining)
    if cancelled:
        return f"✓ Hatırlatıcı iptal edildi: {', '.join(cancelled)}"
    return f"'{query}' ile eşleşen aktif hatırlatıcı bulunamadı."


def poll_due_reminders() -> list[dict]:
    """
    Arka plan servisinin zamanı dolan hatırlatıcıları çekmesi için çağrılır.
    Geriye henüz bildirilmemiş ve süresi dolmuş hatırlatıcı listesini döner.
    """
    now = time.time()
    timers = _load_timers()
    due_items = []
    changed = False

    for t in timers:
        if not t.get("notified") and t.get("due_ts", 0) <= now:
            t["triggered"] = True
            t["notified"] = True
            due_items.append(t)
            changed = True

    if changed:
        # Geçmişteki tamamlananları temizle (son 24 saat kalsın)
        valid = [t for t in timers if not t.get("notified") or (now - t.get("due_ts", 0) < 86400)]
        _save_timers(valid)

    return due_items
