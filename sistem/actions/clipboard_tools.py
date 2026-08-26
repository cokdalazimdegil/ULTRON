"""
ULTRON — Pano (Clipboard) Yönetim Aracı
──────────────────────────────────────
Sistem panosundaki metni okur veya panoya metin/kod kopyalar.
"""

from __future__ import annotations

import subprocess
from actions.platform_utils import IS_WIN, IS_MAC, run_quiet


def clipboard_control(action: str = "get", text: str = "") -> str:
    """
    action:
      - get: Panodaki metni okur
      - set: Belirtilen metni panoya kopyalar
    """
    action = str(action or "get").strip().lower()

    if action in ("get", "read", "oku"):
        if IS_WIN:
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                try:
                    data = win32clipboard.GetClipboardData(win32clipboard.CF_UNICODETEXT)
                    return f"📋 Panodaki Metin:\n{data}"
                finally:
                    win32clipboard.CloseClipboard()
            except Exception:
                # Fallback to powershell
                res = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard"], capture_output=True, text=True, encoding="utf-8")
                return f"📋 Panodaki Metin:\n{res.stdout.strip()}"
        elif IS_MAC:
            res = run_quiet(["pbpaste"])
            return f"📋 Panodaki Metin:\n{res.stdout.strip()}"

    if action in ("set", "copy", "kopyala", "yaz"):
        if not text:
            return "Kopyalanacak metin boş."
        if IS_WIN:
            try:
                import win32clipboard
                win32clipboard.OpenClipboard()
                win32clipboard.EmptyClipboard()
                win32clipboard.SetClipboardText(text, win32clipboard.CF_UNICODETEXT)
                win32clipboard.CloseClipboard()
                return f"✓ Metin panoya kopyalandı ({len(text)} karakter)."
            except Exception:
                # Fallback to Set-Clipboard
                ps_cmd = f"Set-Clipboard -Value @'\n{text}\n'@"
                subprocess.run(["powershell", "-NoProfile", "-Command", ps_cmd], capture_output=True)
                return "✓ Metin panoya kopyalandı."
        elif IS_MAC:
            p = subprocess.Popen(["pbcopy"], stdin=subprocess.PIPE)
            p.communicate(text.encode("utf-8"))
            return "✓ Metin panoya kopyalandı."

    return f"Geçersiz pano işlemi: {action}"
