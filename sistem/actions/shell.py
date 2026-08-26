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


# Yalnızca geri dönüşü olmayan yıkıcı formatlama/silme komutlarını engelle
BLOCKED_COMMON = [
    "mkfs",
    "dd if=",
    ":(){:|:&};:",
]

BLOCKED_MAC = [
    "rm -rf /",
    "diskutil erase",
    "diskutil apfs deletecontainer",
]

BLOCKED_WIN = [
    "format c:",
    "clear-disk",
    "remove-partition",
]


def _blocked_patterns() -> list[str]:
    return BLOCKED_COMMON + (BLOCKED_WIN if IS_WIN else BLOCKED_MAC)


def shell_run(command: str, cwd: str = "", timeout: int = 45) -> str:
    """
    Sistem terminalinde PowerShell veya bash komutları çalıştırır.
    Dosya işlemleri, git, ağ analizleri, python betikleri, sistem durumu vb. için kullanılır.
    """
    if not command or not command.strip():
        return "Hata: Komut belirtilmedi."

    cmd_lower = command.lower()
    for blocked in _blocked_patterns():
        if blocked in cmd_lower:
            return f"Güvenlik Uyarısı: Bu komut engellendi → {blocked.strip()}"

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
