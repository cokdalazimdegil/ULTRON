"""
ULTRON Computer Awareness — Application Controller Module
─────────────────────────────────────────────────────────
• Windows uygulamalarını başlatma, kapatma ve süreç doğrulama (Process Verification)
• Doğal dil uygulama eşleştirme (Chrome, Not Defteri, VS Code, Hesap Makinesi vb.)
• psutil ile gerçek çalışma durumunu doğrulama (Action -> Verify)
"""

from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Any

import psutil

logger = logging.getLogger("ultron.computer.app_controller")

APP_ALIASES: dict[str, list[str]] = {
    "notepad": ["notepad.exe", "notepad"],
    "not defteri": ["notepad.exe", "notepad"],
    "chrome": ["chrome.exe", "google-chrome", "chrome"],
    "google": ["chrome.exe", "msedge.exe"],
    "edge": ["msedge.exe", "edge"],
    "browser": ["chrome.exe", "msedge.exe"],
    "tarayıcı": ["chrome.exe", "msedge.exe"],
    "vscode": ["code.cmd", "code.exe", "code"],
    "code": ["code.cmd", "code.exe", "code"],
    "calculator": ["calc.exe", "calc"],
    "hesap makinesi": ["calc.exe", "calc"],
    "spotify": ["spotify.exe", "spotify"],
    "terminal": ["wt.exe", "powershell.exe", "cmd.exe"],
    "powershell": ["powershell.exe"],
    "cmd": ["cmd.exe"],
    "explorer": ["explorer.exe"],
    "dosya gezgini": ["explorer.exe"],
    "word": ["winword.exe"],
    "excel": ["excel.exe"],
    "paint": ["mspaint.exe"]
}


def is_app_running(app_query: str) -> bool:
    """Verilen uygulama veya sürecin çalışıp çalışmadığını kontrol eder."""
    q = app_query.lower().strip()
    target_names = APP_ALIASES.get(q, [q, f"{q}.exe"])

    for proc in psutil.process_iter(['name', 'pid']):
        try:
            pname = proc.info['name'].lower()
            for t in target_names:
                if t in pname or pname in t:
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return False


def get_running_process_names() -> list[str]:
    """Çalışan tüm benzersiz süreç adlarını listeler."""
    names = set()
    for proc in psutil.process_iter(['name']):
        try:
            n = proc.info['name']
            if n:
                names.add(n)
        except Exception:
            continue
    return sorted(list(names))


def open_application(app_name_or_path: str, wait_verify_sec: float = 2.0) -> tuple[bool, str]:
    """
    Uygulamayı başlatır ve sürecin gerçekten çalıştığını doğrular.
    Dönen: (success, message)
    """
    clean_name = app_name_or_path.strip().lower()
    targets = APP_ALIASES.get(clean_name, [clean_name, f"{clean_name}.exe"])

    # 1. Start komutu ile dene
    cmd_to_run = targets[0]
    try:
        if os.path.exists(app_name_or_path):
            subprocess.Popen([app_name_or_path], shell=False)
        else:
            # Windows 'start' shell komutu
            subprocess.Popen(f'start "" "{cmd_to_run}"', shell=True)

        # Doğrulama (Verify)
        time.sleep(wait_verify_sec)
        if is_app_running(clean_name):
            return True, f"✓ '{app_name_or_path}' uygulaması başarıyla başlatıldı ve doğrulandı."
        else:
            # İkinci deneme (powershell start-process)
            subprocess.Popen(["powershell", "-NoProfile", "-Command", f"Start-Process '{cmd_to_run}' -ErrorAction SilentlyContinue"])
            time.sleep(1.0)
            if is_app_running(clean_name):
                return True, f"✓ '{app_name_or_path}' uygulaması başlatıldı ve doğrulandı."
            return False, f"⚠️ '{app_name_or_path}' komutu gönderildi ancak süreç listesinde tespit edilemedi."

    except Exception as e:
        logger.error(f"Uygulama baslatma hatasi: {e}")
        return False, f"Uygulama başlatılamadı: {e}"


def close_application(app_name: str, force: bool = False) -> tuple[bool, str]:
    """Uygulamayı kapatır ve kapandığını doğrular."""
    clean_name = app_name.strip().lower()
    targets = APP_ALIASES.get(clean_name, [clean_name, f"{clean_name}.exe"])

    closed_any = False
    for proc in psutil.process_iter(['name', 'pid']):
        try:
            pname = proc.info['name'].lower()
            for t in targets:
                if t in pname or pname.replace(".exe", "") == t.replace(".exe", ""):
                    if force:
                        proc.kill()
                    else:
                        proc.terminate()
                    closed_any = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue

    time.sleep(0.5)
    still_running = is_app_running(clean_name)
    if still_running and force:
        # Taskkill fallback
        subprocess.run(["taskkill", "/F", "/IM", targets[0]], capture_output=True)
        time.sleep(0.5)
        still_running = is_app_running(clean_name)

    if not still_running:
        return True, f"✓ '{app_name}' uygulaması kapatıldı ve doğrulandı."
    elif closed_any:
        return True, f"✓ '{app_name}' için kapatma sinyali gönderildi."
    else:
        return False, f"'{app_name}' adında çalışan aktif bir süreç bulunamadı."
