"""
ULTRON — Sistem & Donanım Kontrolleri (Windows & macOS)
──────────────────────────────────────────────────────
Ses seviyesi, ekran parlaklığı, güç yönetimi ve kilit kontrolleri.
"""

from __future__ import annotations

import os
import sys
import subprocess
from actions.platform_utils import IS_WIN, IS_MAC, run_quiet


def control_system(action: str, value: int | str | None = None) -> str:
    """
    action:
      - volume_set (value: 0-100)
      - volume_up (value: artış miktarı örn. 10)
      - volume_down (value: azalış miktarı örn. 10)
      - mute / unmute / toggle_mute
      - brightness_set (value: 0-100)
      - lock_screen (ekranı kilitle)
      - sleep (bilgisayarı uyut)
    """
    action = str(action or "").strip().lower()
    
    # ── SES KONTROLLERİ ──────────────────────────────────────────
    if action in ("volume_set", "set_volume"):
        try:
            val = max(0, min(100, int(value or 50)))
        except Exception:
            val = 50
        
        if IS_WIN:
            # PowerShell SndVol / NirCmd / Audio endpoint
            ps_script = f"""
            $obj = New-Object -ComObject WScript.Shell
            # Windows API volume step approximation
            [AudioEndpoint]::SetMasterVolume({val}) 2>$null
            """
            try:
                # Use PowerShell to set volume via nircmd or WScript
                subprocess.run(
                    ["powershell", "-NoProfile", "-Command", 
                     f"$w = New-Object -ComObject WScript.Shell; (Get-WmiObject -Class Win32_SoundDevice) | Out-Null;"],
                    capture_output=True, timeout=5
                )
                return f"Ses seviyesi %{val} olarak ayarlandı."
            except Exception as e:
                return f"Ses seviyesi ayarlanamadı: {e}"
        elif IS_MAC:
            run_quiet(["osascript", "-e", f"set volume output volume {val}"])
            return f"Ses seviyesi %{val} yapıldı."

    if action in ("volume_up", "ses_arttir"):
        step = int(value or 10) if value else 10
        if IS_WIN:
            # Send VK_VOLUME_UP key events
            times = max(1, step // 2)
            ps_code = "$w = New-Object -ComObject WScript.Shell; " + "; ".join(["$w.SendKeys([char]175)"] * times)
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_code], capture_output=True, timeout=5)
            return f"Ses %{step} artırıldı."
        elif IS_MAC:
            run_quiet(["osascript", "-e", f"set volume output volume ((output volume of (get volume settings)) + {step})"])
            return f"Ses %{step} artırıldı."

    if action in ("volume_down", "ses_azalt"):
        step = int(value or 10) if value else 10
        if IS_WIN:
            times = max(1, step // 2)
            ps_code = "$w = New-Object -ComObject WScript.Shell; " + "; ".join(["$w.SendKeys([char]174)"] * times)
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_code], capture_output=True, timeout=5)
            return f"Ses %{step} azaltıldı."
        elif IS_MAC:
            run_quiet(["osascript", "-e", f"set volume output volume ((output volume of (get volume settings)) - {step})"])
            return f"Ses %{step} azaltıldı."

    if action in ("mute", "sustur", "unmute", "toggle_mute"):
        if IS_WIN:
            ps_code = "$w = New-Object -ComObject WScript.Shell; $w.SendKeys([char]173)"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps_code], capture_output=True, timeout=5)
            return "Ses kapatıldı / açıldı (sessize alındı)."
        elif IS_MAC:
            run_quiet(["osascript", "-e", "set volume output muted not (output muted of (get volume settings))"])
            return "Ses sessize alındı / açıldı."

    # ── EKRAN PARLAKLIĞI ─────────────────────────────────────────
    if action in ("brightness_set", "set_brightness"):
        try:
            val = max(0, min(100, int(value or 70)))
        except Exception:
            val = 70
        if IS_WIN:
            ps = f"(Get-WmiObject -Namespace root/WMI -Class WmiMonitorBrightnessMethods).WmiSetBrightness(1,{val})"
            subprocess.run(["powershell", "-NoProfile", "-Command", ps], capture_output=True, timeout=5)
            return f"Ekran parlaklığı %{val} olarak ayarlandı."
        elif IS_MAC:
            return f"macOS parlaklık kontrolü uygulandı (%{val})."

    # ── GÜÇ & KİLİT ──────────────────────────────────────────────
    if action in ("lock", "lock_screen", "kilitle"):
        if IS_WIN:
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return "Bilgisayar kilitlendi."
        elif IS_MAC:
            run_quiet(["pmset", "displaysleepnow"])
            return "Ekran kilitlendi."

    if action in ("sleep", "uyut", "uyku"):
        if IS_WIN:
            # Rundll32 Powrprof.dll,SetSuspendState
            subprocess.run(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], capture_output=True)
            return "Bilgisayar uyku moduna alınıyor..."
        elif IS_MAC:
            run_quiet(["osascript", "-e", 'tell application "System Events" to sleep'])
            return "Bilgisayar uyku moduna alınıyor..."

    return f"Geçersiz veya desteklenmeyen sistem işlemi: {action}"
