"""
ULTRON Orchestrator — Git Safety, Snapshot & Rollback Engine
────────────────────────────────────────────────────────────
• Git durumu (git status) ve farkların (git diff) otomatik incelenmesi
• Kod değişiklikleri öncesi anlık görüntü (Snapshot) alma
• Hata/regresyon durumunda güvenli geri alma (Rollback) mekanizması
"""

from __future__ import annotations

import json
import logging
import os
import shutil
import subprocess
import time
from pathlib import Path
from typing import Any

from app_paths import data_path

logger = logging.getLogger("ultron.orchestrator.git_safety")

SNAPSHOTS_DIR = data_path("snapshots")


def get_git_status(cwd: str | None = None) -> dict[str, Any]:
    """Git durumunu (değişen, eklenen ve silinen dosyalar) döner."""
    work_dir = cwd or os.getcwd()
    try:
        res = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=work_dir,
            capture_output=True,
            text=True,
            timeout=5
        )
        if res.returncode != 0:
            return {"is_git": False, "files": [], "error": res.stderr}

        lines = [line.strip() for line in res.stdout.splitlines() if line.strip()]
        modified = []
        untracked = []
        for l in lines:
            if l.startswith("??"):
                untracked.append(l[3:].strip())
            else:
                modified.append(l[2:].strip())

        return {
            "is_git": True,
            "modified": modified,
            "untracked": untracked,
            "total_changes": len(lines)
        }
    except Exception as e:
        return {"is_git": False, "files": [], "error": str(e)}


def get_git_diff(cwd: str | None = None, file_path: str = "") -> str:
    """Git diff çıktısını metin olarak döner."""
    work_dir = cwd or os.getcwd()
    try:
        cmd = ["git", "diff"]
        if file_path:
            cmd.append(file_path)
        res = subprocess.run(cmd, cwd=work_dir, capture_output=True, text=True, timeout=8)
        return res.stdout if res.returncode == 0 else f"Git diff hatası: {res.stderr}"
    except Exception as e:
        return f"Git diff okunamadı: {e}"


def create_snapshot(files: list[str] | None = None, label: str = "") -> str:
    """
    Belirtilen veya değişen dosyaların anlık yedeğini (Snapshot) alır.
    Dönen: snapshot_id
    """
    SNAPSHOTS_DIR.mkdir(parents=True, exist_ok=True)
    snap_id = f"SNAP-{int(time.time())}-{label or 'auto'}"
    snap_folder = SNAPSHOTS_DIR / snap_id
    snap_folder.mkdir(parents=True, exist_ok=True)

    backed_up_files = []
    # Dosyalar belirtilmediyse git status üzerinden veya kritik dosyaları al
    if not files:
        st = get_git_status()
        files_to_backup = st.get("modified", [])
    else:
        files_to_backup = files

    for fpath in files_to_backup:
        p = Path(fpath)
        if p.exists() and p.is_file():
            dest = snap_folder / p.name
            try:
                shutil.copy2(p, dest)
                backed_up_files.append({"original": str(p.resolve()), "backup": str(dest)})
            except Exception as e:
                logger.error(f"Snapshot dosya kopyalama hatasi ({fpath}): {e}")

    meta = {
        "snapshot_id": snap_id,
        "label": label,
        "created_at": time.time(),
        "files": backed_up_files
    }
    (snap_folder / "metadata.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"[Git Safety] 💾 Snapshot oluşturuldu: {snap_id} ({len(backed_up_files)} dosya)", flush=True)
    return snap_id


def rollback_to_snapshot(snapshot_id: str) -> tuple[bool, str]:
    """
    Belirtilen Snapshot'taki dosyaları orijinal konumlarına geri yükler (Rollback).
    """
    snap_folder = SNAPSHOTS_DIR / snapshot_id
    meta_file = snap_folder / "metadata.json"
    if not snap_folder.exists() or not meta_file.exists():
        return False, f"Snapshot bulunamadı: '{snapshot_id}'"

    try:
        meta = json.loads(meta_file.read_text(encoding="utf-8"))
        restored = []
        for item in meta.get("files", []):
            orig = Path(item["original"])
            bkp = Path(item["backup"])
            if bkp.exists():
                shutil.copy2(bkp, orig)
                restored.append(orig.name)

        print(f"[Git Safety] ⏪ Rollback tamamlandı: {snapshot_id} ({len(restored)} dosya geri yüklendi)", flush=True)
        return True, f"✓ Başarıyla {len(restored)} dosya geri yüklendi: {', '.join(restored)}"
    except Exception as e:
        logger.error(f"Rollback hatasi: {e}")
        return False, f"Rollback sırasında hata oluştu: {e}"
