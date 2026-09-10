"""
ULTRON — Dosya & Dizin Yönetim Aracı
────────────────────────────────────
Dosya okuma, yazma, dizin listeleme ve dosya arama işlemleri.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from core.security_manager import security_engine, RiskLevel, is_untrusted_content


def file_operations(
    action: str,
    path: str = "",
    content: str = "",
    search_query: str = "",
    is_untrusted: bool = False,
) -> str:
    """
    action:
      - read: Belirtilen dosyanın içeriğini okur
      - write: Belirtilen dosyaya yazar (oluşturur/üzerine yazar)
      - append: Dosyanın sonuna metin ekler
      - delete: Belirtilen dosyayı veya dizini siler (güvenlik denetimli)
      - list: Belirtilen dizindeki dosya ve klasörleri listeler
      - search: Belirtilen dizinde veya dosya adlarında arama yapar
    """
    action = str(action or "read").strip().lower()
    target_path = Path(path).expanduser().resolve() if path else Path.cwd()

    # Merkezi Güvenlik Yetkilendirmesi
    decision = security_engine.authorize(
        "file_tools",
        target=str(target_path),
        params={"action": action, "content_len": len(content or "")},
        is_untrusted=is_untrusted or is_untrusted_content(content or path)
    )

    if not decision.allowed or decision.risk_level == RiskLevel.CRITICAL:
        return (
            f"🚫 Güvenlik Uyarısı (İşlem Engellendi):\n"
            f"Dosya/Dizin: {target_path}\n"
            f"İşlem: {action}\n"
            f"Risk Seviyesi: {decision.risk_level.value}\n"
            f"Gerekçe: {decision.reason}"
        )

    if action in ("read", "oku"):
        if not target_path.exists():
            return f"Hata: '{target_path}' dosyası bulunamadı."
        if not target_path.is_file():
            return f"Hata: '{target_path}' bir dosya değil."
        try:
            text = target_path.read_text(encoding="utf-8", errors="replace")
            if len(text) > 3000:
                text = text[:3000] + f"\n... [Dosya içeriği uzun olduğu için ilk 3000 karakter gösterildi. Toplam boyut: {len(text)} karakter]"
            return f"📄 Dosya İçeriği ({target_path.name}):\n\n{text}"
        except Exception as e:
            return f"Dosya okunurken hata oluştu: {e}"

    if action in ("write", "yaz", "create"):
        if not path:
            return "Hata: Yazılacak dosya yolu belirtilmedi."
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            target_path.write_text(content, encoding="utf-8")
            return f"✓ Dosya başarıyla oluşturuldu/yazıldı: {target_path} ({len(content)} karakter)"
        except Exception as e:
            return f"Dosya yazılırken hata oluştu: {e}"

    if action in ("append", "ekle"):
        if not path:
            return "Hata: Dosya yolu belirtilmedi."
        try:
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with open(target_path, "a", encoding="utf-8") as f:
                f.write(content)
            return f"✓ Dosyaya başarıyla eklendi: {target_path}"
        except Exception as e:
            return f"Dosyaya ekleme yapılırken hata: {e}"

    if action in ("list", "listele", "dir", "ls"):
        if not target_path.exists():
            return f"Hata: '{target_path}' dizini bulunamadı."
        if not target_path.is_dir():
            target_path = target_path.parent
        try:
            items = []
            for entry in os.scandir(target_path):
                if entry.name.startswith(".") and not search_query:
                    continue
                type_str = "📁 Dizin" if entry.is_dir() else f"📄 Dosya ({entry.stat().st_size} bayt)"
                items.append(f"- {entry.name} [{type_str}]")
            
            output = f"📂 Dizin: {target_path}\n" + "\n".join(items[:50])
            if len(items) > 50:
                output += f"\n... ve {len(items) - 50} öğe daha."
            return output
        except Exception as e:
            return f"Dizin listelenirken hata: {e}"

    if action in ("search", "ara", "bul"):
        query = (search_query or path or "").lower()
        search_root = Path.cwd() if not path or not Path(path).exists() else Path(path)
        if search_root.is_file():
            search_root = search_root.parent

        matches = []
        try:
            for root, dirs, files in os.walk(search_root):
                dirs[:] = [d for d in dirs if not d.startswith(".")]
                for f in files:
                    if query in f.lower():
                        matches.append(str(Path(root) / f))
                    if len(matches) >= 25:
                        break
                if len(matches) >= 25:
                    break
            if not matches:
                return f"'{query}' ifadesiyle eşleşen dosya bulunamadı."
            return f"🔍 Bulunan Dosyalar ({len(matches)}):\n" + "\n".join(matches)
        except Exception as e:
            return f"Arama sırasında hata: {e}"

    if action in ("delete", "sil", "remove"):
        if not path:
            return "Hata: Silinecek dosya veya dizin yolu belirtilmedi."
        if not target_path.exists():
            return f"Hata: Silinecek '{target_path}' öğesi bulunamadı."
        try:
            if target_path.is_file():
                target_path.unlink()
                return f"✓ Dosya başarıyla silindi: {target_path}"
            elif target_path.is_dir():
                shutil.rmtree(target_path)
                return f"✓ Dizin ve içeriği başarıyla silindi: {target_path}"
        except Exception as e:
            return f"Silme işlemi sırasında hata: {e}"

    return f"Bilinmeyen dosya işlemi: {action}. (Desteklenenler: read, write, append, delete, list, search)"
