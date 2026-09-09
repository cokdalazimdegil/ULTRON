"""
ULTRON Operator & Developer CLI — Merkezi Yönetim Komut Satırı (Phase 9)
═══════════════════════════════════════════════════════════════════════
Sistem teşhisi, durum görüntüleme, bildirim gönderme, event yayınlama,
hafıza yönetimi ve RAG aramaları için tek komut satırı arayüzü.

Kullanım:
    python -X utf8 cli/ultron_cli.py doctor
    python -X utf8 cli/ultron_cli.py status
    python -X utf8 cli/ultron_cli.py notify "Test" "Mesaj" --priority high
    python -X utf8 cli/ultron_cli.py event "custom.test" '{"hello":"world"}'
    python -X utf8 cli/ultron_cli.py rag search "Event Bus"
    python -X utf8 cli/ultron_cli.py memory set preferences theme dark
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))


def cmd_doctor(args):
    """Sistem teşhisini çalıştırır."""
    from cli.doctor import run_diagnostics
    run_diagnostics()


def cmd_status(args):
    """Sistem anlık durumunu raporlar."""
    print("\n" + "═" * 60)
    print("  📊 ULTRON ANLIK SİSTEM DURUMU")
    print("═" * 60 + "\n")

    # 1. Varlık Durumu
    try:
        from core.presence_engine import presence_engine
        info = presence_engine.get_state_info()
        secs = int(info['seconds_in_state'])
        if secs > 0 and info['last_change'] > 0:
            dur_str = f"{secs}s bu durumda"
        else:
            dur_str = "başlangıç durumunda"
        print(f"  👤 Varlık Durumu:      {info['state'].upper()} ({dur_str})")
    except Exception as e:
        print(f"  👤 Varlık Durumu:      Hata ({e})")

    # 2. Coğrafi Bölgeler
    try:
        from core.geofence_engine import geofence_engine
        zones = geofence_engine.get_zones()
        if zones:
            desc_parts = [f"{z['name']} ({z.get('description', '') or 'Bölge'} - [{z['lat']:.4f}, {z['lng']:.4f}])" for z in zones]
            print(f"  📍 Tanımlı Bölgeler:    {len(zones)} adet -> {', '.join(desc_parts)}")
        else:
            print("  📍 Tanımlı Bölgeler:    0 adet (yok)")
    except Exception as e:
        print(f"  📍 Tanımlı Bölgeler:    Hata ({e})")

    # 3. Hafıza İstatistikleri
    try:
        from core.unified_memory import unified_memory
        stats = unified_memory.get_stats()
        print(f"  🧠 Birleşik Hafıza:     {stats['total_records']} kayıt ({stats.get('by_tier', {})})")
    except Exception as e:
        print(f"  🧠 Birleşik Hafıza:     Hata ({e})")

    # 4. Bildirim Motoru
    try:
        from core.notification_engine import notification_engine
        hist = notification_engine.get_history(limit=5)
        print(f"  🔔 Son Bildirimler:     {len(hist)} adet kayıtlı")
    except Exception as e:
        print(f"  🔔 Bildirim Motoru:     Hata ({e})")

    print("\n" + "═" * 60 + "\n")


def cmd_notify(args):
    """NotificationEngine üzerinden çok kanallı bildirim gönderir."""
    from core.notification_engine import notification_engine, NotificationChannel
    from core.events import EventPriority

    prio_map = {
        "low": EventPriority.LOW,
        "normal": EventPriority.NORMAL,
        "high": EventPriority.HIGH,
        "critical": EventPriority.CRITICAL,
    }
    prio = prio_map.get(args.priority.lower(), EventPriority.NORMAL)

    channels = None
    if args.channel:
        ch_map = {
            "web_ui": NotificationChannel.WEB_UI,
            "gemini": NotificationChannel.GEMINI,
            "tts": NotificationChannel.TTS,
            "ha": NotificationChannel.HOME_ASSISTANT,
        }
        if args.channel in ch_map:
            channels = [ch_map[args.channel]]

    res = notification_engine.notify(
        title=args.title,
        message=args.message,
        priority=prio,
        channels=channels,
        source="cli",
    )
    if res.delivered:
        print(f"✓ Bildirim gönderildi: [{prio.name}] {args.title} -> {res.channels_used}")
    else:
        print("✗ Bildirim gönderilemedi veya hiçbir kanal tarafından teslim alınamadı.")


def cmd_event(args):
    """Event Bus'a manuel event yayınlar."""
    from core.event_bus import bus
    from core.events import UltronEvent, EventPriority, EventSource

    payload = {}
    if args.payload:
        try:
            payload = json.loads(args.payload)
        except Exception:
            payload = {"raw": args.payload}

    prio_map = {
        "low": EventPriority.LOW,
        "normal": EventPriority.NORMAL,
        "high": EventPriority.HIGH,
        "critical": EventPriority.CRITICAL,
    }
    prio = prio_map.get(args.priority.lower(), EventPriority.NORMAL)

    event = UltronEvent(
        event_type=args.event_type,
        source=EventSource.CLI,
        payload=payload,
        priority=prio,
    )
    bus.publish_event(event)
    print(f"✓ Event yayınlandı: '{event.event_type}' (ID: {event.event_id}, Priority: {event.priority.name})")


def cmd_rag(args):
    """Yerel RAG arama ve indeksleme."""
    from core.local_rag_engine import local_rag

    if args.rag_action == "search":
        results = local_rag.search(args.query, limit=args.limit)
        print(f"\n🔍 '{args.query}' için {len(results)} sonuç bulundu:\n")
        for i, r in enumerate(results, 1):
            title = r.metadata.get("title", "Doküman")
            print(f"[{i}] {title} (Skor: {r.score:.2f})")
            print(f"    {r.text[:200]}...\n")

    elif args.rag_action == "index":
        text = args.content
        path = Path(args.content)
        if path.exists() and path.is_file():
            text = path.read_text(encoding="utf-8", errors="replace")
        
        chunks = local_rag.index_document(args.title, text)
        print(f"✓ Doküman '{args.title}' indekslendi ({len(chunks)} parça).")


def cmd_memory(args):
    """Unified Memory yönetimi."""
    from core.unified_memory import unified_memory

    if args.mem_action == "get":
        val = unified_memory.get(args.category, args.key)
        if val is not None:
            print(f"[{args.category}] {args.key} = {val}")
        else:
            print(f"Kayıt bulunamadı: {args.category}::{args.key}")

    elif args.mem_action == "set":
        unified_memory.store(args.category, args.key, args.value)
        print(f"✓ Hafızaya kaydedildi: [{args.category}] {args.key} = {args.value}")

    elif args.mem_action == "search":
        results = unified_memory.search(args.query, limit=args.limit)
        print(f"\n🔍 '{args.query}' için hafıza sonuçları ({len(results)} kayıt):\n")
        for r in results:
            print(f"  • [{r['category'].upper()}] {r['key']}: {r['value']} (Skor: {r['score']:.2f})")
        print()


def cmd_geofence(args):
    """Coğrafi bölge (geofence) yönetimi."""
    from core.geofence_engine import geofence_engine

    if args.geo_action == "list":
        zones = geofence_engine.get_zones()
        print(f"\n📍 Tanımlı Coğrafi Bölgeler ({len(zones)} adet):\n")
        for z in zones:
            desc = f" - {z['description']}" if z.get('description') else ""
            print(f"  • {z['name'].upper()}{desc}: ({z['lat']:.6f}, {z['lng']:.6f}), Yarıçap: {z['radius_meters']:.0f}m")
        print()

    elif args.geo_action == "add":
        z = geofence_engine.add_zone(
            name=args.name,
            lat=float(args.lat),
            lng=float(args.lng),
            radius_meters=float(args.radius),
            description=args.desc or "",
        )
        print(f"✓ Coğrafi bölge kaydedildi: '{z.name}' [{z.lat:.6f}, {z.lng:.6f}] (yarıçap: {z.radius_meters:.0f}m)")

    elif args.geo_action == "remove":
        ok = geofence_engine.remove_zone(args.name)
        if ok:
            print(f"✓ Bölge silindi: '{args.name}'")
        else:
            print(f"✗ Bölge bulunamadı: '{args.name}'")


def main():
    parser = argparse.ArgumentParser(
        prog="ultron",
        description="ULTRON Kişisel Yapay Zeka Asistanı — Komut Satırı Yönetim Aracı",
    )
    subparsers = parser.add_subparsers(dest="command", help="Komutlar")

    # doctor
    subparsers.add_parser("doctor", help="Sistem sağlık ve bağımlılık kontrolü")

    # status
    subparsers.add_parser("status", help="Anlık varlık, hafıza ve servis durumları")

    # notify
    p_notify = subparsers.add_parser("notify", help="Çok kanallı bildirim gönder")
    p_notify.add_argument("title", help="Bildirim başlığı")
    p_notify.add_argument("message", help="Bildirim mesajı")
    p_notify.add_argument("--priority", choices=["low", "normal", "high", "critical"], default="normal")
    p_notify.add_argument("--channel", choices=["web_ui", "gemini", "tts", "ha"], default=None)

    # event
    p_event = subparsers.add_parser("event", help="Event Bus'a event yayınla")
    p_event.add_argument("event_type", help="Event türü (örn: user.custom_alert)")
    p_event.add_argument("payload", nargs="?", default="{}", help="JSON payload")
    p_event.add_argument("--priority", choices=["low", "normal", "high", "critical"], default="normal")

    # rag
    p_rag = subparsers.add_parser("rag", help="Yerel RAG arama ve indeksleme")
    rag_subs = p_rag.add_subparsers(dest="rag_action")

    p_rag_search = rag_subs.add_parser("search", help="RAG'de arama yap")
    p_rag_search.add_argument("query", help="Arama sorgusu")
    p_rag_search.add_argument("--limit", type=int, default=5)

    p_rag_index = rag_subs.add_parser("index", help="Doküman indeksle")
    p_rag_index.add_argument("title", help="Doküman başlığı")
    p_rag_index.add_argument("content", help="Doküman metni veya dosya yolu")

    # memory
    p_mem = subparsers.add_parser("memory", help="Hafıza yönetimi")
    mem_subs = p_mem.add_subparsers(dest="mem_action")

    p_mem_get = mem_subs.add_parser("get", help="Kayıt getir")
    p_mem_get.add_argument("category", help="Kategori")
    p_mem_get.add_argument("key", help="Anahtar")

    p_mem_set = mem_subs.add_parser("set", help="Kayıt ekle / güncelle")
    p_mem_set.add_argument("category", help="Kategori")
    p_mem_set.add_argument("key", help="Anahtar")
    p_mem_set.add_argument("value", help="Değer")

    p_mem_search = mem_subs.add_parser("search", help="Hafıza ara")
    p_mem_search.add_argument("query", help="Arama sorgusu")
    p_mem_search.add_argument("--limit", type=int, default=5)

    # geofence
    p_geo = subparsers.add_parser("geofence", help="Coğrafi bölge yönetimi")
    geo_subs = p_geo.add_subparsers(dest="geo_action")

    geo_subs.add_parser("list", help="Bölgeleri listele")

    p_geo_add = geo_subs.add_parser("add", help="Yeni bölge ekle")
    p_geo_add.add_argument("name", help="Bölge adı (örn: home, ofis)")
    p_geo_add.add_argument("lat", type=float, help="Enlem (latitude)")
    p_geo_add.add_argument("lng", type=float, help="Boylam (longitude)")
    p_geo_add.add_argument("--radius", type=float, default=150.0, help="Yarıçap metre cinsinden (varsayılan: 150)")
    p_geo_add.add_argument("--desc", default="", help="Açıklama / adres")

    p_geo_rm = geo_subs.add_parser("remove", help="Bölge sil")
    p_geo_rm.add_argument("name", help="Bölge adı")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    dispatch = {
        "doctor": cmd_doctor,
        "status": cmd_status,
        "notify": cmd_notify,
        "event": cmd_event,
        "rag": cmd_rag,
        "memory": cmd_memory,
        "geofence": cmd_geofence,
    }

    fn = dispatch.get(args.command)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
