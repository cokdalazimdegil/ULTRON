"""
ULTRON Heartbeat Engine — Otonom Zamanlı Görev Motoru (OpenClaw Mimarisi)
─────────────────────────────────────────────────────────────────────────
heartbeat.yaml içindeki scheduled_tasks tanımlarını okur ve her görevi
doğru saatte kendi kendine tetikler. Kullanıcı mesajı beklemeden çalışır.

Özellikler:
  • HH:MM formatında günlük zamanlayıcı
  • "*/N" formatında periyodik tetikleyici (her N dakikada bir)
  • "broadcast" kanalı: bağlı web istemcilerine bildirim gönderir
  • "silent" kanalı: sadece hafızaya yazar, ses/bildirim üretmez
  • soul.md'den dinamik sistem promptu okur
"""

from __future__ import annotations

import asyncio
import datetime as dt
import logging
import threading
import time
from pathlib import Path
from typing import Any

logger = logging.getLogger("ultron.core.heartbeat_engine")

# Projenin sistem kök dizini
_SISTEM_DIR = Path(__file__).resolve().parent.parent
_HEARTBEAT_YAML = _SISTEM_DIR / "core" / "persona" / "heartbeat.yaml"


def _load_yaml(path: Path) -> dict:
    """YAML dosyasını okur. PyYAML yoksa boş dict döner."""
    try:
        import yaml  # type: ignore
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except ImportError:
        logger.warning("[HeartbeatEngine] pyyaml yüklü değil — pip install pyyaml")
    except Exception as exc:
        logger.error(f"[HeartbeatEngine] YAML okuma hatası: {exc}")
    return {}


def _parse_cron(cron_str: str) -> tuple[str, int | None]:
    """
    Cron ifadesini çözümler.
    Returns:
        ("daily", None)  → HH:MM formatı
        ("interval", N)  → */N (her N dakikada bir)
    """
    cron_str = cron_str.strip()
    if cron_str.startswith("*/"):
        try:
            interval_min = int(cron_str[2:])
            return ("interval", interval_min)
        except ValueError:
            pass
    if ":" in cron_str and len(cron_str) <= 5:
        return ("daily", None)
    return ("unknown", None)


class HeartbeatEngine:
    """
    Otonom görev zamanlayıcısı. Arka planda çalışır.
    Görevleri tetiklemek için broadcast_fn callback'i kullanır.
    """

    def __init__(self):
        self._running = False
        self._thread: threading.Thread | None = None
        self._broadcast_fn = None   # async fn(msg: str, channel: str)
        self._last_daily: dict[str, str] = {}  # task_name → son tetiklenme tarihi
        self._last_interval: dict[str, float] = {}  # task_name → son tetiklenme timestamp

    def set_broadcast(self, fn):
        """
        Görev tetiklendiğinde çağrılacak async fonksiyon.
        fn(message: str, channel: str) şeklinde çağrılır.
        """
        self._broadcast_fn = fn

    def start(self):
        """Heartbeat döngüsünü daemon thread olarak başlatır."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(
            target=self._loop,
            name="HeartbeatEngine",
            daemon=True
        )
        self._thread.start()
        logger.info("[HeartbeatEngine] ⏰ Otonom heartbeat motoru başlatıldı.")

    def stop(self):
        """Heartbeat döngüsünü durdurur."""
        self._running = False
        logger.info("[HeartbeatEngine] Heartbeat motoru durduruldu.")

    # ── İç Döngü ────────────────────────────────────────────────────────────

    def _loop(self):
        """60 saniyede bir scheduled_tasks listesini kontrol eder."""
        while self._running:
            try:
                self._tick()
            except Exception as exc:
                logger.error(f"[HeartbeatEngine] Döngü hatası: {exc}")
            time.sleep(60)  # Her dakika kontrol et

    def _tick(self):
        cfg = _load_yaml(_HEARTBEAT_YAML)
        tasks: list[dict[str, Any]] = cfg.get("scheduled_tasks", [])
        now = dt.datetime.now()
        now_hm = now.strftime("%H:%M")
        today_str = now.strftime("%Y-%m-%d")

        for task in tasks:
            if not task.get("enabled", True):
                continue

            name: str = task.get("name", "Görev")
            cron: str = str(task.get("cron", ""))
            description: str = task.get("description", "")
            channel: str = task.get("channel", "broadcast")

            if not cron:
                continue

            cron_type, interval_min = _parse_cron(cron)

            if cron_type == "daily":
                # HH:MM kontrolü — bugün daha önce tetiklendiyse atla
                if cron == now_hm:
                    last = self._last_daily.get(name, "")
                    if last != today_str:
                        self._last_daily[name] = today_str
                        self._fire_task(name, description, channel)

            elif cron_type == "interval" and interval_min:
                # Her N dakikada bir
                last_ts = self._last_interval.get(name, 0.0)
                elapsed_min = (time.time() - last_ts) / 60
                if elapsed_min >= interval_min:
                    self._last_interval[name] = time.time()
                    self._fire_task(name, description, channel)

    def _fire_task(self, name: str, description: str, channel: str):
        """Görevi tetikler: Gemini'ye description'ı gönderir."""
        logger.info(f"[HeartbeatEngine] 🔔 Görev tetiklendi: '{name}' [{channel}]")

        if self._broadcast_fn is None:
            logger.debug("[HeartbeatEngine] broadcast_fn ayarlanmamış — görev atlandı.")
            return

        # Async fonksiyonu yeni bir event loop'ta çalıştır
        try:
            loop = asyncio.new_event_loop()
            loop.run_until_complete(self._broadcast_fn(description, name, channel))
            loop.close()
        except Exception as exc:
            logger.error(f"[HeartbeatEngine] Görev yayın hatası: {exc}")


# Singleton
heartbeat_engine = HeartbeatEngine()
