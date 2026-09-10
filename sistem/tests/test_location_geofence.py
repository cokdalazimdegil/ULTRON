"""
ULTRON Location & Geofence Engine — Phase 5 Test Suite
══════════════════════════════════════════════════════
- Haversine mesafe doğruluğu
- Bölge ekleme, kaldırma, listeleme
- Bölgeye giriş (geofence.enter) tespiti
- Eve varış (user.arrived_home) özel event'i
- Aynı bölgede kalma (tekrar event fırlatmama)
- Bölgeden çıkış (geofence.exit) tespiti
- Evden ayrılış (user.left_home) özel event'i
- Çoklu kullanıcı bağımsız takibi
- Event Bus user.location.changed abonelik testi
- HA Bridge person event entegrasyonu

Çalıştırma:
    cd sistem
    python -X utf8 tests/test_location_geofence.py
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
_geofence = _load("core.geofence_engine", str(BASE_DIR / "core" / "geofence_engine.py"))
_presence = _load("core.presence_engine", str(BASE_DIR / "core" / "presence_engine.py"))
_ha = _load("core.ha_bridge", str(BASE_DIR / "core" / "ha_bridge.py"))

GeofenceEngine = _geofence.GeofenceEngine
haversine_distance_meters = _geofence.haversine_distance_meters
EventBus = _bus.EventBus
PresenceEngine = _presence.PresenceEngine
HomeAssistantBridge = _ha.HomeAssistantBridge


def get_clean_geofence():
    geo = GeofenceEngine()
    geo._save_to_disk = False
    geo.reset()
    bus = EventBus()
    bus.reset()
    geo._bus = bus
    return geo, bus


# Istanbul koordinatları test verisi
HOME_LAT, HOME_LNG = 41.0082, 28.9784    # Sultanahmet
WORK_LAT, WORK_LNG = 41.0766, 29.0125    # Levent (~9 km mesafe)


def test_haversine_accuracy():
    """Haversine formülü bilinen mesafeleri doğru hesaplamalı."""
    dist = haversine_distance_meters(HOME_LAT, HOME_LNG, WORK_LAT, WORK_LNG)
    # Sultanahmet - Levent arasi yaklasik 8.1 - 8.3 km
    assert 7800 < dist < 8500, f"Beklenmeyen mesafe: {dist}m"
    # Ayni nokta 0m
    dist_zero = haversine_distance_meters(HOME_LAT, HOME_LNG, HOME_LAT, HOME_LNG)
    assert dist_zero == 0.0
    print("  [PASS] Haversine mesafe doğruluğu")


def test_zone_management():
    """Bölge ekleme, listeleme ve kaldırma çalışmalı."""
    geo, _ = get_clean_geofence()
    geo.add_zone("home", HOME_LAT, HOME_LNG, radius_meters=200.0, description="Evim")
    geo.add_zone("office", WORK_LAT, WORK_LNG, radius_meters=100.0, description="Ofisim")

    zones = geo.get_zones()
    assert len(zones) == 2
    names = [z["name"] for z in zones]
    assert "home" in names and "office" in names

    assert geo.remove_zone("office") is True
    assert len(geo.get_zones()) == 1
    assert geo.remove_zone("non_existent") is False
    print("  [PASS] Bölge ekleme, listeleme ve silme")


def test_enter_home_zone():
    """Kullanıcı ev bölgesine girdiğinde geofence.enter ve user.arrived_home fırlatılmalı."""
    geo, bus = get_clean_geofence()
    geo.add_zone("home", HOME_LAT, HOME_LNG, radius_meters=150.0)

    enters = []
    arrived = []
    bus.subscribe("geofence.enter", lambda d: enters.append(d))
    bus.subscribe("user.arrived_home", lambda d: arrived.append(d))

    # Evin 50 metre yanina konum gonder
    lat_near = HOME_LAT + 0.0003  # ~33m
    lng_near = HOME_LNG + 0.0003
    res = geo.process_location("YARATICI", lat_near, lng_near)

    assert "home" in res["current_zones"]
    assert "home" in res["entered"]
    assert len(enters) == 1
    assert enters[0]["user"] == "YARATICI"
    assert enters[0]["zone"] == "home"

    assert len(arrived) == 1
    assert arrived[0]["user"] == "YARATICI"
    print("  [PASS] Eve varış (geofence.enter + user.arrived_home)")


def test_stay_in_zone_no_duplicate():
    """Kullanıcı bölge içinde hareket ederken tekrar enter eventi fırlatılmamalı."""
    geo, bus = get_clean_geofence()
    geo.add_zone("home", HOME_LAT, HOME_LNG, radius_meters=150.0)

    enters = []
    bus.subscribe("geofence.enter", lambda d: enters.append(d))

    # Ilk giris
    geo.process_location("YARATICI", HOME_LAT, HOME_LNG)
    assert len(enters) == 1

    # Bolge icinde kucuk hareket
    geo.process_location("YARATICI", HOME_LAT + 0.0001, HOME_LNG + 0.0001)
    # Tekrar enter firlatilmamali
    assert len(enters) == 1
    print("  [PASS] Bölge içinde kalırken tekrar event fırlatılmaması")


def test_exit_home_zone():
    """Kullanıcı ev bölgesinden çıktığında geofence.exit ve user.left_home fırlatılmalı."""
    geo, bus = get_clean_geofence()
    geo.add_zone("home", HOME_LAT, HOME_LNG, radius_meters=150.0)

    exits = []
    left = []
    bus.subscribe("geofence.exit", lambda d: exits.append(d))
    bus.subscribe("user.left_home", lambda d: left.append(d))

    # Once eve sok
    geo.process_location("YARATICI", HOME_LAT, HOME_LNG)
    assert geo.get_user_zones("YARATICI") == ["home"]

    # Simdi uzaklas (1 km oteye)
    res = geo.process_location("YARATICI", HOME_LAT + 0.01, HOME_LNG + 0.01)
    assert len(res["current_zones"]) == 0
    assert "home" in res["exited"]

    assert len(exits) == 1
    assert exits[0]["user"] == "YARATICI"
    assert exits[0]["zone"] == "home"

    assert len(left) == 1
    assert left[0]["user"] == "YARATICI"
    print("  [PASS] Evden ayrılış (geofence.exit + user.left_home)")


def test_multi_user_independent():
    """Farklı kullanıcılar bağımsız bölgelerde takip edilmeli."""
    geo, _ = get_clean_geofence()
    geo.add_zone("home", HOME_LAT, HOME_LNG, radius_meters=200.0)
    geo.add_zone("office", WORK_LAT, WORK_LNG, radius_meters=200.0)

    # YARATICI evde
    geo.process_location("YARATICI", HOME_LAT, HOME_LNG)
    # AILE_UYESI ofiste
    geo.process_location("AILE_UYESI", WORK_LAT, WORK_LNG)

    assert geo.get_user_zones("YARATICI") == ["home"]
    assert geo.get_user_zones("AILE_UYESI") == ["office"]
    print("  [PASS] Çoklu kullanıcı bağımsız takip")


def test_event_bus_location_listener():
    """Event Bus üzerinden user.location.changed geldiğinde geofence tetiklenmeli."""
    geo, bus = get_clean_geofence()
    geo.add_zone("home", HOME_LAT, HOME_LNG, radius_meters=150.0)
    geo.start()

    arrived = []
    bus.subscribe("user.arrived_home", lambda d: arrived.append(d))

    # Event Bus'a konum firlat
    bus.publish("user.location.changed", {
        "user": "YARATICI",
        "lat": HOME_LAT,
        "lng": HOME_LNG,
    })

    assert len(arrived) == 1
    assert arrived[0]["user"] == "YARATICI"
    print("  [PASS] Event Bus user.location.changed abonelik tetikleme")


def test_ha_bridge_person_home_triggers_presence():
    """HA'dan gelen person.nuri 'home' durumu PresenceEngine'i user_present yapar."""
    from core.presence_engine import presence_engine
    presence_engine.reset()
    bus = EventBus()
    bus.reset()
    presence_engine._bus = bus

    ha = HomeAssistantBridge()
    ha._bus = bus
    ha.start()

    # HA person.nuri event'i fırlat
    bus.publish("ha.person_status", {
        "entity_id": "person.nuri",
        "state": "home",
    })

    # PresenceEngine UNKNOWN -> USER_PRESENT geçmeli
    assert presence_engine.get_state().value == "user_present"
    print("  [PASS] HA person.nuri 'home' -> PresenceEngine USER_PRESENT")


def run_all_tests():
    tests = [
        test_haversine_accuracy,
        test_zone_management,
        test_enter_home_zone,
        test_stay_in_zone_no_duplicate,
        test_exit_home_zone,
        test_multi_user_independent,
        test_event_bus_location_listener,
        test_ha_bridge_person_home_triggers_presence,
    ]

    print("\n" + "=" * 60)
    print("  ULTRON Location & Geofence — Phase 5 Test Suite")
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
    print(f"  Sonuç: {passed} PASSED, {failed} FAILED / {len(tests)} toplam")
    print("-" * 60 + "\n")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
