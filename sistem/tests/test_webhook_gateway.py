"""
ULTRON Webhook Gateway — Phase 3 Test Suite
═══════════════════════════════════════════
- /api/webhook/v1/event (genel webhook)
- /api/webhook/homeassistant (HA entegrasyonu)
- /api/webhook/location (GPS takip)
- Yetkilendirme (token doğrulama)
- Rate limiting kontrolü
- Event Bus entegrasyonu

Çalıştırma:
    cd sistem
    python -X utf8 tests/test_webhook_gateway.py
"""

import sys
import os
import time
from pathlib import Path

TEST_DIR = Path(__file__).resolve().parent
BASE_DIR = TEST_DIR.parent
sys.path.insert(0, str(BASE_DIR))
sys.path.insert(0, str(BASE_DIR / "jarvis_web"))

# Ortam değişkenlerini test için ayarla
os.environ["ULTRON_WEB_TOKEN"] = "test-secret-token-123"
os.environ["ULTRON_PUBLIC"] = "0"

from starlette.testclient import TestClient
import jarvis_web.server as srv
from core.event_bus import bus
from core.events import EventSource, EventPriority

client = TestClient(srv.app)
AUTH_TOKEN = "test-secret-token-123"
srv.TOKEN = AUTH_TOKEN
srv.PUBLIC_MODE = False


def test_generic_webhook_success():
    """Genel webhook başarılı çağrıda Event Bus'a event fırlatmalı."""
    bus.reset()
    received = []
    bus.subscribe("test.incoming.alert", lambda d: received.append(d))

    payload = {
        "event_type": "test.incoming.alert",
        "source": "ios_shortcuts",
        "payload": {"message": "Kapı zili çaldı"},
        "priority": 75,
        "token": AUTH_TOKEN,
    }

    resp = client.post("/api/webhook/v1/event", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["event_type"] == "test.incoming.alert"
    assert len(received) == 1
    assert received[0]["message"] == "Kapı zili çaldı"
    print("  [PASS] Genel webhook başarıyla Event Bus'a iletildi")


def test_generic_webhook_unauthorized():
    """Hatalı token ile 401 dönmeli."""
    payload = {
        "event_type": "test.event",
        "token": "wrong-token",
    }
    resp = client.post("/api/webhook/v1/event", json=payload)
    assert resp.status_code == 200  # API returns JSON with code 401
    data = resp.json()
    assert data["status"] == "error"
    assert data.get("code") == 401
    print("  [PASS] Hatalı token 401 ile engellendi")


def test_generic_webhook_missing_event_type():
    """event_type eksikse hata dönmeli."""
    payload = {
        "token": AUTH_TOKEN,
        "payload": {"hello": "world"},
    }
    resp = client.post("/api/webhook/v1/event", json=payload)
    data = resp.json()
    assert data["status"] == "error"
    assert "event_type" in data["message"]
    print("  [PASS] Eksik event_type doğrulandı")


def test_homeassistant_webhook():
    """Home Assistant webhook event'i ha.* formatına dönüştürüp yayınlamalı."""
    bus.reset()
    ha_events = []
    bus.subscribe("ha.*", lambda d: ha_events.append(d))

    payload = {
        "event_type": "door_opened",
        "entity_id": "binary_sensor.front_door",
        "state": "on",
        "old_state": "off",
        "attributes": {"device_class": "door"},
        "token": AUTH_TOKEN,
    }

    resp = client.post("/api/webhook/homeassistant", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert data["ultron_event_type"] == "ha.door_opened"

    assert len(ha_events) == 1
    assert ha_events[0]["entity_id"] == "binary_sensor.front_door"
    assert ha_events[0]["state"] == "on"
    print("  [PASS] Home Assistant webhook'u alındı ve ha.door_opened olarak yayınlandı")


def test_location_webhook():
    """GPS location webhook konumu kaydetmeli ve user.location.changed yayınlamalı."""
    bus.reset()
    loc_events = []
    bus.subscribe("user.location.changed", lambda d: loc_events.append(d))

    payload = {
        "user": "YARATICI",
        "lat": 41.0082,
        "lng": 28.9784,
        "accuracy": 12.5,
        "speed": 1.2,
        "battery": 90,
        "token": AUTH_TOKEN,
    }

    resp = client.post("/api/webhook/location", json=payload)
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"

    assert len(loc_events) == 1
    assert loc_events[0]["user"] == "YARATICI"
    assert loc_events[0]["lat"] == 41.0082
    print("  [PASS] GPS location webhook konumu güncelledi ve event yayınladı")


def test_location_webhook_missing_coords():
    """Eksik koordinat hata dönmeli."""
    payload = {
        "user": "YARATICI",
        "token": AUTH_TOKEN,
    }
    resp = client.post("/api/webhook/location", json=payload)
    data = resp.json()
    assert data["status"] == "error"
    assert "lat ve lng" in data["message"]
    print("  [PASS] Eksik koordinat doğrulandı")


def test_rate_limiter():
    """Rate limit aşıldığında 429 dönmeli."""
    ip = "192.168.1.99"
    srv._webhook_rate_limiter.clear()

    # Rate limit kadar istek gönder
    limit = srv.WEBHOOK_RATE_LIMIT
    for _ in range(limit):
        allowed = srv._check_webhook_rate(ip)
        assert allowed is True

    # Limit aşıldı
    blocked = srv._check_webhook_rate(ip)
    assert blocked is False

    srv._webhook_rate_limiter.clear()
    print(f"  [PASS] Rate limiter {limit} istek sonrasında devrede")


def run_all_tests():
    tests = [
        test_generic_webhook_success,
        test_generic_webhook_unauthorized,
        test_generic_webhook_missing_event_type,
        test_homeassistant_webhook,
        test_location_webhook,
        test_location_webhook_missing_coords,
        test_rate_limiter,
    ]

    print("\n" + "=" * 60)
    print("  ULTRON Webhook Gateway — Phase 3 Test Suite")
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
