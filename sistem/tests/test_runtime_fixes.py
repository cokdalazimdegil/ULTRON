"""
ULTRON Runtime Fixes & Stability Test Suite
═══════════════════════════════════════════
• Single-entry logging verification (no duplicate log emission)
• Proactive alert text/title integrity (prevention of 'undefined' alert)
• CPU smoothing & adaptive throttling verification
• OpenCV CascadeClassifier graceful presence check
• Workspace Agent 403 accessNotConfigured snooze mechanism
• OpenClaw Brain automatic fallback to local synthesizer
"""

import os
import sys
import time
import logging
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

TEST_DIR = Path(__file__).resolve().parent
BASE_DIR = TEST_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from jarvis_web.server import system_log_handler
from computer.proactive_watcher import ProactiveWatcherEngine, ProactiveAlert, AlertCategory, AlertSeverity
from computer.observer_daemon import _get_face_cascade
from core.proactive_agent import ProactiveWorkspaceAgent
from core.openclaw_brain import OpenClawBrain


class TestRuntimeFixes(unittest.TestCase):

    def test_01_no_duplicate_logging(self):
        """ultron.* loglarının SystemLogHandler buffer'ına çift düşmediğini ve dedup çalıştığını doğrular."""
        system_log_handler.buffer.clear()
        logger = logging.getLogger("ultron.core.test_service")
        
        # Tek bir log bas
        msg = f"Sistem doğrulama kaydı_{int(time.time() * 1000)}"
        logger.info(msg)
        
        matching = [entry for entry in system_log_handler.buffer if entry.get("message") == msg]
        self.assertEqual(len(matching), 1, f"Log mesajı tam olarak 1 kez kaydedilmeli, bulunan: {len(matching)}")

        # Arka arkaya aynı mesaj gönderildiğinde dedup çalışmalı
        logger.info(msg)
        matching_after_dup = [entry for entry in system_log_handler.buffer if entry.get("message") == msg]
        self.assertEqual(len(matching_after_dup), 1, "Aynı mesaj 150ms içinde tekrar geldiğinde filtrelenmeli.")

    def test_02_cpu_smoothing_and_anti_spike(self):
        """Tekil anlık CPU sıçramasının doğrudan alarm üretmediğini, hareketli ortalama gerektiğini doğrular."""
        watcher = ProactiveWatcherEngine(check_interval_sec=8.0)
        watcher.clear_all()
        
        # 1. Anlık spike (%98) ancak tek örnek
        with patch("psutil.cpu_percent", return_value=98.0):
            alerts = watcher.check_system_stress()
            # Henüz en az 2 örnek olmadığından panik alarmı üretilmemeli
            cpu_alerts = [a for a in alerts if a.category == AlertCategory.SYSTEM_STRESS and "CPU" in a.title]
            self.assertEqual(len(cpu_alerts), 0, "Tek bir anlık sıçramada alarm üretilmemeli (smoothing).")

        # 2. İkinci yüksek ölçüm geldiğinde ortalama yüksek kalırsa alarm üretilmeli
        with patch("psutil.cpu_percent", return_value=96.0):
            alerts2 = watcher.check_system_stress()
            cpu_alerts2 = [a for a in alerts2 if a.category == AlertCategory.SYSTEM_STRESS and "CPU" in a.title]
            self.assertEqual(len(cpu_alerts2), 1, "Sürekli yüksek CPU durumunda alarm üretilmeli.")
            self.assertIn("CPU kullanımı kritik seviyede", cpu_alerts2[0].message)

    def test_03_observer_cascade_safe_fallback(self):
        """OpenCV CascadeClassifier bulunmadığında sistemin çökmediğini ve güvenle None döndüğünü doğrular."""
        # hasattr testini simüle et
        with patch.object(sys.modules.get("cv2"), "CascadeClassifier", None, create=True):
            cascade = _get_face_cascade()
            # Hata fırlatılmamalı, None veya mock dönmeli
            self.assertTrue(cascade is None or hasattr(cascade, "detectMultiScale"))

    def test_04_proactive_workspace_403_snooze(self):
        """Google Workspace API 403 accessNotConfigured hatası aldığında döngünün askıya alındığını doğrular."""
        agent = ProactiveWorkspaceAgent(check_interval_sec=10)
        self.assertFalse(agent._disabled)

        # 403 hatası simüle et
        mock_events = [{"error": "<HttpError 403: 'Google Calendar API accessNotConfigured'>"}]
        with patch("core.proactive_agent.get_upcoming_events", return_value=mock_events):
            agent._check_calendar()
            self.assertTrue(agent._disabled, "accessNotConfigured algılandığında agent pasif moda geçmeli.")

    def test_05_openclaw_brain_fallback(self):
        """OpenClaw yanıt vermediğinde ask_with_fallback'in yerel analiz motorunu çağırdığını doğrular."""
        brain = OpenClawBrain(port=18789)
        
        # ask() zaman aşımına uğramış gibi mock'la
        with patch.object(brain, "ask", return_value="⚠️ [OpenClaw Brain] Yanıt zaman aşımına uğradı."):
            with patch("orchestrator.gemini_reasoning.query_gemini_reasoning", return_value="Yerel derin analiz raporu: Sistem mimarisi ve güvenlik stratejisi."):
                result = brain.ask_with_fallback("Bana yapay zeka mimarisini analiz et")
                self.assertIsNotNone(result)
                self.assertIn("Yerel derin analiz raporu", result)


def run_all_tests() -> bool:
    print("\n============================================================")
    print("  ULTRON Runtime Fixes & Stability Test Suite")
    print("============================================================\n")
    suite = unittest.TestLoader().loadTestsFromTestCase(TestRuntimeFixes)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
