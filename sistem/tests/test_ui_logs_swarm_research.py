"""
ULTRON UI, Logs, Swarm & Research Mode — Phase 10 Test Suite
══════════════════════════════════════════════════════════════
• PyWebviewApi Fullscreen Controller
• SystemLogHandler Ring Buffer & REST Endpoints
• Swarm Reporter Task Registration & API (/api/swarm/tasks)
• Deep Research Engine & Fallback Report Synthesizer
• Agent Tool Dispatching (deep_research)
"""

import os
import sys
import unittest
import logging
from pathlib import Path
from fastapi.testclient import TestClient

# Ana proje dizinini ekle
TEST_DIR = Path(__file__).resolve().parent
BASE_DIR = TEST_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from main import PyWebviewApi
from core.swarm_reporter import swarm_reporter
from actions.research_engine import handle_deep_research, _build_fallback_report
from jarvis_web.server import app, system_log_handler
from jarvis_web.agent import execute_tool


class TestPhase10Features(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_01_pywebview_fullscreen_api(self):
        """PyWebviewApi pencere kontrolünün doğru çalıştığını doğrular."""
        class MockWindow:
            def __init__(self):
                self.fullscreen = False
            def toggle_fullscreen(self):
                self.fullscreen = not self.fullscreen

        mock_win = MockWindow()
        api = PyWebviewApi(mock_win)
        self.assertFalse(api.is_fullscreen())
        
        res1 = api.toggle_fullscreen()
        self.assertTrue(res1)
        self.assertTrue(api.is_fullscreen())

        res2 = api.toggle_fullscreen()
        self.assertFalse(res2)
        self.assertFalse(api.is_fullscreen())
        print("  [PASS] PyWebviewApi Fullscreen denetleyici")

    def test_02_system_logs_ring_buffer(self):
        """Sistem log yöneticisinin logları topladığını ve temizlediğini doğrular."""
        # Log üret
        logger = logging.getLogger("ultron.test")
        logger.info("Test log mesajı #1001")
        
        resp = self.client.get("/api/system/logs?limit=50")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        self.assertIsInstance(data.get("logs"), list)
        self.assertGreater(len(data.get("logs")), 0)

        # Temizleme
        clear_resp = self.client.post("/api/system/logs/clear")
        self.assertEqual(clear_resp.status_code, 200)
        self.assertTrue(clear_resp.json().get("ok"))

        resp2 = self.client.get("/api/system/logs")
        self.assertEqual(len(resp2.json().get("logs")), 0)
        print("  [PASS] SystemLogHandler Ring Buffer & REST Endpoints")

    def test_03_swarm_reporter_and_api(self):
        """Ajan ağı konsolunun görev durumlarını bildirdiğini ve API'nin döndüğünü doğrular."""
        task_id = "test_subtask_999"
        swarm_reporter.register_task(
            task_id=task_id,
            agent_role="researcher",
            goal="Quantum computing report",
            plan_steps=["Arama yap", "Kaynak topla", "Sentezle"]
        )
        self.assertIn(task_id, swarm_reporter.get_active_tasks())

        swarm_reporter.update_task(task_id, progress=50)
        task_data = swarm_reporter.get_task(task_id)
        self.assertEqual(task_data["progress"], 50)

        # REST API doğrulaması
        resp = self.client.get("/api/swarm/tasks")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data.get("ok"))
        task_ids = [t["task_id"] for t in data.get("all_tasks", [])]
        self.assertIn(task_id, task_ids)

        swarm_reporter.complete_task(task_id, result_summary="Başarıyla tamamlandı")
        self.assertNotIn(task_id, swarm_reporter.get_active_tasks())
        print("  [PASS] Swarm Reporter & /api/swarm/tasks API")

    def test_04_deep_research_engine_fallback(self):
        """Araştırma motorunun fallback raporu ve parametre kontrolünü doğrular."""
        # Parametre eksikliği kontrolü
        err = handle_deep_research({})
        self.assertIn("Hata", err)

        # Fallback sentezi doğrulaması
        mock_results = [
            {"title": "Test Makale 1", "url": "https://example.com/1", "snippet": "Özet 1"},
            {"title": "Test Makale 2", "url": "https://example.com/2", "snippet": "Özet 2"},
        ]
        fallback_md = _build_fallback_report("Yapay Zeka Mimarileri", mock_results)
        self.assertIn("Yapay Zeka Mimarileri", fallback_md)
        self.assertIn("Bulunan Kaynaklar", fallback_md)
        self.assertIn("https://example.com/1", fallback_md)
        print("  [PASS] Deep Research Fallback Synthesizer")

    def test_05_agent_deep_research_tool(self):
        """Ajanın execute_tool üzerinden deep_research aracını başarıyla çağırdığını doğrular."""
        # Boş sorgu ile execute_tool
        res = execute_tool("deep_research", {})
        self.assertIn("Hata", res)
        print("  [PASS] Agent execute_tool (deep_research)")


def run_all_tests() -> bool:
    print("\n============================================================")
    print("  ULTRON UI, Logs, Swarm & Research — Phase 10 Test Suite")
    print("============================================================\n")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestPhase10Features)
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    passed = result.wasSuccessful()
    print("\n------------------------------------------------------------")
    print(f"  Sonuc: {result.testsRun - len(result.errors) - len(result.failures)} PASSED, {len(result.errors) + len(result.failures)} FAILED / {result.testsRun} toplam")
    print("------------------------------------------------------------\n")
    return passed


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
