"""
ULTRON Companion Mode Test Suite
════════════════════════════════
actions.companion_mode motorunun yaşam döngüsü, durum sorguları,
değişim tespiti ve agent tool entegrasyonu testleri.
"""

import sys
import time
from pathlib import Path

# Proje kökünü sys.path'e ekle
SISTEM_DIR = Path(__file__).resolve().parent.parent
if str(SISTEM_DIR) not in sys.path:
    sys.path.insert(0, str(SISTEM_DIR))

import unittest
from PIL import Image
from actions.companion_mode import companion_engine, CompanionEngine
from jarvis_web.agent import execute_tool
from starlette.testclient import TestClient
from jarvis_web.server import app


def test_companion_lifecycle():
    companion_engine.stop()
    assert not companion_engine.is_running()

    msg = companion_engine.start(interval_sec=5)
    assert "başlatıldı" in msg
    assert companion_engine.is_running()

    msg2 = companion_engine.start()
    assert "zaten devrede" in msg2

    msg_stop = companion_engine.stop()
    assert "kapatıldı" in msg_stop
    assert not companion_engine.is_running()
    print("  [PASS] CompanionEngine yaşam döngüsü (start/stop)")


def test_companion_status():
    status = companion_engine.get_status()
    assert "running" in status
    assert "interval_sec" in status
    assert "comment_count" in status
    print("  [PASS] CompanionEngine durum sorgusu (get_status)")


def test_companion_screen_change_detection():
    im1 = Image.new("L", (64, 36), color=128)
    assert companion_engine._has_screen_changed(im1) is True
    # Aynı görsel verildiğinde False olmalı
    assert companion_engine._has_screen_changed(im1) is False
    # Farklı görsel verildiğinde True olmalı
    im2 = Image.new("L", (64, 36), color=255)
    assert companion_engine._has_screen_changed(im2) is True
    print("  [PASS] Ekran değişim tespiti ve token optimizasyonu")


def test_companion_agent_tool_execution():
    res = execute_tool("start_companion_mode", {"interval_sec": 8})
    assert companion_engine.is_running()
    assert "başlatıldı" in res

    res2 = execute_tool("stop_companion_mode", {})
    assert not companion_engine.is_running()
    assert "kapatıldı" in res2
    print("  [PASS] Agent execute_tool (start_companion_mode / stop_companion_mode)")


def test_companion_fastapi_endpoints():
    client = TestClient(app)

    # GET status
    r_get = client.get("/api/companion/status")
    assert r_get.status_code == 200
    assert r_get.json()["ok"] is True

    # POST toggle start
    r_start = client.post("/api/companion/toggle", json={"action": "start", "interval_sec": 7})
    assert r_start.status_code == 200
    assert r_start.json()["running"] is True

    # POST toggle stop
    r_stop = client.post("/api/companion/toggle", json={"action": "stop"})
    assert r_stop.status_code == 200
    assert r_stop.json()["running"] is False
    print("  [PASS] FastAPI REST endpoints (/api/companion/status & toggle)")


def run_all_tests():
    print("\n" + "=" * 60)
    print("  ULTRON Companion Mode — Phase 9 Test Suite")
    print("=" * 60 + "\n")

    tests = [
        test_companion_lifecycle,
        test_companion_status,
        test_companion_screen_change_detection,
        test_companion_agent_tool_execution,
        test_companion_fastapi_endpoints,
    ]

    passed = 0
    failed = 0
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"  [FAIL] {test.__name__}: {e}")
            failed += 1

    print("\n" + "-" * 60)
    print(f"  Sonuç: {passed} PASSED, {failed} FAILED / {len(tests)} toplam")
    print("-" * 60 + "\n")
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
