"""
ULTRON Notification Engine — Phase 2 Test Suite
════════════════════════════════════════════════
Bildirim motorunun cooldown, dedup, quiet hours, kanal yönlendirme
ve priority-based politika testleri.

Calistirma:
    cd sistem
    python -X utf8 tests/test_notification_engine.py
"""

import sys
import time
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
BASE_DIR = TEST_DIR.parent
sys.path.insert(0, str(BASE_DIR))

# __init__.py atlanarak dogrudan modul yukle
import importlib.util

def _load_module_from_file(name: str, filepath: str):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_events_mod = _load_module_from_file("core.events", str(BASE_DIR / "core" / "events.py"))
_bus_mod = _load_module_from_file("core.event_bus", str(BASE_DIR / "core" / "event_bus.py"))
_notif_mod = _load_module_from_file("core.notification_engine", str(BASE_DIR / "core" / "notification_engine.py"))

EventPriority = _events_mod.EventPriority
EventSource = _events_mod.EventSource
NotificationEngine = _notif_mod.NotificationEngine
NotificationRequest = _notif_mod.NotificationRequest
NotificationChannel = _notif_mod.NotificationChannel


def get_clean_engine() -> NotificationEngine:
    engine = NotificationEngine()
    engine.reset()
    engine._channel_handlers.clear()
    engine.configure(default_cooldown=0.1, dedup_window=0.1)
    engine.set_quiet_hours(23, 7, enabled=False)  # quiet hours kapat
    return engine


# =========================================================================
# 1. TEMEL BILDIRIM
# =========================================================================

def test_basic_notify():
    """Temel bildirim gonderdim."""
    engine = get_clean_engine()
    delivered = []

    def web_handler(title, message, priority, metadata):
        delivered.append({"title": title, "message": message})
        return True

    engine.register_channel("web_ui", web_handler)

    result = engine.notify(NotificationRequest(
        title="Test", message="Merhaba", priority=EventPriority.NORMAL
    ))

    assert result.delivered is True
    assert "web_ui" in result.channels_used
    assert len(delivered) == 1
    print("  [PASS] Temel bildirim gonderimi")


# =========================================================================
# 2. PRIORITY-BASED KANAL SECIMI
# =========================================================================

def test_priority_channels():
    """Oncelik bazli otomatik kanal secimi."""
    engine = get_clean_engine()
    web_calls = []
    tts_calls = []
    gemini_calls = []

    engine.register_channel("web_ui", lambda **kw: web_calls.append(1) or True)
    engine.register_channel("tts", lambda **kw: tts_calls.append(1) or True)
    engine.register_channel("gemini", lambda **kw: gemini_calls.append(1) or True)

    # LOW = sadece log (web_ui'a gitmemeli)
    engine.notify(NotificationRequest(
        title="Low", message="Dusuk", priority=EventPriority.LOW
    ))
    assert len(web_calls) == 0, "LOW oncelik web_ui'a gitmemeli"

    # NORMAL = web_ui
    time.sleep(0.15)
    engine.notify(NotificationRequest(
        title="Normal", message="Normal", priority=EventPriority.NORMAL
    ))
    assert len(web_calls) == 1, "NORMAL oncelik web_ui'a gitmeli"
    assert len(gemini_calls) == 0, "NORMAL oncelik gemini'ye gitmemeli"

    # HIGH = web_ui + gemini
    time.sleep(0.15)
    engine.notify(NotificationRequest(
        title="High", message="Yuksek", priority=EventPriority.HIGH
    ))
    assert len(web_calls) == 2
    assert len(gemini_calls) == 1

    # CRITICAL = web_ui + gemini + tts
    time.sleep(0.15)
    engine.notify(NotificationRequest(
        title="Crit", message="Kritik", priority=EventPriority.CRITICAL
    ))
    assert len(tts_calls) == 1
    print("  [PASS] Priority-based kanal secimi")


# =========================================================================
# 3. COOLDOWN
# =========================================================================

def test_cooldown():
    """Cooldown suresi icindeki tekrar bildirimler bastirilir."""
    engine = get_clean_engine()
    engine.configure(default_cooldown=1.0)  # 1 saniye
    delivered = []

    engine.register_channel("web_ui", lambda **kw: delivered.append(1) or True)

    r1 = engine.notify(NotificationRequest(
        title="CD Test", message="Ilk", priority=EventPriority.NORMAL
    ))
    r2 = engine.notify(NotificationRequest(
        title="CD Test2", message="Ikinci", priority=EventPriority.NORMAL,
        cooldown_key="system:CD Test"
    ))

    assert r1.delivered is True
    assert r2.suppressed_reason == "cooldown"
    assert len(delivered) == 1
    print("  [PASS] Cooldown engelleme")


# =========================================================================
# 4. DEDUPLICATION
# =========================================================================

def test_deduplication():
    """Ayni mesajin kisa surede tekrarini engeller."""
    engine = get_clean_engine()
    engine.configure(default_cooldown=0.0, dedup_window=2.0)
    delivered = []

    engine.register_channel("web_ui", lambda **kw: delivered.append(1) or True)

    r1 = engine.notify(NotificationRequest(
        title="Dedup", message="Ayni mesaj", priority=EventPriority.NORMAL
    ))
    r2 = engine.notify(NotificationRequest(
        title="Dedup", message="Ayni mesaj", priority=EventPriority.NORMAL
    ))

    assert r1.delivered is True
    assert r2.suppressed_reason == "duplicate"
    print("  [PASS] Deduplication")


# =========================================================================
# 5. QUIET HOURS
# =========================================================================

def test_quiet_hours():
    """Quiet hours'ta dusuk oncelikli bildirimler bastirilir."""
    engine = get_clean_engine()
    import datetime
    current_hour = datetime.datetime.now().hour

    # Quiet hours'u mevcut saat icine al
    engine.set_quiet_hours(current_hour, (current_hour + 2) % 24, enabled=True)
    delivered = []
    engine.register_channel("web_ui", lambda **kw: delivered.append(1) or True)

    r_normal = engine.notify(NotificationRequest(
        title="QH Normal", message="Normal", priority=EventPriority.NORMAL
    ))
    assert r_normal.suppressed_reason == "quiet_hours"

    # HIGH oncelik quiet hours'ta bile gecmeli
    r_high = engine.notify(NotificationRequest(
        title="QH High", message="Acil", priority=EventPriority.HIGH
    ))
    assert r_high.delivered is True
    print("  [PASS] Quiet hours engelleme")


# =========================================================================
# 6. OZEL KANAL BELIRTME
# =========================================================================

def test_explicit_channels():
    """Istekte ozel kanal belirtme."""
    engine = get_clean_engine()
    tts_calls = []
    web_calls = []

    engine.register_channel("tts", lambda **kw: tts_calls.append(1) or True)
    engine.register_channel("web_ui", lambda **kw: web_calls.append(1) or True)

    result = engine.notify(NotificationRequest(
        title="Sadece TTS", message="Sesli bildirim",
        priority=EventPriority.NORMAL,
        channels=["tts"],
    ))

    assert len(tts_calls) == 1
    assert len(web_calls) == 0
    assert "tts" in result.channels_used
    print("  [PASS] Ozel kanal belirtme")


# =========================================================================
# 7. HANDLER HATASI IZOLASYONU
# =========================================================================

def test_handler_error_isolation():
    """Bir kanalda hata olursa diger kanallar etkilenmez."""
    engine = get_clean_engine()
    delivered = []

    def bad_handler(**kw):
        raise RuntimeError("Kanal hatasi!")

    def good_handler(**kw):
        delivered.append(1)
        return True

    engine.register_channel("web_ui", bad_handler)
    engine.register_channel("tts", good_handler)

    result = engine.notify(NotificationRequest(
        title="Error Test", message="Hata",
        priority=EventPriority.CRITICAL,
        channels=["web_ui", "tts"]
    ))

    assert len(delivered) == 1
    assert "tts" in result.channels_used
    print("  [PASS] Handler hatasi izolasyonu")


# =========================================================================
# 8. ISTATISTIKLER
# =========================================================================

def test_stats():
    """Istatistik kaydi."""
    engine = get_clean_engine()
    engine.register_channel("web_ui", lambda **kw: True)

    engine.notify(NotificationRequest(
        title="Stat1", message="m1", priority=EventPriority.NORMAL
    ))
    time.sleep(0.15)
    engine.notify(NotificationRequest(
        title="Stat2", message="m2", priority=EventPriority.NORMAL
    ))

    stats = engine.get_stats()
    assert stats["total_sent"] == 2
    assert stats["by_channel"].get("web_ui", 0) == 2
    print("  [PASS] Istatistik kaydi")


# =========================================================================
# RUNNER
# =========================================================================

def run_all_tests():
    tests = [
        test_basic_notify,
        test_priority_channels,
        test_cooldown,
        test_deduplication,
        test_quiet_hours,
        test_explicit_channels,
        test_handler_error_isolation,
        test_stats,
    ]

    print("\n" + "=" * 60)
    print("  ULTRON Notification Engine — Phase 2 Test Suite")
    print("=" * 60 + "\n")

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  [FAIL] {test.__name__}: {e}")

    print("\n" + "-" * 60)
    print(f"  Sonuc: {passed} PASSED, {failed} FAILED / {len(tests)} toplam")
    print("-" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
