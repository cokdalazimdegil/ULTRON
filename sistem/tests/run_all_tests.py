"""
ULTRON Master Test Runner — Tüm Mimari Testleri Toplu Çalıştırıcı (Phase 11)
═══════════════════════════════════════════════════════════════════════════
Tüm faz test paketlerini sırayla çalıştırır, sonuçları konsolide eder
ve tam regresyon raporunu üretir.

Çalıştırma:
    cd sistem
    python -X utf8 tests/run_all_tests.py
"""

import os
import sys
import time
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
BASE_DIR = TESTS_DIR.parent
sys.path.insert(0, str(BASE_DIR))

try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Ortam değişkenleri
os.environ["ULTRON_WEB_TOKEN"] = "master-test-token"
os.environ["ULTRON_PUBLIC"] = "0"

TEST_MODULES = [
    ("Phase 1: Event Bus", "test_event_bus"),
    ("Phase 2: Notification Engine", "test_notification_engine"),
    ("Phase 3: Webhook Gateway", "test_webhook_gateway"),
    ("Phase 4: Presence Engine", "test_presence_engine"),
    ("Phase 5: Location & Geofence", "test_location_geofence"),
    ("Phase 6: Email Proactivity", "test_email_proactivity"),
    ("Phase 7 & 8: Memory & Local RAG", "test_memory_and_rag"),
    ("Phase 9: Companion Mode", "test_companion_mode"),
    ("Phase 10: UI, Logs, Swarm & Research", "test_ui_logs_swarm_research"),
    ("Phase 11: CPU & Resource Optimizations", "test_cpu_optimization"),
]


def run_master_suite():
    print("\n" + "═" * 70)
    print("  🚀 ULTRON MASTER MİMARİ REGRESYON TESTİ (ALL PHASES)")
    print("═" * 70)

    start_time = time.time()
    results = []

    for phase_name, module_name in TEST_MODULES:
        print(f"\n▶ [{phase_name}] çalıştırılıyor ({module_name}.py)...")
        mod_start = time.time()
        try:
            import importlib
            if module_name in sys.modules:
                del sys.modules[module_name]
            mod = importlib.import_module(f"tests.{module_name}")
            success = mod.run_all_tests()
            dur = time.time() - mod_start
            results.append((phase_name, success, dur, None))
        except Exception as e:
            dur = time.time() - mod_start
            results.append((phase_name, False, dur, str(e)))

    total_dur = time.time() - start_time
    total_suites = len(results)
    passed_suites = sum(1 for _, s, _, _ in results if s)
    failed_suites = total_suites - passed_suites

    print("\n" + "═" * 70)
    print("  📊 GENEL REGRESYON TEST RAPORU")
    print("═" * 70 + "\n")

    for name, success, dur, err in results:
        status_icon = "  [✓] PASSED" if success else "  [✗] FAILED"
        err_msg = f" — Hata: {err}" if err else ""
        print(f"{status_icon}  {name:<35} ({dur:.2f}s){err_msg}")

    print("\n" + "─" * 70)
    print(f"  Toplam Test Paketi: {total_suites} | Başarılı: {passed_suites} | Başarısız: {failed_suites}")
    print(f"  Toplam Süre:        {total_dur:.2f} saniye")
    if failed_suites == 0:
        print("  🎉 TÜM MİMARİ TESTLER EKSİKSİZ VE BAŞARIYLA GEÇTİ!")
    else:
        print("  ⚠️ BAZI TESTLER BAŞARISIZ OLDU!")
    print("═" * 70 + "\n")

    return failed_suites == 0


if __name__ == "__main__":
    success = run_master_suite()
    sys.exit(0 if success else 1)
