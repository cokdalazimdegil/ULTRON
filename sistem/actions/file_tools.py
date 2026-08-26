"""
ULTRON — Dosya & Dizin Yönetim Aracı
────────────────────────────────────
Dosya okuma, yazma, dizin listeleme ve dosya arama işlemleri.
"""

from __future__ import annotations

import os
from pathlib import Path


def file_operations(
    action: str,
    path: str = "",
    content: str = "",
    search_query: str = "",
) -> str:
    """
    action:
      - read: Belirtilen dosyanın içeriğini okur
      - write: Belirtilen dosyaya yazar (oluşturur/üzerine yazar)
      - append: Dosyanın sonuna metin ekler
      - list: Belirtilen dizindeki dosya ve klasörleri listeler
      - search: Belirtilen dizinde veya dosya adlarında arama yapar
    """
    action = str(action or "read").strip().lower()
    target_path = Path(path).expanduser().resolve() if path else Path.cwd()

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

    return f"Bilinmeyen dosya işlemi: {action}. (Desteklenenler: read, write, append, list, search)"
