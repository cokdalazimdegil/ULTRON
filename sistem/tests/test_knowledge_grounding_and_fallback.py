"""
ULTRON Test Paketi — Phase 14: Knowledge Grounding, Fallback & Self-Healing
═══════════════════════════════════════════════════════════════════════════
Bu test paketi şunları doğrular:
1. Sistem promptu ve persona kurallarının genel güncellik ve teyit prensiplerini
   içerdiğini, hardcoded tek ürün istisnaları barındırmadığını,
2. Araç (tool) tanımlarının (web_search, ask_openclaw_brain, deep_research)
   eksiksiz ve doğru yönlendirme açıklamalarına sahip olduğunu,
3. Araştırma motorunun fallback sağlayıcılarını, HTML temizliğini ve yapılandırılmış
   yedek rapor sentezini,
4. OpenClaw Brain'in isteğe bağlı açılıp kapatılabilmesini ve çevrimdışıyken
   otomatik canlı web + akıl yürütme fallback mekanizmasını,
5. Self-Healer ve Self-Healing Motorunun hata sınıflandırma, dosya çıkarımı
   ve güvenli teşhis yeteneklerini.
"""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

# Sistem kök dizinini ekle
TESTS_DIR = Path(__file__).resolve().parent
BASE_DIR = TESTS_DIR.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))


class TestKnowledgeGroundingAndFallback(unittest.TestCase):

    def test_01_system_prompt_grounding_directive(self):
        """Sistem promptunun genel teyit ve güncellik direktiflerini içerdiğini doğrula."""
        from prompt_loader import load_system_prompt
        prompt_text = load_system_prompt()

        # Genel güncellik kuralı var mı?
        self.assertIn("Canlı Bilgi ve Teyit Protokolü", prompt_text)
        self.assertIn("web_search", prompt_text)

        # Asla tek bir ürün adının (örn: iPhone Duo) hardcoded kural olarak gömülmediğini doğrula
        self.assertNotIn("iPhone Duo", prompt_text)
        self.assertNotIn("iphone duo", prompt_text.lower())

    def test_02_soul_grounding_protocol(self):
        """soul.md dosyasının genel teyit protokolünü ve temiz kuralları içerdiğini doğrula."""
        soul_path = BASE_DIR / "core" / "persona" / "soul.md"
        self.assertTrue(soul_path.exists(), "soul.md mevcut olmalıdır.")
        content = soul_path.read_text(encoding="utf-8")

        self.assertIn("Canlı Bilgi ve Teyit Protokolü", content)
        self.assertIn("Doğrulanmamış Ret Yasağı", content)
        self.assertIn("ask_openclaw_brain", content)
        self.assertNotIn("iPhone Duo", content)

    def test_03_tool_declarations_and_routing(self):
        """Araç tanımlarının (web_search, ask_openclaw_brain, deep_research) eksiksiz olduğunu doğrula."""
        from tool_defs import TOOL_DECLARATIONS

        declared_names = {t.get("name"): t for t in TOOL_DECLARATIONS}

        # 1. web_search
        self.assertIn("web_search", declared_names)
        ws = declared_names["web_search"]
        self.assertIn("query", ws.get("parameters", {}).get("required", []))
        self.assertIn("canlı", ws.get("description", "").lower())

        # 2. ask_openclaw_brain
        self.assertIn("ask_openclaw_brain", declared_names)
        aob = declared_names["ask_openclaw_brain"]
        self.assertIn("query", aob.get("parameters", {}).get("required", []))
        self.assertIn("otonom", aob.get("description", "").lower())
        self.assertNotIn("iPhone Duo", aob.get("description", ""))

        # 3. deep_research
        self.assertIn("deep_research", declared_names)
        dr = declared_names["deep_research"]
        self.assertIn("query", dr.get("parameters", {}).get("required", []))

    def test_04_research_engine_clean_and_fallback(self):
        """Araştırma motorunun HTML temizliği ve fallback rapor oluşturmasını doğrula."""
        from actions.research_engine import _clean_html, _build_fallback_report, simple_web_search

        # HTML temizliği testi
        raw_html = "<div><h1>Başlık</h1><script>alert(1)</script><p>Açıklama &amp; Detay</p></div>"
        cleaned = _clean_html(raw_html)
        self.assertNotIn("<script>", cleaned)
        self.assertNotIn("alert(1)", cleaned)
        self.assertIn("Başlık", cleaned)
        self.assertIn("Açıklama & Detay", cleaned)

        # Boş arama kontrolü
        empty_res = simple_web_search("   ")
        self.assertEqual(empty_res, "Arama sorgusu boş olamaz.")

        # Fallback rapor testi
        fake_results = [
            {"title": "Test Başlık 1", "url": "https://example.com/1", "snippet": "Özet 1"},
            {"title": "Test Başlık 2", "url": "https://example.com/2", "snippet": "Özet 2"},
        ]
        rep = _build_fallback_report("Test Sorgu", fake_results)
        self.assertIn("# Test Sorgu — Araştırma Raporu", rep)
        self.assertIn("Test Başlık 1", rep)
        self.assertIn("https://example.com/2", rep)

    def test_05_openclaw_brain_toggle_and_resilience(self):
        """OpenClaw Brain açma/kapatma durumunu ve fallback yapısını doğrula."""
        from core.openclaw_brain import openclaw_brain

        original_state = openclaw_brain.is_enabled()
        try:
            # 1. Devre dışı bırakma testi
            openclaw_brain.set_enabled(False)
            self.assertFalse(openclaw_brain.is_enabled())

            # Devre dışıyken ask() hemen boş dönmeli, subprocess çalıştırmamalı
            res = openclaw_brain.ask("test query")
            self.assertEqual(res, "")

            # 2. ask_with_fallback testi (OpenClaw kapalıyken fallback devreye girmeli)
            # Not: API çağrısı olmadan da en azından boş sorgu veya web fallback çalışmalı
            fallback_res = openclaw_brain.ask_with_fallback("")
            self.assertEqual(fallback_res, "")

            # Tekrar aktif etme
            openclaw_brain.set_enabled(True)
            self.assertTrue(openclaw_brain.is_enabled())

        finally:
            openclaw_brain.set_enabled(original_state)

    def test_06_self_healer_diagnostics_and_inference(self):
        """Self-Healer'ın dosya çıkarımını ve hata sınıflandırmasını doğrula."""
        from core.self_healer import self_healer
        from core.self_healing import self_healing_engine, ErrorCategory

        # 1. Dosya çıkarımı (inference)
        self.assertEqual(self_healer._infer_file("web_search"), "actions/research_engine.py")
        self.assertEqual(self_healer._infer_file("ask_openclaw_brain"), "core/openclaw_brain.py")
        self.assertEqual(self_healer._infer_file("shopping_action"), "computer/shopping_engine.py")
        self.assertEqual(self_healer._infer_file("shell_run"), "actions/shell.py")

        # 2. Hata kategorilendirme
        cat_timeout = self_healing_engine.classify_error(TimeoutError("Operation timed out after 30s"))
        self.assertEqual(cat_timeout, ErrorCategory.TIMEOUT)

        cat_dep = self_healing_engine.classify_error(ModuleNotFoundError("No module named 'missing_pkg'"))
        self.assertEqual(cat_dep, ErrorCategory.DEPENDENCY)

        cat_net = self_healing_engine.classify_error(ConnectionError("Connection refused by peer"))
        self.assertEqual(cat_net, ErrorCategory.NETWORK)

        # 3. Teşhis raporu üretimi
        diag = self_healing_engine.diagnose("Connection refused by peer", component="network_module")
        self.assertEqual(diag.category, ErrorCategory.NETWORK)
        self.assertTrue(diag.can_auto_recover)


def run_all_tests() -> bool:
    suite = unittest.TestLoader().loadTestsFromTestCase(TestKnowledgeGroundingAndFallback)
    runner = unittest.TextTestRunner(verbosity=2)
    res = runner.run(suite)
    return res.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
