"""
ULTRON Proactive Shadow Observer & Error Interceptor Engine
════════════════════════════════════════════════════════════
• Sıfır / Düşük Maliyetli Arka Plan Ekran & Sistem İzleme (Low-Overhead Daemon)
• Hata İmzası Tespiti (Python Traceback, JS/Node Error, Windows Crash, System Stress)
• Proaktif ve Müdahaleci Olmayan Çözüm Sentezi (Non-Intrusive Recommendation Synthesis)
• HUD & WebSocket Bildirim Hattı ile Çift Yönlü Aksiyon Entegrasyonu
"""

from __future__ import annotations

import logging
import os
import re
import threading
import time
import uuid
from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Callable, List, Optional

import psutil

from computer.screen_awareness import screen_awareness, VisualScreenContext, ChangeSeverity
from computer.world_model import world_model

logger = logging.getLogger("ultron.computer.proactive_watcher")


class AlertCategory(str, Enum):
    CODE_ERROR         = "CODE_ERROR"         # Traceback, Syntax, Import, Runtime hatası
    SYSTEM_STRESS      = "SYSTEM_STRESS"      # Aşırı CPU, RAM şişmesi, disk doluluğu
    NETWORK_ISSUE      = "NETWORK_ISSUE"      # Bağlantı kopması, port meşgul, timeout
    SECURITY_WARNING   = "SECURITY_WARNING"   # Yetkisiz işlem veya tehlikeli komut uyarısı
    ROUTINE_SUGGESTION = "ROUTINE_SUGGESTION" # Alışkanlık / Rutin önerisi


class AlertSeverity(str, Enum):
    INFO     = "INFO"
    LOW      = "LOW"
    MEDIUM   = "MEDIUM"
    HIGH     = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class ProactiveAlert:
    alert_id: str
    timestamp: float
    category: AlertCategory
    severity: AlertSeverity
    title: str
    message: str
    detected_snippet: str = ""
    suggested_action: str = ""
    auto_executable: bool = False
    status: str = "PENDING"  # PENDING, NOTIFIED, DISMISSED, EXECUTED
    target_app: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["category"] = self.category.value
        d["severity"] = self.severity.value
        return d


# Tanınan Hata İmzaları ve Çözüm Şablonları
ERROR_PATTERNS: list[dict[str, Any]] = [
    {
        "pattern": r"ModuleNotFoundError:\s+No module named ['\"]([^'\"]+)['\"]",
        "category": AlertCategory.CODE_ERROR,
        "severity": AlertSeverity.HIGH,
        "title": "Eksik Python Modülü Tespiti",
        "msg_tpl": "'{match}' modülü bulunamadı. Muhtemelen sanal ortam aktif değil veya paket yüklenmemiş.",
        "action_tpl": "pip install {match}",
        "auto_executable": True
    },
    {
        "pattern": r"ImportError:\s+cannot import name ['\"]([^'\"]+)['\"]",
        "category": AlertCategory.CODE_ERROR,
        "severity": AlertSeverity.HIGH,
        "title": "Python Import Hatası",
        "msg_tpl": "'{match}' ögesi içe aktarılamadı. Döngüsel import (circular dependency) veya isim çakışması olabilir.",
        "action_tpl": "İlgili modülü ve import sırasını denetle",
        "auto_executable": False
    },
    {
        "pattern": r"SyntaxError:\s+(.+)",
        "category": AlertCategory.CODE_ERROR,
        "severity": AlertSeverity.HIGH,
        "title": "Sözdizimi (Syntax) Hatası",
        "msg_tpl": "Kodda syntax hatası: {match}",
        "action_tpl": "Kodu sözdizimi kurallarına göre düzelt",
        "auto_executable": False
    },
    {
        "pattern": r"Traceback \(most recent call last\):",
        "category": AlertCategory.CODE_ERROR,
        "severity": AlertSeverity.HIGH,
        "title": "Çalışma Zamanı (Runtime) Hatası",
        "msg_tpl": "Aktif pencerede bir Python Traceback tespit edildi.",
        "action_tpl": "Hata logunu analiz et ve düzelt",
        "auto_executable": False
    },
    {
        "pattern": r"npm ERR!\s+(.+)",
        "category": AlertCategory.CODE_ERROR,
        "severity": AlertSeverity.HIGH,
        "title": "Node.js / NPM Paket Hatası",
        "msg_tpl": "NPM çalıştırma hatası tespit edildi: {match}",
        "action_tpl": "npm install",
        "auto_executable": True
    },
    {
        "pattern": r"Address already in use|EADDRINUSE.*:(\d+)",
        "category": AlertCategory.NETWORK_ISSUE,
        "severity": AlertSeverity.HIGH,
        "title": "Port Çakışması",
        "msg_tpl": "Hedef port zaten kullanımda: {match}",
        "action_tpl": "Portu kullanan süreci sonlandır",
        "auto_executable": True
    },
    {
        "pattern": r"OutOfMemoryError|MemoryError|out of memory",
        "category": AlertCategory.SYSTEM_STRESS,
        "severity": AlertSeverity.CRITICAL,
        "title": "Bellek Yetersizliği (Out of Memory)",
        "msg_tpl": "Sistem veya uygulama bellek sınırına ulaştı.",
        "action_tpl": "Bellek tüketen arka plan süreçlerini temizle",
        "auto_executable": True
    },
    {
        "pattern": r"Access is denied|PermissionError:\s+\[WinError 5\]",
        "category": AlertCategory.SECURITY_WARNING,
        "severity": AlertSeverity.HIGH,
        "title": "Erişim Engellendi (Yetki Hatası)",
        "msg_tpl": "Dosya veya kaynağa erişim yetkisi reddedildi.",
        "action_tpl": "Yönetici yetkileriyle yeniden dene veya izinleri kontrol et",
        "auto_executable": False
    },
]


class ProactiveWatcherEngine:
    """
    Arka planda düşük CPU ile sistemi, ekranı ve kaynakları izleyen proaktif zeka motoru.
    """

    def __init__(self, check_interval_sec: float = 3.5):
        self.check_interval_sec = check_interval_sec
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._lock = threading.RLock()
        
        self._alerts: list[ProactiveAlert] = []
        self._max_history = 50
        self._cooldowns: dict[str, float] = {}  # alert_key -> timestamp
        self._cooldown_period_sec = 60.0        # Aynı hata için 60 saniye bildirim kısıtlaması
        
        # Olay Dinleyicileri (WebSocket ve Ses Hattı için)
        self._listeners: list[Callable[[ProactiveAlert], None]] = []

    def register_listener(self, callback: Callable[[ProactiveAlert], None]) -> None:
        """Yeni bir proaktif bildirim dinleyicisi ekler."""
        with self._lock:
            if callback not in self._listeners:
                self._listeners.append(callback)

    def unregister_listener(self, callback: Callable[[ProactiveAlert], None]) -> None:
        with self._lock:
            if callback in self._listeners:
                self._listeners.remove(callback)

    def _broadcast_alert(self, alert: ProactiveAlert) -> None:
        """Tüm kayıtlı dinleyicilere (WebSocket, UI, Voice) alert gönderir."""
        with self._lock:
            listeners = list(self._listeners)
        for cb in listeners:
            try:
                cb(alert)
            except Exception as e:
                logger.debug(f"Proaktif dinleyici hatası: {e}")

    # ── Metin & Ekran Analizi ──────────────────────────────────────────────────
    def analyze_text_content(self, text: str, source_app: str = "") -> list[ProactiveAlert]:
        """Verilen metin bloğunda hata imzalarını arar ve alarm üretir."""
        if not text or not text.strip():
            return []

        generated: list[ProactiveAlert] = []
        now = time.time()

        for pattern_info in ERROR_PATTERNS:
            regex = pattern_info["pattern"]
            match = re.search(regex, text, re.IGNORECASE)
            if match:
                matched_val = match.group(1) if match.groups() else match.group(0)
                cooldown_key = f"{pattern_info['title']}:{matched_val}"
                
                # Cooldown kontrolü (Aynı hatayı sürekli spamlamamak için)
                last_time = self._cooldowns.get(cooldown_key, 0.0)
                if now - last_time < self._cooldown_period_sec:
                    continue

                self._cooldowns[cooldown_key] = now
                msg = pattern_info["msg_tpl"].format(match=matched_val)
                action = pattern_info["action_tpl"].format(match=matched_val)

                alert = ProactiveAlert(
                    alert_id=f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                    timestamp=now,
                    category=pattern_info["category"],
                    severity=pattern_info["severity"],
                    title=pattern_info["title"],
                    message=msg,
                    detected_snippet=text[:300].strip(),
                    suggested_action=action,
                    auto_executable=pattern_info["auto_executable"],
                    target_app=source_app
                )

                with self._lock:
                    self._alerts.append(alert)
                    if len(self._alerts) > self._max_history:
                        self._alerts.pop(0)

                generated.append(alert)
                self._broadcast_alert(alert)

        return generated

    # ── Sistem Kaynak Kontrolü ───────────────────────────────────────────────
    def check_system_stress(self) -> list[ProactiveAlert]:
        """CPU, RAM ve Disk doluluğunu denetler."""
        alerts: list[ProactiveAlert] = []
        now = time.time()

        try:
            cpu_percent = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()
            disk = psutil.disk_usage(os.path.abspath(os.sep))

            # 1. Aşırı CPU Kullanımı (> 92%)
            if cpu_percent > 92.0:
                key = "SYSTEM_HIGH_CPU"
                if now - self._cooldowns.get(key, 0.0) >= self._cooldown_period_sec:
                    self._cooldowns[key] = now
                    alert = ProactiveAlert(
                        alert_id=f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                        timestamp=now,
                        category=AlertCategory.SYSTEM_STRESS,
                        severity=AlertSeverity.HIGH,
                        title="Yüksek CPU Yükü Tespiti",
                        message=f"CPU kullanımı kritik seviyede: %{cpu_percent:.1f}",
                        suggested_action="Ağır arka plan işlemlerini optimize et veya sınırla",
                        auto_executable=False
                    )
                    with self._lock:
                        self._alerts.append(alert)
                    alerts.append(alert)
                    self._broadcast_alert(alert)

            # 2. Aşırı RAM Kullanımı (> 94%)
            if ram.percent > 94.0:
                key = "SYSTEM_HIGH_RAM"
                if now - self._cooldowns.get(key, 0.0) >= self._cooldown_period_sec:
                    self._cooldowns[key] = now
                    alert = ProactiveAlert(
                        alert_id=f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                        timestamp=now,
                        category=AlertCategory.SYSTEM_STRESS,
                        severity=AlertSeverity.CRITICAL,
                        title="Kritik RAM Doluluğu",
                        message=f"Kullanılabilir RAM %{100 - ram.percent:.1f} seviyesine indi ({ram.available / (1024*1024):.0f} MB boş).",
                        suggested_action="Kullanılmayan önbellek ve süreçleri serbest bırak",
                        auto_executable=True
                    )
                    with self._lock:
                        self._alerts.append(alert)
                    alerts.append(alert)
                    self._broadcast_alert(alert)

            # 3. Düşük Disk Alanı (< 5 GB)
            free_gb = disk.free / (1024 * 1024 * 1024)
            if free_gb < 5.0:
                key = "SYSTEM_LOW_DISK"
                if now - self._cooldowns.get(key, 0.0) >= (self._cooldown_period_sec * 3):
                    self._cooldowns[key] = now
                    alert = ProactiveAlert(
                        alert_id=f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                        timestamp=now,
                        category=AlertCategory.SYSTEM_STRESS,
                        severity=AlertSeverity.HIGH,
                        title="Düşük Disk Alanı",
                        message=f"Ana diskte yalnızca {free_gb:.2f} GB boş alan kaldı.",
                        suggested_action="Geçici dosyaları ve önbelleği temizle",
                        auto_executable=False
                    )
                    with self._lock:
                        self._alerts.append(alert)
                    alerts.append(alert)
                    self._broadcast_alert(alert)

        except Exception as e:
            logger.debug(f"Sistem kaynak denetimi hatası: {e}")

        return alerts

    # ── İzleme Döngüsü ───────────────────────────────────────────────────────
    def _run_loop(self) -> None:
        logger.info("[Proactive Watcher] 👁️ Arka plan gölge gözlemci aktif.")
        while self._running:
            try:
                # 1. Sistem Metriklerini Kontrol Et
                self.check_system_stress()

                # 2. Ekran Değişimini ve Aktif Pencereyi Gözlemle
                screen_ctx = screen_awareness.observe_screen(force_full_analysis=False)
                
                # Sadece belirgin değişimlerde metin analizi yap (CPU tasarrufu)
                if screen_ctx.change_severity in (ChangeSeverity.SIGNIFICANT_CHANGE, ChangeSeverity.MAJOR_CHANGE):
                    active_title = screen_ctx.active_window.get("title", "")
                    active_proc = screen_ctx.active_window.get("process", "")
                    
                    combined_text = active_title + "\n" + "\n".join(screen_ctx.detected_texts)
                    self.analyze_text_content(combined_text, source_app=active_proc or active_title)

                # 3. Görsel (Vision) Derin Analiz - Sadece Hata/Modal Tespit Edilirse ve Cooldown Yoksa
                if screen_ctx.has_error_box or screen_ctx.has_modal_dialog:
                    vision_key = f"VISION_ERROR_{screen_ctx.active_window.get('title', '')}"
                    now = time.time()
                    if now - self._cooldowns.get(vision_key, 0.0) >= self._cooldown_period_sec * 2:
                        self._cooldowns[vision_key] = now
                        from actions.screen_vision import analyze_screen
                        logger.info(f"[Proactive Watcher] 👁️ Şüpheli ekran aktivitesi ({vision_key}), Vision modeline gönderiliyor...")
                        prompt = (
                            "Ekranda bir hata penceresi veya uyarı modalı tespit ettim. "
                            "Eğer ekranda gerçekten bir hata, kilitlenme, uyarı, veya "
                            "çözülmesi gereken bir sorun varsa kısaca 1-2 cümleyle ne olduğunu yaz. "
                            "Eğer tamamen normal veya rutin bir pencereyse SADECE 'YOK' yaz."
                        )
                        try:
                            vision_res = analyze_screen(query=prompt, target="active_window")
                            if vision_res and "YOK" not in vision_res.upper() and len(vision_res) > 8:
                                alert = ProactiveAlert(
                                    alert_id=f"ALERT-{uuid.uuid4().hex[:8].upper()}",
                                    timestamp=time.time(),
                                    category=AlertCategory.CODE_ERROR,
                                    severity=AlertSeverity.HIGH,
                                    title="Otonom Görsel Tespit (Vision)",
                                    message=vision_res,
                                    suggested_action="Düzeltmek için bana sor veya otonom aksiyon başlat.",
                                    auto_executable=False,
                                    target_app=screen_ctx.active_window.get("process", "")
                                )
                                with self._lock:
                                    self._alerts.append(alert)
                                self._broadcast_alert(alert)
                        except Exception as e:
                            logger.debug(f"[Proactive Watcher] Vision analizi hatası: {e}")

            except Exception as e:
                logger.debug(f"[Proactive Watcher] Döngü adımı hatası: {e}")

            time.sleep(self.check_interval_sec)

    def start_watcher(self) -> None:
        """Gözlemci arka plan iş parçacığını başlatır."""
        with self._lock:
            if self._running:
                return
            self._running = True
            self._thread = threading.Thread(target=self._run_loop, name="UltronProactiveWatcher", daemon=True)
            self._thread.start()

    def stop_watcher(self) -> None:
        """Gözlemciyi güvenle durdurur."""
        with self._lock:
            self._running = False
            if self._thread and self._thread.is_alive():
                self._thread.join(timeout=1.0)
            self._thread = None
        logger.info("[Proactive Watcher] 🛑 Gölge gözlemci durduruldu.")

    def get_active_alerts(self, limit: int = 10) -> list[dict[str, Any]]:
        """Bekleyen ve son üretilen proaktif alarmları döner."""
        with self._lock:
            return [a.to_dict() for a in reversed(self._alerts[-limit:])]

    def dismiss_alert(self, alert_id: str) -> bool:
        """Bir alarmı kapatıldı/yoksayıldı olarak işaretler."""
        with self._lock:
            for a in self._alerts:
                if a.alert_id == alert_id:
                    a.status = "DISMISSED"
                    return True
        return False

    def clear_all(self) -> None:
        """Tüm geçmiş alarmları temizler."""
        with self._lock:
            self._alerts.clear()
            self._cooldowns.clear()


# Canonical Global Singleton Instance
proactive_watcher = ProactiveWatcherEngine()
