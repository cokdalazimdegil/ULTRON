"""
ULTRON Event Bus — Phase 1 Test Suite
═════════════════════════════════════
Event Bus'ın temel işlevselliğini ve geriye dönük uyumluluğu doğrular.

Çalıştırma:
    cd sistem
    python -m pytest tests/test_event_bus.py -v
    veya
    python tests/test_event_bus.py
"""

import sys
import asyncio
import time
from pathlib import Path

# Proje kök dizinine erişim
TEST_DIR = Path(__file__).resolve().parent
BASE_DIR = TEST_DIR.parent
sys.path.insert(0, str(BASE_DIR))

# ── Test Modülleri ──────────────────────────────────────────────────────────
# NOT: core/__init__.py ağır bağımlılıklar (cv2, numpy) tetikler.
# importlib.util ile doğrudan dosyadan yüklüyoruz — __init__.py atlanır.
import importlib.util

def _load_module_from_file(name: str, filepath: str):
    spec = importlib.util.spec_from_file_location(name, filepath)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # event_bus.py core.events'e bağlı olduğu için cache'le
    spec.loader.exec_module(mod)
    return mod

_events_mod = _load_module_from_file("core.events", str(BASE_DIR / "core" / "events.py"))
_bus_mod = _load_module_from_file("core.event_bus", str(BASE_DIR / "core" / "event_bus.py"))

UltronEvent = _events_mod.UltronEvent
EventPriority = _events_mod.EventPriority
EventSource = _events_mod.EventSource
EventBus = _bus_mod.EventBus

# Test başlamadan önce temiz singleton
def get_clean_bus() -> EventBus:
    """Her test için temiz bir EventBus döner."""
    bus = EventBus()
    bus.reset()
    return bus


# ═══════════════════════════════════════════════════════════════════════════
# 1. TEMEL İŞLEVSELLİK
# ═══════════════════════════════════════════════════════════════════════════

def test_events_dataclass():
    """UltronEvent oluşturma ve serialization."""
    event = UltronEvent(
        event_type="user.arrived_home",
        source=EventSource.LOCATION,
        payload={"lat": 41.01, "lon": 28.97},
        priority=EventPriority.HIGH,
    )
    assert event.event_type == "user.arrived_home"
    assert event.source == "location"
    assert event.priority == EventPriority.HIGH
    assert event.domain == "user"
    assert len(event.event_id) == 12

    # Serialization round-trip
    d = event.to_dict()
    assert d["priority"] == 80
    restored = UltronEvent.from_dict(d)
    assert restored.event_type == event.event_type
    assert restored.priority == EventPriority.HIGH
    print("  ✅ UltronEvent dataclass")


def test_backward_compat_subscribe_publish():
    """Eski API: bus.subscribe(str, callback) ve bus.publish(str, data)."""
    bus = get_clean_bus()
    received = []

    def on_alert(data):
        received.append(data)

    bus.subscribe("ui_alert", on_alert)
    bus.publish("ui_alert", "Test mesajı")

    assert len(received) == 1
    assert received[0] == "Test mesajı"
    print("  ✅ Geriye dönük uyumlu subscribe/publish (string data)")


def test_backward_compat_dict_payload():
    """Eski API: dict payload ile publish."""
    bus = get_clean_bus()
    received = []

    def on_presence(data):
        received.append(data)

    bus.subscribe("observer_presence", on_presence)
    bus.publish("observer_presence", {"present": True})

    assert len(received) == 1
    assert received[0] == {"present": True}
    print("  ✅ Geriye dönük uyumlu subscribe/publish (dict payload)")


# ═══════════════════════════════════════════════════════════════════════════
# 2. WILDCARD PATTERN MATCHING
# ═══════════════════════════════════════════════════════════════════════════

def test_wildcard_star():
    """'*' ile tüm event'leri alma."""
    bus = get_clean_bus()
    received = []

    def on_all(data):
        received.append(data)

    bus.subscribe("*", on_all)
    bus.publish("anything", "a")
    time.sleep(0.01)  # dedup window
    bus.publish("something.else", "b")

    assert len(received) == 2
    print("  ✅ Wildcard '*' (tüm event'ler)")


def test_wildcard_prefix():
    """'camera.*' ile camera domain'i altındaki event'leri alma."""
    bus = get_clean_bus()
    received = []

    def on_camera(data):
        received.append(data)

    bus.subscribe("camera.*", on_camera)
    bus.publish("camera.face_detected", {"face": True})
    time.sleep(0.01)
    bus.publish("camera.person_left", {"face": False})
    time.sleep(0.01)
    bus.publish("user.arrived_home", {})  # Bu gelmemeli

    assert len(received) == 2
    print("  ✅ Wildcard 'camera.*' (prefix matching)")


# ═══════════════════════════════════════════════════════════════════════════
# 3. ASYNC CALLBACK DESTEĞİ
# ═══════════════════════════════════════════════════════════════════════════

def test_async_callback():
    """Async callback'in çalışması."""
    bus = get_clean_bus()
    received = []

    async def on_event(data):
        received.append(data)

    bus.subscribe("async.test", on_event)
    bus.publish("async.test", "async_data")

    # Async callback run_coroutine_threadsafe veya asyncio.run ile çalışır
    time.sleep(0.1)  # async callback'in tamamlanmasını bekle
    assert len(received) == 1
    print("  ✅ Async callback desteği")


# ═══════════════════════════════════════════════════════════════════════════
# 4. DEDUPLICATION
# ═══════════════════════════════════════════════════════════════════════════

def test_deduplication():
    """Aynı event_type + payload kısa sürede tekrar fırlatılmasını engeller."""
    bus = get_clean_bus()
    received = []

    def on_event(data):
        received.append(data)

    bus.subscribe("dedup.test", on_event)

    bus.publish("dedup.test", {"key": "value"})
    bus.publish("dedup.test", {"key": "value"})  # Bu engellenmeli
    bus.publish("dedup.test", {"key": "value"})  # Bu da engellenmeli

    assert len(received) == 1, f"Beklenen: 1, Gelen: {len(received)}"
    print("  ✅ Deduplication (aynı payload)")


def test_dedup_different_payload():
    """Farklı payload'lar dedup edilmemeli."""
    bus = get_clean_bus()
    received = []

    def on_event(data):
        received.append(data)

    bus.subscribe("dedup.diff", on_event)

    bus.publish("dedup.diff", {"key": "value1"})
    bus.publish("dedup.diff", {"key": "value2"})  # Farklı payload → kabul

    assert len(received) == 2
    print("  ✅ Deduplication farklı payload'lar geçer")


# ═══════════════════════════════════════════════════════════════════════════
# 5. COOLDOWN
# ═══════════════════════════════════════════════════════════════════════════

def test_cooldown():
    """Cooldown süresi içindeki tekrar yayınları engeller."""
    bus = get_clean_bus()
    received = []

    def on_event(data):
        received.append(data)

    bus.subscribe("cool.test", on_event)
    bus.set_cooldown("cool.test", 0.5)  # 500ms cooldown

    bus.publish("cool.test", {"n": 1})
    bus.publish("cool.test", {"n": 2})  # Engellenmeli (cooldown)

    assert len(received) == 1
    print("  ✅ Cooldown engelleme")


# ═══════════════════════════════════════════════════════════════════════════
# 6. FAILURE ISOLATION
# ═══════════════════════════════════════════════════════════════════════════

def test_failure_isolation():
    """Bir callback'teki hata diğerlerini etkilememeli."""
    bus = get_clean_bus()
    received = []

    def bad_callback(data):
        raise RuntimeError("Test hatası!")

    def good_callback(data):
        received.append(data)

    bus.subscribe("fail.test", bad_callback, priority=EventPriority.HIGH)
    bus.subscribe("fail.test", good_callback, priority=EventPriority.LOW)

    bus.publish("fail.test", "data")

    assert len(received) == 1, "İyi callback hâlâ çalışmalı"
    print("  ✅ Failure isolation (hatalı callback diğerlerini etkilemiyor)")


# ═══════════════════════════════════════════════════════════════════════════
# 7. PRIORITY ORDERING
# ═══════════════════════════════════════════════════════════════════════════

def test_priority_ordering():
    """Yüksek öncelikli subscriber'lar önce çağrılmalı."""
    bus = get_clean_bus()
    order = []

    def low_cb(data):
        order.append("low")

    def high_cb(data):
        order.append("high")

    def normal_cb(data):
        order.append("normal")

    bus.subscribe("prio.test", low_cb, priority=EventPriority.LOW)
    bus.subscribe("prio.test", high_cb, priority=EventPriority.HIGH)
    bus.subscribe("prio.test", normal_cb, priority=EventPriority.NORMAL)

    bus.publish("prio.test", "data")

    assert order == ["high", "normal", "low"], f"Sıra yanlış: {order}"
    print("  ✅ Priority ordering")


# ═══════════════════════════════════════════════════════════════════════════
# 8. UNSUBSCRIBE
# ═══════════════════════════════════════════════════════════════════════════

def test_unsubscribe():
    """Abonelik kaldırma."""
    bus = get_clean_bus()
    received = []

    def on_event(data):
        received.append(data)

    bus.subscribe("unsub.test", on_event)
    bus.publish("unsub.test", "before")

    result = bus.unsubscribe("unsub.test", on_event)
    assert result is True

    bus.publish("unsub.test", "after")  # Bu gelmemeli
    time.sleep(0.01)

    assert len(received) == 1
    print("  ✅ Unsubscribe")


# ═══════════════════════════════════════════════════════════════════════════
# 9. EVENT HISTORY
# ═══════════════════════════════════════════════════════════════════════════

def test_event_history():
    """Event geçmişinin kaydedilmesi."""
    bus = get_clean_bus()
    bus.subscribe("hist.a", lambda d: None)
    bus.subscribe("hist.b", lambda d: None)

    bus.publish("hist.a", {"x": 1})
    time.sleep(0.01)
    bus.publish("hist.b", {"y": 2})

    history = bus.get_history()
    assert len(history) == 2

    filtered = bus.get_history(event_type="hist.a")
    assert len(filtered) == 1
    assert filtered[0]["event_type"] == "hist.a"
    print("  ✅ Event history & filtering")


# ═══════════════════════════════════════════════════════════════════════════
# 10. PUBLISH_EVENT (TİPLİ API)
# ═══════════════════════════════════════════════════════════════════════════

def test_publish_event():
    """Yeni tipli API: publish_event(UltronEvent)."""
    bus = get_clean_bus()
    received = []

    def on_event(data):
        received.append(data)

    bus.subscribe("typed.test", on_event)

    event = UltronEvent(
        event_type="typed.test",
        source=EventSource.OBSERVER,
        payload={"detected": True},
        priority=EventPriority.HIGH,
    )
    bus.publish_event(event)

    assert len(received) == 1
    assert received[0] == {"detected": True}
    print("  ✅ publish_event (tipli API)")


# ═══════════════════════════════════════════════════════════════════════════
# RUNNER
# ═══════════════════════════════════════════════════════════════════════════

def run_all_tests():
    tests = [
        test_events_dataclass,
        test_backward_compat_subscribe_publish,
        test_backward_compat_dict_payload,
        test_wildcard_star,
        test_wildcard_prefix,
        test_async_callback,
        test_deduplication,
        test_dedup_different_payload,
        test_cooldown,
        test_failure_isolation,
        test_priority_ordering,
        test_unsubscribe,
        test_event_history,
        test_publish_event,
    ]

    print("\n" + "=" * 60)
    print("  ULTRON Event Bus — Phase 1 Test Suite")
    print("=" * 60 + "\n")

    passed = 0
    failed = 0

    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            failed += 1
            print(f"  ❌ {test.__name__}: {e}")

    print("\n" + "-" * 60)
    print(f"  Sonuç: {passed} PASSED, {failed} FAILED / {len(tests)} toplam")
    print("-" * 60 + "\n")

    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
