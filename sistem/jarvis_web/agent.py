#!/usr/bin/env python3
"""
JARVIS Web — Bilgisayar Ajanı
─────────────────────────────
Backend sunucusuna bağlanır ve sistem araçlarını (uygulama açma, takvim,
anımsatıcı, shell, ekran analizi, WhatsApp, medya...) bu bilgisayarda
çalıştırır. macOS ve Windows'ta aynı şekilde çalışır.

Çalıştırma:
    python agent.py                           # localhost'taki sunucuya
    python agent.py --server ws://1.2.3.4:8765 --token <token>

Token verilmezse aynı klasördeki web_config.json'dan okunur.
"""

from __future__ import annotations

import sys

import asyncio
import argparse
import json
import ssl
import traceback
from pathlib import Path

import websockets

# ── Ana proje modüllerine erişim ─────────────────────────────────────────────
WEB_DIR  = Path(__file__).resolve().parent
BASE_DIR = WEB_DIR.parent
sys.path.insert(0, str(BASE_DIR))

from actions.open_app  import open_app
from actions.sys_info  import sys_info
from actions.weather   import get_weather_summary
from actions.reminders import get_reminders, add_reminder, delete_reminder
from actions.browser   import browser_control
from actions.shell     import shell_run
from actions.whatsapp  import send_whatsapp_message, save_whatsapp_contact
from actions.media     import play_media, control_media
from actions.screen_vision import analyze_screen
from actions.win_controls import control_system
from actions.smarthome import control_home_device, get_home_status
from actions.file_tools import file_operations
from actions.clipboard_tools import clipboard_control
from actions.web_tools import fetch_webpage_content
from actions.proactive_engine import set_proactive_timer, get_active_timers, cancel_timer
from actions.location_tracker import get_user_location
from actions.youtube_stats import get_youtube_channel_report
from actions.research_engine import handle_web_search, handle_deep_research
from memory.memory_manager import update_memory, delete_memory

RECONNECT_DELAY = 3.0


def execute_tool(name: str, args: dict) -> str:
    """Masaüstü main.py'deki araç dağıtımının ajan kopyası (UI'sız)."""
    try:
        # ── Skill Router: önce dinamik skill sistemine sor ───────────────────
        try:
            from skills import execute_skill
            skill_result = execute_skill(name, args)
            if skill_result is not None:
                return skill_result
        except Exception:
            pass  # Skill sistemi çalışmıyorsa mevcut if-elif zincirine devam

        if name == "open_app":
            return open_app(args.get("app_name", "")) or \
                   f"{args.get('app_name')} açıldı."

        if name == "sys_info":
            return sys_info(args.get("query", "all")) or "Bilgi alındı."

        if name == "get_weather":
            return get_weather_summary(args.get("location") or None) or "Hava durumu alındı."

        if name == "save_memory":
            cat = args.get("category", "notes")
            key = args.get("key", "")
            val = args.get("value", "") or ""
            content = args.get("content", "") or ""
            if key:
                update_memory({cat: {key: {"value": val or content[:200]}}})
            # Also store to vector memory (long content support)
            if content or val:
                try:
                    from memory.vector_store import vector_memory
                    text = content if content else val
                    vector_memory.add(
                        text=text,
                        metadata={"category": cat, "key": key},
                    )
                except Exception:
                    pass
            return "Hafızaya kaydedildi."

        if name == "search_memory":
            query = args.get("query", "")
            limit = int(args.get("limit", 5) or 5)
            try:
                from memory.vector_store import vector_memory
                results = vector_memory.search(query, n=limit)
                if not results:
                    return "Hafızada bu konuyla ilgili kayıt bulunamadı."
                lines = [f"🔍 '{query}' için hafıza sonuçları ({len(results)} kayıt):"]
                for i, r in enumerate(results, 1):
                    cat = r.metadata.get("category", "")
                    key = r.metadata.get("key", "")
                    label = f"{cat}/{key}" if cat else key or r.doc_id
                    score_pct = round(r.score * 100)
                    lines.append(f"{i}. [{label}] ({score_pct}% eşleşme): {r.text[:300]}")
                return "\n".join(lines)
            except Exception as e:
                # Fallback to json memory
                try:
                    from memory.memory_manager import load_memory
                    mem = load_memory()
                    q_lower = query.lower()
                    matches = []
                    for cat, items in mem.items():
                        if isinstance(items, dict):
                            for k, v in items.items():
                                val = v.get("value", str(v)) if isinstance(v, dict) else str(v)
                                if q_lower in f"{k} {val} {cat}".lower():
                                    matches.append(f"• {cat}/{k}: {val}")
                    if matches:
                        return f"🔍 '{query}' için hafıza:\n" + "\n".join(matches[:limit])
                    return "Hafızada bu konuyla ilgili kayıt bulunamadı."
                except Exception:
                    return f"Hafıza araması başarısız: {e}"

        if name == "delete_memory":
            return delete_memory(
                args.get("category", ""),
                args.get("key", ""),
                args.get("match_text", ""),
            ) or "Hafızadan silindi."

        if name == "web_search":
            return handle_web_search(args)

        if name == "trigger_phone_call":
            from actions.twilio_caller import make_phone_call
            return make_phone_call(args.get("message", "Ultron acil durum uyarısı."))

        if name == "deep_research":
            return handle_deep_research(args)

        if name == "get_reminders":
            return get_reminders(
                args.get("query", "upcoming"),
                int(args.get("limit", 8) or 8),
                args.get("list_name", ""),
            ) or "Animsatici bilgisi alindi."

        if name == "add_reminder":
            return add_reminder(
                args.get("title", ""),
                args.get("due_iso", ""),
                args.get("notes", ""),
                args.get("list_name", ""),
                args.get("priority", ""),
                bool(args.get("all_day", False)),
            ) or "Animsatici eklendi."

        if name == "delete_reminder":
            return delete_reminder(
                args.get("title", ""),
                args.get("list_name", ""),
            ) or "Animsatici silme islemi tamamlandi."

        if name == "browser_control":
            return browser_control(
                args.get("action"),
                args.get("url"),
                args.get("query"),
            ) or "Tamam."

        if name == "shell_run":
            return shell_run(
                args.get("command", ""),
                args.get("cwd", ""),
            ) or "Komut çalıştırıldı."

        if name == "workspace_search_emails":
            from actions.workspace.gmail_service import search_emails
            res = search_emails(args.get("query", ""), int(args.get("max_results", 5)))
            return str(res)

        if name == "workspace_read_email":
            from actions.workspace.gmail_service import read_email_content
            return read_email_content(args.get("message_id", ""))

        if name == "workspace_draft_email":
            from actions.workspace.gmail_service import send_or_draft_email
            return send_or_draft_email(
                args.get("to", ""), 
                args.get("subject", ""), 
                args.get("body", ""), 
                bool(args.get("is_draft", True))
            )

        if name == "workspace_search_drive":
            from actions.workspace.drive_service import search_drive_files
            res = search_drive_files(args.get("name_query", ""), args.get("mime_type"))
            return str(res)

        if name == "workspace_read_drive_file":
            from actions.workspace.drive_service import read_drive_file
            return read_drive_file(args.get("file_id", ""))

        if name == "workspace_upload_drive":
            from actions.workspace.drive_service import upload_file_to_drive
            return upload_file_to_drive(args.get("file_path", ""))

        if name == "workspace_get_upcoming_events":
            from actions.workspace.calendar_service import get_upcoming_events
            res = get_upcoming_events(int(args.get("days_ahead", 1)))
            return str(res)

        if name == "workspace_create_event":
            from actions.workspace.calendar_service import create_calendar_event
            return create_calendar_event(
                args.get("title", ""),
                args.get("start_time", ""),
                args.get("end_time", ""),
                args.get("description", "")
            )

        if name == "play_media":
            return play_media(
                args.get("query", ""),
                args.get("provider", "auto"),
                bool(args.get("autoplay", True)),
            ) or "Medya oynatma başlatıldı."

        if name == "control_media":
            return control_media(args.get("action", "pause")) or "Medya komutu gonderildi."

        if name == "get_youtube_channel_report":
            return get_youtube_channel_report(
                args.get("query", "overview"),
                args.get("handle", ""),
                int(args.get("video_limit", 6) or 6),
            ) or "YouTube kanal raporu alindi."

        if name == "analyze_screen":
            return analyze_screen(
                args.get("query", "Ekranda ne var?"),
                args.get("target", "active_window"),
            ) or "Ekran analizi tamamlandi."

        if name == "send_whatsapp_message":
            return send_whatsapp_message(
                args.get("message", ""),
                args.get("phone_number", ""),
                args.get("recipient_name", ""),
                bool(args.get("send_now", False)),
                args.get("app_target", "auto"),
            ) or "WhatsApp işlemi tamamlandı."

        if name == "save_whatsapp_contact":
            return save_whatsapp_contact(
                args.get("display_name", ""),
                args.get("phone_number", ""),
                args.get("aliases", ""),
            ) or "WhatsApp kişisi kaydedildi."

        if name == "control_system":
            return control_system(
                args.get("action", ""),
                args.get("value"),
            ) or "Sistem işlemi uygulandı."

        if name == "control_home_device":
            return control_home_device(
                args.get("device_name", ""),
                args.get("action", "toggle"),
                args.get("brightness"),
                args.get("color"),
                args.get("temperature"),
            ) or "Akıllı ev işlemi uygulandı."

        if name == "get_home_status":
            return get_home_status(
                args.get("query", "all"),
            ) or "Akıllı ev durumu alındı."

        if name == "file_operations":
            return file_operations(
                args.get("action", "read"),
                args.get("path", ""),
                args.get("content", ""),
                args.get("search_query", ""),
            ) or "Dosya işlemi tamamlandı."

        if name == "clipboard_control":
            return clipboard_control(
                args.get("action", "get"),
                args.get("text", ""),
            ) or "Pano işlemi tamamlandı."

        if name == "fetch_webpage_content":
            return fetch_webpage_content(
                args.get("url", ""),
            ) or "Web sayfası içeriği alındı."

        if name == "set_proactive_timer":
            return set_proactive_timer(
                args.get("title", ""),
                float(args.get("minutes", 0) or 0),
                float(args.get("seconds", 0) or 0),
                args.get("due_iso", ""),
                args.get("user", "YARATICI"),
                bool(args.get("is_task", False)),
            ) or "Hatırlatıcı ayarlandı."

        if name == "get_active_timers":
            return get_active_timers() or "Aktif sayaç yok."

        if name == "cancel_timer":
            return cancel_timer(args.get("query", "")) or "İptal edildi."

        if name == "get_user_location":
            return get_user_location(args.get("user_name", "all")) or "Konum alındı."

        if name == "send_email":
            from actions.email_manager import send_email
            return send_email(
                args.get("to_address", ""),
                args.get("subject", ""),
                args.get("body", "")
            )

        if name == "screen_awareness":
            from computer.screen_analyzer import analyze_current_screen
            question = args.get("question", "")
            force_v = bool(args.get("force_vision", False))
            res = analyze_current_screen(user_question=question, force_vision=force_v)
            return res.get("summary", "Ekran analizi tamamlandı.")

        if name == "computer_control":
            action = args.get("action", "").lower().strip()
            x = args.get("x")
            y = args.get("y")
            text = args.get("text", "")
            key = args.get("key", "")
            target = args.get("target", "")
            grounding_mode = bool(args.get("grounding_mode", False))

            from computer.mouse_controller import move_mouse, click, double_click, right_click, scroll, drag
            from computer.keyboard_controller import type_text, press_key, hotkey, paste_text
            from computer.window_manager import focus_window, minimize_window, maximize_window, close_window
            from computer.safety_manager import SafetyManager

            safety = SafetyManager.evaluate_risk(action, target or text)
            if safety["requires_confirmation"]:
                return safety["warning"]

            # ── Grounding Mode: Gemini Vision ile koordinat tespiti ─────────
            if grounding_mode and action in ("click", "double_click", "right_click") and target:
                try:
                    from computer.gemini_grounding import ground_and_click
                    result = ground_and_click(
                        target_description=target,
                        double_click=(action == "double_click"),
                    )
                    if result["success"]:
                        return result["message"]
                    # Grounding başarısız — koordinata düş
                    if x is None or y is None:
                        return f"⚠️ Grounding başarısız: {result['message']}"
                    # Fall through to manual coords if provided
                except Exception as grounding_err:
                    import traceback as _tb
                    if x is None or y is None:
                        return f"⚠️ Grounding hatası: {grounding_err}"

            if action == "click":
                ok = click(int(x) if x is not None else None, int(y) if y is not None else None)
                return "Tıklandı." if ok else "Tıklama başarısız."
            elif action == "double_click":
                ok = double_click(int(x) if x is not None else None, int(y) if y is not None else None)
                return "Çift tıklandı." if ok else "Başarısız."
            elif action == "right_click":
                ok = right_click(int(x) if x is not None else None, int(y) if y is not None else None)
                return "Sağ tıklandı." if ok else "Başarısız."
            elif action == "move_mouse":
                if x is not None and y is not None:
                    move_mouse(int(x), int(y))
                    return f"Fare ({x}, {y}) konumuna taşındı."
                return "Geçersiz koordinat."
            elif action == "scroll":
                scroll(int(y or -3))
                return "Kaydırma yapıldı."
            elif action == "type_text":
                ok = type_text(text)
                return f"'{text}' yazıldı." if ok else "Yazma başarısız."
            elif action == "paste_text":
                ok = paste_text(text)
                return f"'{text}' yapıştırıldı." if ok else "Yapıştırma başarısız."
            elif action == "press_key":
                ok = press_key(key or target)
                return f"'{key or target}' tuşuna basıldı." if ok else "Tuş bulunamadı."
            elif action == "hotkey":
                keys = [k.strip() for k in (key or target).split("+")]
                ok = hotkey(*keys)
                return f"'{'+'.join(keys)}' kısayolu çalıştırıldı." if ok else "Kısayol başarısız."
            elif action == "focus_window":
                ok = focus_window(target)
                return f"'{target}' penceresi öne getirildi." if ok else f"'{target}' penceresi bulunamadı."
            elif action == "minimize_window":
                ok = minimize_window(target)
                return f"'{target}' küçültüldü." if ok else "Pencere bulunamadı."
            elif action == "maximize_window":
                ok = maximize_window(target)
                return f"'{target}' büyütüldü." if ok else "Pencere bulunamadı."
            elif action == "close_window":
                ok = close_window(target)
                return f"'{target}' kapatıldı." if ok else "Pencere bulunamadı."
            return f"Bilinmeyen bilgisayar kontrol eylemi: {action}"


        if name == "browser_action":
            action = args.get("action", "").lower().strip()
            url = args.get("url", "").strip()
            query = args.get("query", "").strip()
            from computer.browser_controller import browser_open, browser_search, browser_read_page, browser_new_tab, browser_back

            if action == "open":
                ok, msg = browser_open(url)
                return msg
            elif action == "search":
                ok, msg = browser_search(query)
                return msg
            elif action == "read_page":
                return browser_read_page(url)
            elif action == "new_tab":
                ok = browser_new_tab(url)
                return "Yeni sekme açıldı." if ok else "Sekme açılamadı."
            elif action == "back":
                ok = browser_back()
                return "Önceki sayfaya dönüldü." if ok else "Geri dönülemedi."
            return f"Bilinmeyen tarayıcı eylemi: {action}"

        if name == "start_swarm_project":
            desc = args.get("project_description", "").strip()
            import threading
            from orchestrator.swarm_manager import swarm_manager
            
            # Arka planda çalıştır (Zaman aşımını önlemek için)
            threading.Thread(target=swarm_manager.start_project, args=(desc,), daemon=True).start()
            return "Swarm projesi arka planda başarıyla başlatıldı. Takım (PM, Coder, QA) görevi aldı."

        if name == "start_companion_mode":
            from actions.companion_mode import companion_engine
            return companion_engine.start()

        if name == "stop_companion_mode":
            from actions.companion_mode import companion_engine
            return companion_engine.stop()

        if name == "autonomous_task":
            desc = args.get("task_description", "").strip()
            is_res = bool(args.get("research_mode", False))
            import threading
            
            def _run_autonomous():
                from computer.task_executor import TaskEngine
                if is_res:
                    from computer.research_engine import execute_research_plan
                    execute_research_plan(desc)
                else:
                    task = TaskEngine.create_task(desc, owner="YARATICI")
                    TaskEngine.execute_task_sync(task)
                    
            threading.Thread(target=_run_autonomous, daemon=True).start()
            return "Otonom görev arka planda başlatıldı."

        if name == "emergency_stop":
            from computer.safety_manager import SafetyManager
            from computer.task_executor import cancel_all_tasks
            cancel_all_tasks()
            return SafetyManager.trigger_emergency_stop()

        if name == "orchestrate_task":
            desc = args.get("task_description", "").strip()
            import threading
            
            def _run_orchestration():
                from orchestrator.orchestrator_engine import OrchestratorEngine
                OrchestratorEngine.orchestrate_task(desc, user_name="YARATICI")
                
            threading.Thread(target=_run_orchestration, daemon=True).start()
            return "Orkestrasyon arka planda başlatıldı. Geliştirme, test ve analiz işlemleri bittiğinde bilgi verilecek."

        if name == "code_action":
            action = args.get("action", "").lower().strip()
            file_path = args.get("file_path", "").strip()
            code_content = args.get("code_content", "")
            from orchestrator.coding_agent import CodingAgent
            if action == "write_file":
                ok, msg = CodingAgent.write_code_file(file_path, code_content)
                return msg
            elif action == "execute_and_fix":
                res = CodingAgent.execute_and_self_correct(file_path)
                return f"Çalıştırma Sonucu: {'BAŞARILI' if res['success'] else 'BAŞARISIZ'} ({res['attempts']} deneme)"
            elif action == "validate_syntax":
                ok, msg = CodingAgent.validate_python_syntax(code_content)
                return msg
            return f"Bilinmeyen kod eylemi: {action}"

        if name == "run_tests":
            path = args.get("test_script_path", "").strip()
            from orchestrator.testing_agent import TestingAgent
            res = TestingAgent.run_test_script(path)
            return res.get("summary", "Test tamamlandı.")

        if name == "code_review":
            text = args.get("code_or_diff", "")
            is_diff = bool(args.get("is_diff", False))
            from orchestrator.reviewer_agent import ReviewerAgent
            if is_diff:
                res = ReviewerAgent.review_diff(text)
            else:
                res = ReviewerAgent.review_code(text)
            return res.get("feedback", "İnceleme tamamlandı.")

        if name == "git_snapshot_rollback":
            action = args.get("action", "").lower().strip()
            snap_id = args.get("snapshot_id", "").strip()
            label = args.get("label", "").strip()
            from orchestrator.git_safety import get_git_status, get_git_diff, create_snapshot, rollback_to_snapshot
            if action == "create_snapshot":
                sid = create_snapshot(label=label)
                return f"Snapshot oluşturuldu: {sid}"
            elif action == "rollback":
                ok, msg = rollback_to_snapshot(snap_id)
                return msg
            elif action == "status":
                st = get_git_status()
                return f"Değişen dosyalar: {len(st.get('modified', []))} adet."
            elif action == "diff":
                return get_git_diff()[:3000]
            return f"Bilinmeyen git/snapshot eylemi: {action}"

        if name == "draft_reply":
            from actions.digital_clone import generate_clone_reply, notify_pending_reply
            draft = generate_clone_reply(
                original_message=args.get("original_message", ""),
                platform=args.get("platform", "genel"),
                sender_name=args.get("sender_name", "Biri"),
            )
            return notify_pending_reply(draft)

        return f"Bilinmeyen araç: {name}"

    except Exception as e:
        traceback.print_exc()
        # ── Self-Healer: ardışık hata varsa onarım başlat ────────────────────
        try:
            import traceback as _tb
            tb_str = _tb.format_exc()
            from core.self_healer import self_healer
            repaired = self_healer.record_failure(name, str(e), tb_str)
            if repaired:
                return f"Hata: {e}\n🔧 Ardışık hata tespit edildi — otomatik onarım başlatıldı."
        except Exception:
            pass
        return f"Hata: {e}"


async def handle_connection(ws):
    print("[Ajan] ✅ Sunucuya bağlandı — araç çağrıları bekleniyor.")
    loop = asyncio.get_event_loop()

    async def run_call(obj: dict):
        name = obj.get("name", "")
        args = obj.get("args", {}) or {}
        print(f"[Ajan] 🔧 {name} {args}")
        result = await loop.run_in_executor(None, lambda: execute_tool(name, args))
        print(f"[Ajan] 📤 {name} → {str(result)[:80]}")
        await ws.send(json.dumps(
            {"type": "tool_result", "id": obj.get("id", ""), "result": result},
            ensure_ascii=False,
        ))

    async for message in ws:
        try:
            obj = json.loads(message)
        except Exception:
            continue
        if obj.get("type") == "tool_call":
            # Eşzamanlı çağrılar birbirini bloklamasın
            asyncio.create_task(run_call(obj))


def load_token_from_config() -> str:
    # Baslatici token'i ortam degiskeniyle veriyor — dosya yazilamasa bile
    # ajan baglanabilsin diye ONCE buna bakiyoruz.
    import os

    env_token = str(os.environ.get("ULTRON_WEB_TOKEN", "") or os.environ.get("JARVIS_WEB_TOKEN", "") or "").strip()
    if env_token:
        return env_token

    # Sunucu token'i YAZILABILIR koke yaziyor. .exe'de WEB_DIR paketin
    # icidir (salt okunur) — oradan okursak token'i asla bulamayiz.
    candidates = []
    try:
        from app_paths import data_path

        candidates.append(data_path("jarvis_web", "web_config.json"))
    except Exception:
        pass
    candidates.append(WEB_DIR / "web_config.json")

    for path in candidates:
        try:
            cfg = json.loads(Path(path).read_text(encoding="utf-8"))
            token = str(cfg.get("token", "") or "")
            if token:
                return token
        except Exception:
            continue
    return ""


async def main():
    ap = argparse.ArgumentParser(description="ULTRON bilgisayar ajanı")
    ap.add_argument("--server", default="ws://127.0.0.1:8765",
                    help="Sunucu adresi, örn. wss://1.2.3.4:8765")
    ap.add_argument("--token", default="",
                    help="Erişim token'ı (boşsa web_config.json'dan okunur)")
    args = ap.parse_args()

    token = args.token or load_token_from_config()
    if not token:
        print("[Ajan] ❌ Token bulunamadı. --token verin veya önce sunucuyu çalıştırın.")
        return

    server_base = args.server.rstrip('/')
    if server_base.endswith('/ws/agent'):
        server_base = server_base[:-len('/ws/agent')]
    url = f"{server_base}/ws/agent?token={token}"

    ssl_ctx = None
    if url.startswith("wss://"):
        # Kendinden imzalı sertifika kabul edilir (v1)
        ssl_ctx = ssl.create_default_context()
        ssl_ctx.check_hostname = False
        ssl_ctx.verify_mode = ssl.CERT_NONE

    print(f"[Ajan] 🔌 Bağlanılıyor: {args.server}")
    while True:
        try:
            async with websockets.connect(url, ssl=ssl_ctx,
                                          ping_interval=20) as ws:
                await handle_connection(ws)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[Ajan] ⚠️  Bağlantı sorunu: {e} — {RECONNECT_DELAY:.0f}s sonra tekrar denenecek.")
        await asyncio.sleep(RECONNECT_DELAY)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[Ajan] 👋 Kapatıldı.")
