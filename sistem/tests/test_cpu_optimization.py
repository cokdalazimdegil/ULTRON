"""
ULTRON CPU Optimization Verification Tests
"""
import unittest
from PIL import Image
from computer.screen_awareness import screen_awareness, ChangeSeverity
from computer.proactive_watcher import proactive_watcher
from computer.cyber_dog import cyber_dog, SAFE_PROCESSES
from computer.observer_daemon import observer_daemon


class TestCPUOptimizations(unittest.TestCase):
    def test_screen_awareness_cache_on_no_change(self):
        # Create a test image
        img = Image.new("RGB", (400, 300), color=(50, 50, 50))
        elems = screen_awareness.detect_ui_elements(img)
        self.assertIsInstance(elems, list)
        
        # Test cache reuse
        screen_awareness._last_ui_elements = elems
        # If severity is NO_CHANGE, detect_ui_elements shouldn't recalculate
        ctx = screen_awareness.observe_screen(force_full_analysis=False)
        self.assertIsNotNone(ctx)
        self.assertEqual(ctx.ui_elements, elems)

    def test_proactive_watcher_interval(self):
        self.assertGreaterEqual(proactive_watcher.check_interval_sec, 8.0)

    def test_cyber_dog_optimizations(self):
        self.assertGreaterEqual(cyber_dog.patrol_interval_sec, 90.0)
        self.assertIsInstance(SAFE_PROCESSES, set)
        self.assertIn("chrome.exe", SAFE_PROCESSES)
        self.assertIn("python.exe", SAFE_PROCESSES)

    def test_observer_daemon_cam_fail_count(self):
        self.assertTrue(hasattr(observer_daemon, "_cam_fail_count"))
        self.assertEqual(observer_daemon._cam_fail_count, 0)


def run_all_tests() -> bool:
    suite = unittest.defaultTestLoader.loadTestsFromTestCase(TestCPUOptimizations)
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    return result.wasSuccessful()


if __name__ == "__main__":
    unittest.main()
