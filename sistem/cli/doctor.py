"""
ULTRON System Doctor — Kapsamlı Sistem Sağlık ve Teşhis Aracı (Phase 9)
═════════════════════════════════════════════════════════════════════
Tüm bağımlılıkları, konfigürasyonları, donanım/port durumlarını ve çekirdek
modüllerin sağlığını denetler; tespit edilen sorunlar için net çözüm önerileri sunar.

Çalıştırma:
    cd sistem
    python -X utf8 cli/doctor.py
"""

from __future__ import annotations

import os
import sys
import socket
import importlib
from pathlib import Path
from typing import Dict, List, Tuple

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


class DiagnosticCheck:
    def __init__(self, name: str, category: str):
        self.name = name
        self.category = category
        self.passed = False
        self.warning = False
        self.message = ""
        self.fix = ""


def check_python_environment() -> List[DiagnosticCheck]:
    checks = []

    # Python Versiyonu
    c1 = DiagnosticCheck("Python Sürümü", "Ortam")
    v = sys.version_info
    if v.major == 3 and v.minor >= 10:
        c1.passed = True
        c1.message = f"Python {v.major}.{v.minor}.{v.micro} (Uyumlu)"
    else:
        c1.passed = False
        c1.message = f"Python {v.major}.{v.minor}.{v.micro} (Python 3.10+ gereklidir)"
        c1.fix = "Python 3.10 veya daha güncel bir sürüm yükleyin."
    checks.append(c1)

    # İşletim Sistemi
    c2 = DiagnosticCheck("İşletim Sistemi", "Ortam")
    c2.passed = True
    c2.message = f"{sys.platform} ({os.name})"
    checks.append(c2)

    return checks


def check_dependencies() -> List[DiagnosticCheck]:
    required_packages = [
        ("fastapi", "Web sunucusu ve REST API", "pip install fastapi"),
        ("uvicorn", "ASGI sunucusu", "pip install uvicorn"),
        ("google.genai", "Gemini 2.5 Live ve Reasoning SDK", "pip install google-genai"),
        ("chromadb", "Vektör veritabanı ve semantik arama", "pip install chromadb"),
        ("cv2", "Kamera ve yüz algılama (OpenCV)", "pip install opencv-python"),
        ("requests", "Dış servis ve webhook istemcisi", "pip install requests"),
        ("numpy", "Sayısal hesaplama altyapısı", "pip install \"numpy<2\""),
    ]

    checks = []
    for pkg, desc, fix in required_packages:
        c = DiagnosticCheck(f"Paket: {pkg}", "Bağımlılıklar")
        try:
            mod = importlib.import_module(pkg)
            version = getattr(mod, "__version__", "yüklü")
            c.passed = True
            c.message = f"v{version} ({desc})"
        except Exception as e:
            c.passed = False
            c.message = f"Eksik veya yüklenemedi: {e}"
            c.fix = fix
        checks.append(c)

    return checks


def check_api_keys() -> List[DiagnosticCheck]:
    checks = []
    c = DiagnosticCheck("Gemini API Anahtarı", "Kimlik & Yapılandırma")

    from app_config import get_app_config_value
    key = str(get_app_config_value("gemini_api_key", "") or os.environ.get("GEMINI_API_KEY", "")).strip()

    if key:
        masked = key[:6] + "..." + key[-4:] if len(key) > 10 else "***"
        c.passed = True
        c.message = f"Tanımlı ({masked})"
    else:
        c.warning = True
        c.message = "Gemini API anahtarı boş — Canlı ses ve muhakeme çalışmayabilir."
        c.fix = "sistem/config/api_keys.json dosyasına 'gemini_api_key' ekleyin veya GEMINI_API_KEY çevre değişkenini tanımlayın."
    checks.append(c)

    return checks


def check_ports() -> List[DiagnosticCheck]:
    checks = []
    ports = [(8765, "ULTRON Web Sunucusu"), (8766, "HTTPS / Telefon Tüneli")]

    for port, name in ports:
        c = DiagnosticCheck(f"Port {port} ({name})", "Ağ")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(0.5)
        try:
            result = sock.connect_ex(("127.0.0.1", port))
            if result == 0:
                c.passed = True
                c.message = "Port aktif / servis çalışıyor."
            else:
                c.passed = True
                c.message = "Port boş, dinlemeye hazır."
        except Exception as e:
            c.passed = True
            c.message = f"Kontrol edildi: {e}"
        finally:
            sock.close()
        checks.append(c)

    return checks


def check_core_modules() -> List[DiagnosticCheck]:
    core_mods = [
        ("core.events", "Event Veri Yapıları"),
        ("core.event_bus", "Asenkron Event Bus"),
        ("core.notification_engine", "Çok Kanallı Bildirim Motoru"),
        ("core.presence_engine", "Varlık Durum Makinesi"),
        ("core.geofence_engine", "Coğrafi Sınır Motoru"),
        ("core.ha_bridge", "Home Assistant Köprüsü"),
        ("core.email_scorer", "E-Posta Önem Skorlayıcı"),
        ("core.unified_memory", "Konsolide Bellek Motoru"),
        ("core.local_rag_engine", "Yerel RAG Arama Motoru"),
    ]

    checks = []
    for mod_path, desc in core_mods:
        c = DiagnosticCheck(f"Çekirdek: {mod_path}", "Mimari Bileşenler")
        try:
            importlib.import_module(mod_path)
            c.passed = True
            c.message = f"Başarıyla yüklendi ({desc})"
        except Exception as e:
            c.passed = False
            c.message = f"İçe aktarma hatası: {e}"
            c.fix = f"Modül dosyasını ve bağımlılıklarını kontrol edin: sistem/{mod_path.replace('.', '/')}.py"
        checks.append(c)

    return checks


def run_diagnostics() -> Tuple[int, int, int]:
    """Tüm teşhis adımlarını çalıştırır ve konsola renkli rapor döker."""
    print("\n" + "═" * 65)
    print("  🏥 ULTRON MİMARİ SAĞLIK VE TEŞHİS RAPORU (DOCTOR)")
    print("═" * 65 + "\n")

    all_checks = []
    all_checks.extend(check_python_environment())
    all_checks.extend(check_dependencies())
    all_checks.extend(check_api_keys())
    all_checks.extend(check_ports())
    all_checks.extend(check_core_modules())

    current_cat = ""
    passed_count = 0
    warn_count = 0
    fail_count = 0

    for c in all_checks:
        if c.category != current_cat:
            current_cat = c.category
            print(f"\n┌─ [ {current_cat} ] " + "─" * (50 - len(current_cat)))

        if c.passed and not c.warning:
            passed_count += 1
            icon = "  [✓] PASS"
            status_text = f"{icon}  {c.name}: {c.message}"
        elif c.warning:
            warn_count += 1
            icon = "  [!] WARN"
            status_text = f"{icon}  {c.name}: {c.message}"
        else:
            fail_count += 1
            icon = "  [✗] FAIL"
            status_text = f"{icon}  {c.name}: {c.message}"

        print(status_text)
        if c.fix:
            print(f"      └─ Çözüm: {c.fix}")

    print("\n" + "═" * 65)
    print(f"  ÖZET: {passed_count} Başarılı | {warn_count} Uyarı | {fail_count} Hata")
    if fail_count == 0 and warn_count == 0:
        print("  🎉 ULTRON sistemi kusursuz durumda, tüm bileşenler hazır!")
    elif fail_count == 0:
        print("  👍 ULTRON çalışabilir durumda, küçük uyarılar var.")
    else:
        print("  ⚠️ ULTRON sisteminde kritik sorunlar tespit edildi. Lütfen çözüm önerilerini uygulayın.")
    print("═" * 65 + "\n")

    return passed_count, warn_count, fail_count


if __name__ == "__main__":
    passed, warns, fails = run_diagnostics()
    sys.exit(1 if fails > 0 else 0)
