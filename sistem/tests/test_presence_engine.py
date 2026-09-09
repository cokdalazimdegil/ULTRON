"""
ULTRON Presence Engine — Phase 4 Test Suite
═══════════════════════════════════════════
State machine gecisleri, debounce, greeting cooldown ve
away timeout testleri.

Calistirma:
    cd sistem
    python -X utf8 tests/test_presence_engine.py
"""

import sys
import time
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
BASE_DIR = TEST_DIR.parent
sys.path.insert(0, str(BASE_DIR))

import importlib.util

def _load(name, fp):
    spec = importlib.util.spec_from_file_location(name, fp)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

_events = _load("core.events", str(BASE_DIR / "core" / "events.py"))
_bus = _load("core.event_bus", str(BASE_DIR / "core" / "event_bus.py"))
_presence = _load("core.presence_engine", str(BASE_DIR / "core" / "presence_engine.py"))

PresenceEngine = _presence.PresenceEngine
PresenceState = _presence.PresenceState
EventBus = _bus.EventBus


def get_clean_engine():
    engine = PresenceEngine()
    engine.reset()
    engine.configure(debounce_interval=0, greeting_cooldown=0, away_timeout=0.3)
    bus = EventBus()
    bus.reset()
    return engine, bus


# =========================================================================

def test_initial_state():
    """Baslangic durumu UNKNOWN olmali."""
    engine, _ = get_clean_engine()
    assert engine.get_state() == PresenceState.UNKNOWN
    print("  [PASS] Baslangic durumu UNKNOWN")


def test_person_detected():
    """Kamerada kisi goruldugunde UNKNOWN -> PERSON_DETECTED."""
    engine, _ = get_clean_engine()
    engine._trigger("person_detected")
    assert engine.get_state() == PresenceState.PERSON_DETECTED
    print("  [PASS] UNKNOWN -> PERSON_DETECTED")


def test_user_identified():
    """Kisi tanidiginda PERSON_DETECTED -> USER_PRESENT."""
    engine, _ = get_clean_engine()
    engine._trigger("person_detected")
    engine._trigger("user_identified")
    assert engine.get_state() == PresenceState.USER_PRESENT
    print("  [PASS] PERSON_DETECTED -> USER_PRESENT")


def test_no_person_from_present():
    """Kisi kayboldiginda USER_PRESENT -> USER_AWAY."""
    engine, _ = get_clean_engine()
    engine._trigger("person_detected")
    engine._trigger("user_identified")
    assert engine.get_state() == PresenceState.USER_PRESENT
    engine._trigger("no_person")
    assert engine.get_state() == PresenceState.USER_AWAY
    print("  [PASS] USER_PRESENT -> USER_AWAY")


def test_away_timeout_to_left():
    """USER_AWAY suresi dolunca USER_LEFT."""
    engine, _ = get_clean_engine()
    engine.configure(away_timeout=0.2)
    engine._trigger("person_detected")
    engine._trigger("user_identified")
    engine._trigger("no_person")
    assert engine.get_state() == PresenceState.USER_AWAY
    time.sleep(0.4)
    assert engine.get_state() == PresenceState.USER_LEFT
    print("  [PASS] USER_AWAY -> USER_LEFT (timeout)")


def test_return_from_away():
    """USER_AWAY'den kullanici donunce USER_PRESENT."""
    engine, _ = get_clean_engine()
    engine._trigger("person_detected")
    engine._trigger("user_identified")
    engine._trigger("no_person")
    assert engine.get_state() == PresenceState.USER_AWAY
    engine._trigger("person_detected")
    assert engine.get_state() == PresenceState.USER_PRESENT
    print("  [PASS] USER_AWAY -> USER_PRESENT (donus)")


def test_return_from_left():
    """USER_LEFT'ten kullanici donunce PERSON_DETECTED."""
    engine, _ = get_clean_engine()
    engine.configure(away_timeout=0.1)
    engine._trigger("person_detected")
    engine._trigger("user_identified")
    engine._trigger("no_person")
    time.sleep(0.2)
    assert engine.get_state() == PresenceState.USER_LEFT
    engine._trigger("person_detected")
    assert engine.get_state() == PresenceState.PERSON_DETECTED
    print("  [PASS] USER_LEFT -> PERSON_DETECTED (donus)")


def test_debounce():
    """Debounce suresi icinde gecis engellenir."""
    engine, _ = get_clean_engine()
    engine.configure(debounce_interval=1.0)
    engine._trigger("person_detected")
    assert engine.get_state() == PresenceState.PERSON_DETECTED
    # Hemen tekrar tetikleme — debounce engellemeli
    engine._trigger("user_identified")
    assert engine.get_state() == PresenceState.PERSON_DETECTED  # degismemeli
    print("  [PASS] Debounce engelleme")


def test_greeting_event():
    """Kullanici geldiginde greeting event firlatilir."""
    engine, bus = get_clean_engine()
    greeting_events = []
    bus.subscribe("presence.greeting_due", lambda d: greeting_events.append(d))

    engine._bus = bus
    engine._trigger("person_detected")
    engine._trigger("user_identified")

    assert len(greeting_events) == 1
    print("  [PASS] Greeting event firlatma")


def test_greeting_cooldown():
    """Greeting cooldown aktifken tekrar karsilama yapilmaz."""
    engine, bus = get_clean_engine()
    engine.configure(greeting_cooldown=10.0)
    greeting_events = []
    bus.subscribe("presence.greeting_due", lambda d: greeting_events.append(d))

    engine._bus = bus
    engine._trigger("person_detected")
    engine._trigger("user_identified")
    assert len(greeting_events) == 1

    # Kullanici ayrilip tekrar gelsin
    engine.configure(debounce_interval=0)
    engine._trigger("no_person")
    time.sleep(0.01)
    engine._trigger("person_detected")
    time.sleep(0.01)
    engine._trigger("user_identified")

    # Cooldown aktif — tekrar karsilama yok
    assert len(greeting_events) == 1
    print("  [PASS] Greeting cooldown")


def test_state_change_callback():
    """on_state_change callback'i cagrilir."""
    engine, _ = get_clean_engine()
    changes = []
    engine.on_state_change(lambda old, new: changes.append((old, new)))

    engine._trigger("person_detected")
    assert len(changes) == 1
    assert changes[0] == (PresenceState.UNKNOWN, PresenceState.PERSON_DETECTED)
    print("  [PASS] State change callback")


def test_state_info():
    """get_state_info detayli bilgi doner."""
    engine, _ = get_clean_engine()
    info = engine.get_state_info()
    assert "state" in info
    assert "last_change" in info
    assert "seconds_in_state" in info
    print("  [PASS] State info")


# =========================================================================

def run_all_tests():
    tests = [
        test_initial_state,
        test_person_detected,
        test_user_identified,
        test_no_person_from_present,
        test_away_timeout_to_left,
        test_return_from_away,
        test_return_from_left,
        test_debounce,
        test_greeting_event,
        test_greeting_cooldown,
        test_state_change_callback,
        test_state_info,
    ]

    print("\n" + "=" * 60)
    print("  ULTRON Presence Engine — Phase 4 Test Suite")
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
