"""
ULTRON Orchestrator — Testing Agent Module
──────────────────────────────────────────
• Bağımsız test yürütücüsü ve kalite güvence uzmanı
• Birim testleri, regresyon denetimleri ve çalışma zamanı doğrulaması
• Hata yakalama, log inceleme ve yapısal test raporu üretimi
"""

from __future__ import annotations

import logging
import os
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from orchestrator.agent_registry import agent_registry

logger = logging.getLogger("ultron.orchestrator.testing_agent")


class TestingAgent:
    """Yazılan kodu bağımsız olarak test eden uzman ajan."""

    @staticmethod
    def run_test_script(test_script_path: str, cwd: str | None = None) -> dict[str, Any]:
        """
        Belirtilen test dosyasını çalıştırır ve sonuçları ayrıştırır.
        """
        perm_ok, perm_msg = agent_registry.check_permission("testing_agent", "run_tests")
        if not perm_ok:
            return {"all_passed": False, "passed_count": 0, "failed_count": 1, "error": perm_msg, "summary": perm_msg}

        p = Path(test_script_path)
        if not p.exists():
            return {"all_passed": False, "passed_count": 0, "failed_count": 1, "error": f"Test dosyası bulunamadı: {test_script_path}", "summary": f"Test dosyası bulunamadı: {test_script_path}"}

        work_dir = cwd or str(p.parent)
        print(f"[Testing Agent] 🧪 Test paketi yürütülüyor: {p.name}", flush=True)

        start_time = time.time()
        try:
            res = subprocess.run(
                [sys.executable, str(p.resolve())],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=25
            )
            duration_ms = int((time.time() - start_time) * 1000)
            output = (res.stdout + "\n" + res.stderr).strip()

            # Test ve assertion sayılarını ayıkla
            import re
            ran_match = re.search(r"Ran (\d+) tests? in ([\d\.]+)s", output)
            total_ran = int(ran_match.group(1)) if ran_match else 1
            has_failures = ("FAIL" in output.upper() or "ERROR" in output.upper() or "TRACEBACK" in output.upper())
            all_passed = (res.returncode == 0) and not has_failures

            passed_count = total_ran if all_passed else max(0, total_ran - 1)
            failed_count = 0 if all_passed else max(1, total_ran - passed_count)

            summary_msg = f"✓ {passed_count}/{total_ran} test başarıyla geçti ({duration_ms} ms)." if all_passed else f"❌ {failed_count}/{total_ran} test başarısız oldu ({duration_ms} ms)."

            return {
                "all_passed": all_passed,
                "exit_code": res.returncode,
                "passed_count": passed_count,
                "failed_count": failed_count,
                "total_count": total_ran,
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip(),
                "duration_ms": duration_ms,
                "summary": summary_msg
            }

        except subprocess.TimeoutExpired:
            return {
                "all_passed": False,
                "exit_code": -1,
                "passed_count": 0,
                "failed_count": 1,
                "total_count": 1,
                "error": "Test zaman aşımına uğradı (25s)",
                "duration_ms": 25000,
                "summary": "Zaman aşımı hatası (25s)."
            }
        except Exception as e:
            return {
                "all_passed": False,
                "exit_code": -2,
                "passed_count": 0,
                "failed_count": 1,
                "total_count": 1,
                "error": str(e),
                "duration_ms": 0,
                "summary": f"Test yürütme hatası: {e}"
            }
