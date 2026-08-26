"""
ULTRON Orchestrator — Terminal Agent Module
───────────────────────────────────────────
• Güvenli terminal / shell komutu yürütme (PowerShell & Cmd)
• Çıktı (stdout/stderr), çalışma süresi ve dönüş kodu yakalama
• Risk ve güvenlik ön kontrolleri
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Any

from computer.safety_manager import SafetyManager
from orchestrator.agent_registry import agent_registry

logger = logging.getLogger("ultron.orchestrator.terminal_agent")


class TerminalAgent:
    """Terminal komutlarını güvenle çalıştıran uzman ajan."""

    @staticmethod
    def execute(command: str, cwd: str | None = None, timeout: int = 30) -> dict[str, Any]:
        """
        Komutu çalıştırır ve çıktıyı yapısal olarak döner.
        """
        # 1. Yetki ve İzin Kontrolü
        perm_ok, perm_msg = agent_registry.check_permission("terminal_agent", "run_shell")
        if not perm_ok:
            return {"success": False, "stdout": "", "stderr": perm_msg, "returncode": -1}

        # 2. Risk Kontrolü
        risk_eval = SafetyManager.evaluate_risk(command)
        if risk_eval["requires_confirmation"]:
            return {
                "success": False,
                "stdout": "",
                "stderr": risk_eval["warning"],
                "returncode": -2,
                "requires_confirmation": True
            }

        work_dir = cwd or os.getcwd()
        start_time = time.time()
        print(f"[Terminal Agent] 💻 Komut çalıştırılıyor: '{command}' (Dizin: {work_dir})", flush=True)

        try:
            res = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                cwd=work_dir,
                capture_output=True,
                text=True,
                timeout=timeout
            )
            duration_ms = int((time.time() - start_time) * 1000)
            success = (res.returncode == 0)

            return {
                "success": success,
                "stdout": res.stdout.strip(),
                "stderr": res.stderr.strip(),
                "returncode": res.returncode,
                "duration_ms": duration_ms
            }

        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Komut zaman aşımına uğradı ({timeout} saniye).",
                "returncode": -3,
                "duration_ms": int(timeout * 1000)
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": str(e),
                "returncode": -4,
                "duration_ms": 0
            }

    execute_command = execute

