"""
ULTRON Daemon Manager (Arka Plan Hizmetleri Yöneticisi)
──────────────────────────────────────────────────────
Tüm arka plan asistanlarını ve thread'leri merkezi olarak
başlatıp durdurur.
"""

import logging

logger = logging.getLogger("ultron.core.daemon_manager")

class DaemonManager:
    def __init__(self):
        self.daemons = []

    def register(self, start_func, stop_func, name: str):
        """Başlatma ve durdurma fonksiyonlarını kaydeder."""
        self.daemons.append({
            "name": name,
            "start": start_func,
            "stop": stop_func
        })

    def start_all(self):
        for daemon in self.daemons:
            try:
                daemon["start"]()
                logger.info(f"[DaemonManager] {daemon['name']} başlatıldı.")
            except Exception as e:
                logger.error(f"[DaemonManager] {daemon['name']} başlatılamadı: {e}")

    def stop_all(self):
        for daemon in self.daemons:
            try:
                daemon["stop"]()
                logger.info(f"[DaemonManager] {daemon['name']} durduruldu.")
            except Exception as e:
                logger.error(f"[DaemonManager] {daemon['name']} durdurulamadı: {e}")

daemon_manager = DaemonManager()

# --- Modülleri İçe Aktar ve Kaydet ---
try:
    from computer.proactive_watcher import proactive_watcher
    daemon_manager.register(proactive_watcher.start_watcher, proactive_watcher.stop_watcher, "Proactive Watcher (Ekran/Hata)")
except Exception: pass

try:
    from computer.cyber_dog import cyber_dog
    daemon_manager.register(cyber_dog.start_patrol, cyber_dog.stop_patrol, "Cyber-Dog")
except Exception: pass

# Companion mode otomatik başlamaz, kullanıcı tetikler
# Swarm manager proje bazlı başlar
# Workspace Agent'ı kaydedelim:
try:
    from core.proactive_agent import workspace_agent
    daemon_manager.register(workspace_agent.start, workspace_agent.stop, "Workspace Agent")
except Exception: pass

# ── ULTRON 3.0 Arka Plan Servisleri ──────────────────────────────────────────

# Observer Daemon — Çevresel Farkındalık
try:
    from computer.observer_daemon import observer_daemon
    daemon_manager.register(
        observer_daemon.start,
        observer_daemon.stop,
        "Observer Daemon (Çevresel Farkındalık)"
    )
except Exception: pass

# Dream Engine — Bellek Konsolidasyonu
try:
    from memory.dream_engine import dream_engine
    daemon_manager.register(
        dream_engine.start,
        dream_engine.stop,
        "Dream Engine (Bellek Konsolidasyonu)"
    )
except Exception: pass

# ── ULTRON 4.0 Arka Plan Servisleri ──────────────────────────────────────────

# Semantic Desktop — Ekran Belleği
try:
    from computer.semantic_desktop import semantic_desktop
    daemon_manager.register(
        semantic_desktop.start,
        semantic_desktop.stop,
        "Semantic Desktop (Ekran Belleği)"
    )
except Exception: pass

# Desktop HUD — Şeffaf Masaüstü Arayüzü (sadece masaüstü/ajan modunda)
try:
    from computer.desktop_hud import desktop_hud
    daemon_manager.register(
        desktop_hud.start,
        desktop_hud.stop,
        "Desktop HUD (Şeffaf Masaüstü Arayüzü)"
    )
except Exception: pass

# ── ULTRON 5.0 Arka Plan Servisleri ──────────────────────────────────────────

# Heartbeat Engine — Otonom Zamanlı Görev Motoru (OpenClaw mimarisi)
try:
    from core.heartbeat_engine import heartbeat_engine
    daemon_manager.register(
        heartbeat_engine.start,
        heartbeat_engine.stop,
        "Heartbeat Engine (Otonom Zamanlayıcı)"
    )
except Exception: pass
