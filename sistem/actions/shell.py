"""
ULTRON — Terminal & Shell Komutu Çalıştırma Aracı
─────────────────────────────────────────────────
macOS   → bash / zsh
Windows → PowerShell & Cmd
"""

import os
import subprocess
from pathlib import Path
from actions.platform_utils import IS_WIN, quiet_popen_kwargs


from core.security_manager import security_engine, RiskLevel, is_untrusted_content


def shell_run(command: str, cwd: str = "", timeout: int = 45, is_untrusted: bool = False) -> str:
    """
    Sistem terminalinde PowerShell veya bash komutları çalıştırır.
    Tüm komutlar çalıştırmadan önce merkezi security_engine üzerinden yetkilendirilir.
    RiskLevel.CRITICAL ise çalıştırmayı durdurur ve onay ister; HIGH ise audit log'a yazar.
    """
    if not command or not command.strip():
        return "Hata: Komut belirtilmedi."

    # Merkezi Güvenlik Katmanı Yetkilendirmesi
    decision = security_engine.authorize(
        "shell_run",
        target=command,
        params={"cwd": cwd},
        is_untrusted=is_untrusted or is_untrusted_content(command)
    )

    if not decision.allowed or decision.risk_level == RiskLevel.CRITICAL:
        return (
            f"🚫 Güvenlik Uyarısı (İşlem Engellendi):\n"
            f"Komut: {command}\n"
            f"Risk Seviyesi: {decision.risk_level.value}\n"
            f"Gerekçe: {decision.reason}\n"
            f"{decision.warning_message}"
        )

    work_dir = str(Path(cwd).expanduser().resolve()) if cwd and Path(cwd).exists() else None

    try:
        if IS_WIN:
            result = _run_windows(command, work_dir, timeout)
        else:
            result = subprocess.run(
                command, shell=True, capture_output=True,
                text=True, timeout=timeout, cwd=work_dir,
                encoding="utf-8", errors="replace"
            )

        stdout = (result.stdout or "").strip()
        stderr = (result.stderr or "").strip()

        output_parts = []
        if stdout:
            output_parts.append(stdout)
        if stderr and result.returncode != 0:
            output_parts.append(f"[Hata Çıktısı]:\n{stderr}")

        output = "\n\n".join(output_parts).strip()
        if not output:
            return f"✓ Komut başarıyla tamamlandı (Kod: {result.returncode}, çıktı yok)."

        if len(output) > 2500:
            output = output[:2500] + f"\n\n... [Çıktı kısaltıldı. Toplam: {len(output)} karakter]"

        return f"💻 Terminal Çıktısı (Kod: {result.returncode}):\n{output}"

    except subprocess.TimeoutExpired:
        return f"Hata: Komut {timeout} saniye zaman aşımına uğradı."
    except Exception as e:
        return f"Komut çalıştırılırken hata oluştu: {e}"


def _run_windows(command: str, cwd: str | None, timeout: int) -> subprocess.CompletedProcess:
    """Komutu PowerShell'de UTF-8 çıktıyla çalıştırır."""
    wrapped = "[Console]::OutputEncoding = [Text.Encoding]::UTF8; " + command
    return subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy", "Bypass",
            "-Command", wrapped,
        ],
        capture_output=True,
        text=True,
        timeout=timeout,
        cwd=cwd,
        encoding="utf-8",
        errors="replace",
        **quiet_popen_kwargs(),
    )
