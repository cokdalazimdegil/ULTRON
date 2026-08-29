"""
ULTRON — Canlı Konum Takip Modülü
─────────────────────────────────
YARATICI ve AILE_UYESI'nın canlı konumlarını kaydeder, aralarındaki mesafeyi
hesaplar ve Gemini asistanına coğrafi bilgi sağlar.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
import urllib.request
import urllib.parse

from app_paths import data_path

LOCATION_FILE = data_path("memory", "user_locations.json")
GEO_CACHE: dict[str, str] = {}


def _load_locations() -> dict:
    try:
        if LOCATION_FILE.exists():
            return json.loads(LOCATION_FILE.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {
        "YARATICI": {"lat": None, "lng": None, "accuracy": None, "address": "Bilinmiyor", "updated_at": 0},
        "AILE_UYESI": {"lat": None, "lng": None, "accuracy": None, "address": "Bilinmiyor", "updated_at": 0}
    }


def _save_locations(data: dict) -> None:
    try:
        LOCATION_FILE.parent.mkdir(parents=True, exist_ok=True)
        LOCATION_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def reverse_geocode(lat: float, lng: float) -> str:
    """Enlem ve boylamı semt/şehir adresine çevirir (önbellekli)."""
    key = f"{round(lat, 3)},{round(lng, 3)}"
    if key in GEO_CACHE:
        return GEO_CACHE[key]

    try:
        url = f"https://nominatim.openstreetmap.org/reverse?format=json&lat={lat}&lon={lng}&zoom=16&addressdetails=1"
        req = urllib.request.Request(url, headers={"User-Agent": "UltronAssistant/2.0 (ulrton@local.ai)"})
        with urllib.request.urlopen(req, timeout=4) as response:
            res = json.loads(response.read().decode("utf-8"))
            addr = res.get("address", {})
            parts = []
            for k in ("suburb", "neighbourhood", "district", "town", "city", "province"):
                if k in addr and addr[k] not in parts:
                    parts.append(addr[k])
            display = ", ".join(parts) if parts else res.get("display_name", f"{lat:.4f}, {lng:.4f}")
            GEO_CACHE[key] = display
            return display
    except Exception:
        return f"{lat:.4f}, {lng:.4f}"


def update_user_location(user_name: str, lat: float, lng: float, accuracy: float = None) -> dict:
    """Kullanıcının canlı konumunu günceller."""
    data = _load_locations()
    norm_name = "AILE_UYESI" if "rabia" in user_name.lower() else "YARATICI"
    
    address = reverse_geocode(lat, lng)
    
    record = {
        "lat": lat,
        "lng": lng,
        "accuracy": accuracy,
        "address": address,
        "updated_at": time.time(),
        "time_str": time.strftime("%H:%M:%S", time.localtime())
    }
    
    data[norm_name] = record
    _save_locations(data)
    return record


def _haversine_distance_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """İki GPS koordinatı arasındaki mesafeyi kilometre olarak hesaplar."""
    r = 6371.0  # Dünya yarıçapı (km)
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = math.sin(dlat / 2) ** 2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return r * c


def get_user_location(user_name: str = "all") -> str:
    """
    YARATICI ve AILE_UYESI'nın konum bilgilerini ve aralarındaki mesafeyi özetler.
    user_name: 'all', 'YARATICI', 'AILE_UYESI'
    """
    data = _load_locations()
    nuri = data.get("YARATICI", {})
    rabia = data.get("AILE_UYESI", {})

    def format_user(name: str, u: dict) -> str:
        if not u or u.get("lat") is None:
            return f"📍 {name}: Henüz konum sinyali alınmadı."
        
        diff_mins = int((time.time() - u.get("updated_at", 0)) / 60)
        time_text = "az önce" if diff_mins < 2 else f"{diff_mins} dk önce"
        acc = f" (±{int(u['accuracy'])}m)" if u.get("accuracy") else ""
        return f"📍 {name}: {u.get('address', 'Bilinmiyor')}{acc} [Güncelleme: {time_text}]"

    norm = (user_name or "all").lower()
    
    if "nuri" in norm:
        return format_user("YARATICI", nuri)
    if "rabia" in norm:
        return format_user("AILE_UYESI", rabia)

    # İkisi birden
    lines = [
        format_user("YARATICI", nuri),
        format_user("AILE_UYESI", rabia)
    ]

    if nuri.get("lat") is not None and rabia.get("lat") is not None:
        dist_km = _haversine_distance_km(nuri["lat"], nuri["lng"], rabia["lat"], rabia["lng"])
        if dist_km < 0.1:
            lines.append("💑 YARATICI ve AILE_UYESI şu anda yan yana (aynı konumdalar).")
        elif dist_km < 1.0:
            lines.append(f"📏 Aralarındaki mesafe: Yaklaşık {int(dist_km * 1000)} metre.")
        else:
            lines.append(f"📏 Aralarındaki mesafe: {dist_km:.1f} km.")

    return "\n".join(lines)
