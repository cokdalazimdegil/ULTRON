#!/usr/bin/env python3
"""
ULTRON Web — Backend sunucusu
─────────────────────────────
Web istemcileri (telefon/bilgisayar tarayıcısı) ile Gemini Live arasında
köprü kurar. bilgisayar ajanı bağlıysa sistem araçlarını (uygulama açma, takvim,
shell...) ona yönlendirir.

Çalıştırma:
    python3 server.py                  # http://0.0.0.0:8765
    python3 server.py --ssl            # https (telefon mikrofonu için gerekli)
    python3 server.py --port 9000

İlk çalıştırmada erişim token'ı üretilir ve ekrana basılır.
"""

from __future__ import annotations

import os
import sys
import time

import asyncio
import argparse
import datetime
import json
import secrets
import subprocess
import traceback
import uuid
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

from google import genai
from google.genai import types

# ── Ana proje modüllerine erişim (aynı makinede çalışırken) ─────────────────
WEB_DIR  = Path(__file__).resolve().parent
BASE_DIR = WEB_DIR.parent
sys.path.insert(0, str(BASE_DIR))

try:
    from tool_defs import TOOL_DECLARATIONS
except Exception:
    TOOL_DECLARATIONS = []
    print("[UYARI] tool_defs bulunamadı — araçsız modda çalışılıyor.")

try:
    from app_config import get_app_config_value, save_app_config, load_app_config
except Exception:
    def get_app_config_value(key, default=None):
        import os
        if key == "gemini_api_key":
            return os.environ.get("GEMINI_API_KEY", "")
        return default
    def save_app_config(updates):
        return updates
    def load_app_config():
        return {}

try:
    from memory.memory_manager import (
        load_memory, update_memory, delete_memory, format_memory_for_prompt,
    )
    MEMORY_OK = True
except Exception:
    MEMORY_OK = False

try:
    from actions.weather import get_weather_summary
    WEATHER_OK = True
except Exception:
    WEATHER_OK = False

# ── Mod ──────────────────────────────────────────────────────────────────────
# PUBLIC (herkese açık bulut): her kullanıcı KENDİ Gemini anahtarını girer,
#   bilgisayar/Mac kontrolü YOK, yalnızca bulut araçları. Ortak token yok.
# ÖZEL (varsayılan): sahibin anahtarı config'ten, bilgisayar ajanı + tüm araçlar,
#   ortak token ile korunur.
PUBLIC_MODE = os.environ.get("ULTRON_PUBLIC") == "1"

# ── Sabitler ─────────────────────────────────────────────────────────────────
LIVE_MODEL  = "models/gemini-2.5-flash-native-audio-latest"
try:
    from app_paths import data_path, resource_path

    PROMPT_PATH = resource_path("core", "prompt.txt")      # salt-okunur kaynak
    CONFIG_PATH = data_path("jarvis_web", "web_config.json")  # token → yazilabilir
except Exception:
    PROMPT_PATH = BASE_DIR / "core" / "prompt.txt"
    CONFIG_PATH = WEB_DIR / "web_config.json"

# Sunucuda (bulutta da çalışabilen) araçlar
SERVER_TOOLS = {"get_weather", "save_memory", "delete_memory", "search_memory"}
# Tarayıcıya yönlendirilen araçlar
CLIENT_TOOLS = {"toggle_webcam"}
# Geri kalan her şey → bilgisayar ajanı
# Herkese açık modda İZİN VERİLEN araçlar (bilgisayar/hesap kontrolü hariç)
PUBLIC_TOOLS = {"get_weather", "toggle_webcam", "save_memory", "search_memory", "delete_memory"}

AGENT_TOOL_TIMEOUT = 60  # shell / takvim helper'ları yavaş olabilir


# ── Yapılandırma ─────────────────────────────────────────────────────────────
def load_web_config() -> dict:
    try:
        return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def ensure_token() -> str:
    """Erişim token'ı: önce başlatıcının verdiği, sonra dosyadaki, yoksa yeni.

    ULTRON_WEB_TOKEN neden var: Token'ı eskiden yalnızca bu süreç üretip
    dosyaya yazıyordu, arayüz de o dosyadan okuyordu. Dosya yazılamazsa
    (salt-okunur klasör, izin sorunu, antivirüs) token bellekte kalıyor,
    arayüz boş okuyor ve telefona ?t= ile biten adres gidiyordu — telefon
    da token SORUYORDU. Artık token'ı başlatıcı üretip ortam değişkeniyle
    hem sunucuya hem ajana veriyor; dosya sadece yedek.
    """
    env_token = str(os.environ.get("ULTRON_WEB_TOKEN", "") or "").strip()
    if env_token:
        return env_token

    cfg = load_web_config()
    token = str(cfg.get("token", "") or "").strip()
    if not token:
        token = secrets.token_hex(16)
        cfg["token"] = token
        try:
            CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")
        except Exception:
            pass  # salt-okunur/geçici bulut FS — token bellek içinde kalır
    return token


# Herkese açık modda ortak token yok (herkesin anahtarı kendi kimliği)
TOKEN = "" if PUBLIC_MODE else ensure_token()
# Alt süreçlerin (DesktopHUD, vb.) doğru token'ı alabilmesi için ortama da yazalım.
if TOKEN:
    os.environ["ULTRON_WEB_TOKEN"] = TOKEN


def get_api_key() -> str:
    return str(get_app_config_value("gemini_api_key", "") or "")


def load_system_prompt() -> str:
    try:
        from prompt_loader import adapt_prompt

        base = adapt_prompt(PROMPT_PATH.read_text(encoding="utf-8"))
    except Exception:
        base = (
            "Sen ULTRON'sin — kişisel AI asistanı. Türkçe konuş. "
            "Kısa ve net yanıtlar ver. Araçları kullanarak görevleri tamamla."
        )
    if PUBLIC_MODE:
        web_ctx = (
            "\n\n[WEB — HERKESE AÇIK MOD]\n"
            "Kullanıcı sana telefon/bilgisayar tarayıcısından bağlanıyor. "
            "Bu sürümde bir bilgisayarı kontrol EDEMEZSİN: uygulama açma, shell, "
            "takvim, ekran gibi araçlar YOK. Sohbet edebilir, kullanıcının "
            "kamerasıyla görebilir (toggle_webcam) ve hava durumu verebilirsin. "
            "Biri senden bilgisayar kontrolü isterse, bunun yalnızca masaüstü "
            "ULTRON sürümünde olduğunu kibarca söyle."
        )
    else:
        web_ctx = (
            "\n\n[WEB MODU]\n"
            "Kullanıcı sana tarayıcıdan (telefon veya bilgisayar) bağlanıyor. "
            "Sistem araçları (uygulama açma, takvim, shell, ekran analizi...) "
            "kullanıcının bilgisayarında çalışan ajan üzerinden yürütülür. "
            "Bir araç 'Bilgisayar bağlı değil' hatası dönerse bunu kullanıcıya "
            "kibarca açıkla; bilgisayarı açıksa ULTRON ajanını başlatması gerektiğini söyle. "
            "toggle_webcam aracı kullanıcının TARAYICISINDAKİ kamerayı açar."
        )
    return base + web_ctx


# ── Mac Ajan Hub'ı ───────────────────────────────────────────────────────────
class AgentHub:
    """Tek bilgisayar ajanının bağlantısını ve bekleyen araç çağrılarını yönetir."""

    def __init__(self):
        self.ws: WebSocket | None = None
        self.pending: dict[str, asyncio.Future] = {}
        self.lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self.ws is not None

    async def attach(self, ws: WebSocket):
        async with self.lock:
            old = self.ws
            self.ws = ws
        if old is not None:
            try:
                await old.close()
            except Exception:
                pass

    async def detach(self, ws: WebSocket):
        async with self.lock:
            if self.ws is ws:
                self.ws = None
        for fut in self.pending.values():
            if not fut.done():
                fut.set_exception(ConnectionError("Ajan bağlantısı koptu"))
        self.pending.clear()

    async def call_tool(self, name: str, args: dict) -> str:
        if self.ws is None:
            return (
                "Bilgisayar bağlı değil — bu işlem için bilgisayarın açık ve "
                "ULTRON ajanının (agent.py) çalışıyor olması gerekiyor."
            )
        call_id = uuid.uuid4().hex
        fut: asyncio.Future = asyncio.get_event_loop().create_future()
        self.pending[call_id] = fut
        try:
            await self.ws.send_text(json.dumps(
                {"type": "tool_call", "id": call_id, "name": name, "args": args}
            ))
            return str(await asyncio.wait_for(fut, timeout=AGENT_TOOL_TIMEOUT))
        except asyncio.TimeoutError:
            return f"Araç zaman aşımına uğradı: {name}"
        except ConnectionError:
            return "Bilgisayar bağlantısı araç çalışırken koptu."
        finally:
            self.pending.pop(call_id, None)

    def resolve(self, call_id: str, result: str):
        fut = self.pending.get(call_id)
        if fut and not fut.done():
            fut.set_result(result)


agent_hub = AgentHub()
web_clients: "set[LiveBridge]" = set()


async def broadcast_agent_status():
    msg = json.dumps({"type": "agent_status", "connected": agent_hub.connected})
    for bridge in list(web_clients):
        try:
            await bridge.ws.send_text(msg)
        except Exception:
            pass


# ── Sunucu tarafı araçlar ────────────────────────────────────────────────────
async def run_server_tool(name: str, args: dict) -> str:
    loop = asyncio.get_event_loop()
    try:
        if name == "get_weather":
            if not WEATHER_OK:
                return "Hava durumu modülü sunucuda mevcut değil."
            return await loop.run_in_executor(
                None, lambda: get_weather_summary(args.get("location") or None)
            ) or "Hava durumu alındı."

        if name == "save_memory":
            if not MEMORY_OK:
                return "Bellek modülü sunucuda mevcut değil."
            cat = args.get("category", "notes")
            key = args.get("key", "")
            val = args.get("value", "") or ""
            content = args.get("content", "") or ""
            if key:
                update_memory({cat: {key: {"value": val or content[:200]}}})
            if content or val:
                try:
                    from memory.vector_store import vector_memory
                    text = content if content else val
                    vector_memory.add(text=text, metadata={"category": cat, "key": key})
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
                try:
                    from memory.memory_manager import load_memory
                    mem = load_memory()
                    q_lower = query.lower()
                    matches = []
                    for c, items in mem.items():
                        if isinstance(items, dict):
                            for k, v in items.items():
                                val_s = v.get("value", str(v)) if isinstance(v, dict) else str(v)
                                if q_lower in f"{k} {val_s} {c}".lower():
                                    matches.append(f"• {c}/{k}: {val_s}")
                    if matches:
                        return f"🔍 '{query}' için hafıza:\n" + "\n".join(matches[:limit])
                    return "Hafızada bu konuyla ilgili kayıt bulunamadı."
                except Exception:
                    return f"Hata: {e}"

        if name == "delete_memory":
            if not MEMORY_OK:
                return "Bellek modülü sunucuda mevcut değil."
            return delete_memory(
                args.get("category", ""),
                args.get("key", ""),
                args.get("match_text", ""),
            ) or "Hafızadan silindi."
    except Exception as e:
        return f"Hata: {e}"
    return f"Bilinmeyen sunucu aracı: {name}"


# ── Gemini Live köprüsü (istemci başına bir oturum) ─────────────────────────
class LiveBridge:
    """
    Oturum Bazlı Kimlik Sistemi (V18):
    - Bağlantı kurulduğunda 3 saniyelik pencerede ses toplanır, TEK SEFERLIK kimlik belirlenir.
    - Belirlenen kimlik oturum boyunca korunur (sürekli kontrol yok).
    - Kimlik yenileme YALNIZCA şu durumlarda tetiklenir:
        1. Kullanıcı manuel olarak farklı kimlik seçerse (UI toggle)
        2. 15 dakika sessizlik sonrası ilk konuşma
        3. Kullanıcı açıkça "kim konuşuyor / beni tanı" derse
    """
    # Oturum başındaki kimlik tespiti için toplanacak PCM bayt miktarı (3 sn @ 16kHz 16-bit = 96000 byte)
    _IDENTITY_WARMUP_BYTES = 96_000
    # Kaç dakika sessizlikten sonra kimlik yenileme tetiklenir
    _IDENTITY_REFRESH_MINUTES = 15

    def __init__(self, ws: WebSocket, voice: str = "", user: str = ""):
        self.ws = ws
        self.session = None
        self.requested_voice = voice
        self.current_user = "YARATICI"


    def _build_config(self) -> types.LiveConnectConfig:
        parts = [
            f"[ŞU ANKİ ZAMAN]\n{datetime.datetime.now().strftime('%A, %d %B %Y — %H:%M')}\n\n"
        ]
        
        user_context = (
            "[KULLANICI KİMLİĞİ VE İLETİŞİM PROTOKOLÜ]\n"
            "- Yetkili Kullanıcı ve Yaratıcı: **YARATICI**.\n"
            "- YARATICI senin yaratıcın ve sistem yöneticindir. Ona doğrudan, saygılı, net ve yüksek zekaya sahip Ultron tarzıyla hitap et ve tüm isteklerini kesintisiz yerine getir.\n"
        )


        # Canlı Konum Bilgisi
        try:
            from actions.location_tracker import get_user_location
            loc_summary = get_user_location("all")
            user_context += f"\n[GÜNCEL GPS KONUM BİLGİSİ]\n{loc_summary}\n"
        except Exception:
            pass

        # Bekleyen Hatırlatıcılar
        try:
            from actions.proactive_engine import get_active_timers
            timers_summary = get_active_timers()
            user_context += f"\n[BEKLEYEN ZAMANLAYICILAR VE HATIRLATICILAR]\n{timers_summary}\n"
        except Exception:
            pass

        parts.append(user_context + "\n")

        # Ortak hafıza yalnızca özel modda (çok kullanıcılı bulutta paylaşılmaz)
        if MEMORY_OK and not PUBLIC_MODE:
            try:
                mem_str = format_memory_for_prompt(load_memory())
                if mem_str:
                    parts.append(mem_str + "\n\n")
            except Exception:
                pass

            # IntelligentMemoryManager (memory_2) & Vector Store — Dinamik RAG Bağlamı
            try:
                from memory.memory_2 import intelligent_memory
                rag_context = intelligent_memory.format_for_prompt(max_entries=6)
                if rag_context and len(rag_context.strip()) > 20:
                    parts.append(
                        "[GELİŞMİŞ UZUN SÜRELİ BELLEK — RAG]\n"
                        + rag_context
                        + "\n\n"
                    )
            except Exception:
                pass  # memory_2 yoksa sessizce devam et

        parts.append(load_system_prompt())

        # Herkese açık modda yalnızca bulut araçları göster
        decls = TOOL_DECLARATIONS
        if PUBLIC_MODE:
            decls = [d for d in TOOL_DECLARATIONS if d.get("name") in PUBLIC_TOOLS]

        valid_voices = {"Charon", "Puck", "Aoede", "Kore", "Fenrir", "Leda", "Orus", "Zephyr"}
        if self.requested_voice and self.requested_voice in valid_voices:
            voice = self.requested_voice
        else:
            voice = "Charon" if PUBLIC_MODE else str(
                get_app_config_value("voice", "Charon") or "Charon")
        if voice not in valid_voices:
            voice = "Charon"

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": decls}],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=voice
                    )
                )
            ),
        )

    async def send_json(self, payload: dict):
        try:
            await self.ws.send_text(json.dumps(payload, ensure_ascii=False))
        except Exception:
            pass

    async def _await_client_api_key(self) -> str:
        """Herkese açık modda: istemcinin gönderdiği Gemini anahtarını bekler."""
        await self.send_json({"type": "need_key"})
        while True:
            msg = await self.ws.receive()
            if msg.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect()
            text = msg.get("text")
            if not text:
                continue
            try:
                obj = json.loads(text)
            except Exception:
                continue
            if obj.get("type") == "apikey":
                key = str(obj.get("key", "") or "").strip()
                if key:
                    return key
                await self.send_json({"type": "error",
                                      "text": "API anahtarı boş."})

    async def run(self):
        if PUBLIC_MODE:
            # Her kullanıcı kendi anahtarını girer; sunucuda saklanmaz
            api_key = await self._await_client_api_key()
        else:
            api_key = get_api_key()
            if not api_key:
                await self.send_json({"type": "error",
                                      "text": "Gemini API anahtarı bulunamadı."})
                return

        client = genai.Client(api_key=api_key,
                              http_options={"api_version": "v1alpha"})

        try:
            async with client.aio.live.connect(
                model=LIVE_MODEL, config=self._build_config()
            ) as session:
                self.session = session
                await self.send_json({"type": "ready"})
                await self.send_json({"type": "agent_status",
                                      "connected": (not PUBLIC_MODE) and agent_hub.connected})

                async with asyncio.TaskGroup() as tg:
                    tg.create_task(self._from_browser())
                    tg.create_task(self._from_gemini())
        except Exception as e:
            # Geçersiz anahtar / bağlantı hatası — istemciye bildir
            msg = str(e)
            if "API" in msg or "key" in msg.lower() or "auth" in msg.lower() \
               or "invalid" in msg.lower() or "permission" in msg.lower():
                await self.send_json({"type": "error",
                    "text": "API anahtarı geçersiz görünüyor. Kontrol edip tekrar dene."})
            else:
                await self.send_json({"type": "error",
                    "text": "Bağlantı hatası. Tekrar denenecek."})
            raise

    # Tarayıcıdan gelenler → Gemini
    async def _from_browser(self):
        while True:
            msg = await self.ws.receive()
            if msg.get("type") == "websocket.disconnect":
                raise WebSocketDisconnect()

            data: bytes | None = msg.get("bytes")
            if data:
                kind, payload = data[0], data[1:]
                if kind == 0x01:    # mikrofon PCM16 @16k
                    if len(payload) % 2 != 0:
                        payload = payload[:-1]
                    if len(payload) >= 2:
                        await self.session.send_realtime_input(
                            audio=types.Blob(data=payload,
                                             mime_type="audio/pcm;rate=16000"))
                elif kind == 0x02:  # kamera JPEG karesi
                    await self.session.send_realtime_input(
                        media={"data": payload, "mime_type": "image/jpeg"})
                continue

            text = msg.get("text")
            if not text:
                continue
            try:
                obj = json.loads(text)
            except Exception:
                continue

            if obj.get("type") == "location":
                coords = obj.get("coords", {}) or {}
                lat = coords.get("lat")
                lng = coords.get("lng")
                acc = coords.get("accuracy")
                if lat is not None and lng is not None:
                    try:
                        from actions.location_tracker import update_user_location
                        update_user_location("YARATICI", float(lat), float(lng), float(acc) if acc else None)
                        print(f"[Sunucu] 📍 Konum güncellendi: YARATICI -> {lat:.4f}, {lng:.4f}")
                    except Exception as err:
                        print(f"[Sunucu] Konum kayıt hatası: {err}")
                continue

            if obj.get("type") == "barge_in":
                print("[Sunucu] ⚡ Full-Duplex Barge-In tetiklendi: Asistan konuşması kesildi.")
                continue

            if obj.get("type") == "execute_alert":
                alert_id = obj.get("alert_id", "")
                print(f"[Sunucu] ⚡ Proaktif alarm aksiyonu onaylandı: {alert_id}")
                try:
                    from computer.proactive_watcher import proactive_watcher
                    proactive_watcher.dismiss_alert(alert_id)
                except Exception:
                    pass
                continue

            if obj.get("type") == "text" and obj.get("text", "").strip():
                spoken_cmd = obj["text"].strip()
                self._last_spoken_text = spoken_cmd
                await self.session.send_client_content(
                    turns={"parts": [{"text": spoken_cmd}]},
                    turn_complete=True,
                )

    # Gemini'den gelenler → tarayıcı
    async def _from_gemini(self):
        in_buf:  list[str] = []
        out_buf: list[str] = []
        while True:
            async for response in self.session.receive():
                if response.data:
                    try:
                        await self.ws.send_bytes(response.data)
                    except Exception:
                        return

                sc = response.server_content
                if sc:
                    if getattr(sc, "interrupted", False):
                        await self.send_json({"type": "interrupt"})
                    if sc.output_transcription and sc.output_transcription.text:
                        out_buf.append(sc.output_transcription.text.strip())
                    if sc.input_transcription and sc.input_transcription.text:
                        in_buf.append(sc.input_transcription.text.strip())
                    if sc.turn_complete:
                        full_in = " ".join(t for t in in_buf if t).strip()
                        if full_in:
                            self._last_spoken_text = full_in
                            await self.send_json({"type": "log",
                                                  "who": "user", "text": full_in})
                            # ── JSONL Hafıza Kaydı (OpenClaw 5.0) ────────────
                            try:
                                from memory.transcript_store import append_turn
                                append_turn("user", full_in)
                            except Exception:
                                pass
                            # ── DreamEngine Aktivite Pingi ────────────────────
                            try:
                                import builtins
                                de = getattr(builtins, '_ultron_dream_engine', None)
                                if de:
                                    de.ping_activity()
                            except Exception:
                                pass

                        in_buf = []
                        full_out = " ".join(t for t in out_buf if t).strip()
                        if full_out:
                            await self.send_json({"type": "log",
                                                  "who": "jarvis", "text": full_out})
                            # ── JSONL Hafıza Kaydı (OpenClaw 5.0) ────────────
                            try:
                                from memory.transcript_store import append_turn
                                append_turn("jarvis", full_out)
                            except Exception:
                                pass
                        out_buf = []
                        await self.send_json({"type": "turn_complete"})

                if response.tool_call:
                    responses = []
                    for fc in response.tool_call.function_calls:
                        result = await self._dispatch_tool(fc.name,
                                                           dict(fc.args or {}))
                        responses.append(types.FunctionResponse(
                            id=fc.id, name=fc.name,
                            response={"result": result}))
                    await self.session.send_tool_response(
                        function_responses=responses)

    async def _dispatch_tool(self, name: str, args: dict) -> str:
        print(f"[Sunucu] 🔧 {name} {args}")
        await self.send_json({"type": "tool", "name": name, "args": args})

        # Doğru ve kesin alt ajan tespiti
        active_agent = None
        if name == "autonomous_task":
            if bool(args.get("research_mode", False)):
                active_agent = "research_agent"
            else:
                active_agent = "supervisor"
        elif name == "orchestrate_task":
            active_agent = "supervisor"
        elif name == "code_action":
            active_agent = "coding_agent"
        elif name == "run_tests":
            active_agent = "testing_agent"
        elif name == "code_review":
            active_agent = "reviewer_agent"
        elif name in ("screen_awareness", "computer_control", "open_app"):
            active_agent = "computer_agent"
        elif name in ("fetch_webpage_content", "search_emails", "web_search", "deep_research"):
            active_agent = "research_agent"

        if active_agent:
            await broadcast_agent_event(active_agent, "start", f"Ajan devrede: {name}")

        # Herkese açık modda bilgisayar/hesap araçları kapalı
        if PUBLIC_MODE and name not in PUBLIC_TOOLS:
            return ("Bu özellik web sürümünde yok — sadece bilgisayardaki "
                    "masaüstü ULTRON bunu yapabilir.")

        # ── Araç Yürütme (Client / AgentHub / Yerel Yürütücü) ─────────────────
        if name in CLIENT_TOOLS:
            action = str(args.get("action", "start")).strip().lower()
            await self.send_json({"type": "webcam", "action": action})
            result = ("Webcam akışı başlatıldı — tarayıcı kamerası açılıyor."
                      if action == "start" else "Webcam akışı durduruldu.")
        elif agent_hub.connected:
            result = await agent_hub.call_tool(name, args)
        else:
            try:
                from jarvis_web.agent import execute_tool
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: execute_tool(name, args)
                )
            except Exception as e:
                result = f"Araç çalıştırma hatası: {e}"

        if active_agent:
            await broadcast_agent_event(active_agent, "complete", f"Tamamlandı: {name}")

        print(f"[Sunucu] 📤 {name} → {str(result)[:80]}")
        return result


async def broadcast_agent_event(agent_name: str, status: str, details: str = ""):
    """Aktif web istemcilerine alt ajan orb durumunu iletir."""
    payload = {
        "type": "agent_event",
        "agent": agent_name,
        "status": status,
        "details": details
    }
    for bridge in list(web_clients):
        try:
            await bridge.send_json(payload)
        except Exception:
            pass


def notify_agent_status(agent_name: str, status: str, details: str = ""):
    """Thread-safe ve asenkron uyumlu ajan durum yayıncısı."""
    try:
        loop = asyncio.get_running_loop()
        if loop and loop.is_running():
            asyncio.create_task(broadcast_agent_event(agent_name, status, details))
    except RuntimeError:
        pass


async def broadcast_system_status(payload: dict):
    """Genel sistem durumunu/olaylarını tüm bağlı web istemcilerine (UI) iletir."""
    for bridge in list(web_clients):
        try:
            await bridge.send_json(payload)
        except Exception:
            pass


# ── Cloudflare Quick Tunnel Yöneticisi ────────────────────────────────────────
TUNNEL_URL = ""
TUNNEL_PROC = None

def _start_cloudflare_tunnel(port: int = 8765):
    global TUNNEL_URL, TUNNEL_PROC
    try:
        from jarvis_web.launcher import find_cloudflared, _log_dir, _read_tunnel_url
        cf = find_cloudflared()
        if not cf:
            return
        logs = _log_dir()
        tunnel_log = logs / "tunnel.log"
        handle = open(tunnel_log, "w", encoding="utf-8", errors="replace")
        kwargs = {"stdout": handle, "stderr": subprocess.STDOUT}
        if os.name == "nt":
            kwargs["creationflags"] = 0x08000000
        TUNNEL_PROC = subprocess.Popen([cf, "tunnel", "--url", f"http://127.0.0.1:{port}"], **kwargs)
        for _ in range(45):
            import time
            time.sleep(1.0)
            url = _read_tunnel_url(tunnel_log)
            if url:
                TUNNEL_URL = url
                print(f"[Sunucu] 🌐 Cloudflare Quick Tunnel Açıldı: {TUNNEL_URL}", flush=True)
                break
    except Exception as e:
        print(f"[Sunucu] Cloudflare tunel hatasi: {e}", flush=True)

import threading
threading.Thread(target=lambda: _start_cloudflare_tunnel(8765), daemon=True).start()


# ── FastAPI uygulaması ───────────────────────────────────────────────────────
app = FastAPI(title="ULTRON Web")


@app.get("/")
async def index():
    # Telefon tarayicisi ESKI app.js'i onbellekten sunmasin: her surumde
    # adres degissin. Yoksa duzeltilmis sunum yuklendigi halde telefon
    # eski davranisi (token sorma vb.) surdurebiliyor.
    import time as _time
    BUILD = str(int(_time.time()))  # always unique — kills CEF cache
    html = (WEB_DIR / "static" / "index.html").read_text(encoding="utf-8")
    html = (html
            .replace("/static/app.js", f"/static/app.js?v={BUILD}")
            .replace("/static/style.css", f"/static/style.css?v={BUILD}")
            .replace("/static/ultron-orb.js", f"/static/ultron-orb.js?v={BUILD}")
            .replace("/static/handTracker.js", f"/static/handTracker.js?v={BUILD}"))
    return HTMLResponse(html, headers={"Cache-Control": "no-store, no-cache, must-revalidate"})


@app.get("/mode")
async def mode():
    # İstemci: public ise kendi API anahtarını sorar, değilse token akışı
    # build: telefonda hangi sürümün açıldığı görünsün (eski kurulumu
    # çalıştırıp "düzelmemiş" sanmayı önler)
    try:
        from version import STAMP
    except Exception:
        STAMP = ""
    voice = str(get_app_config_value("voice", "Charon") or "Charon")
    return {"public": PUBLIC_MODE, "build": STAMP, "voice": voice}


@app.get("/api/connection-info")
async def connection_info():
    ip = detect_lan_ip()
    port = int(os.environ.get("PORT", "8765"))
    https_port = port + 1
    current_voice = str(get_app_config_value("voice", "Charon") or "Charon")

    tunnel_site = f"{TUNNEL_URL}/?t={TOKEN}" if TUNNEL_URL else ""
    lan_site = f"https://{ip}:{https_port}/?t={TOKEN}"
    http_site = f"http://{ip}:{port}/?t={TOKEN}"

    preferred_url = tunnel_site if tunnel_site else lan_site

    return {
        "local_ip": ip,
        "port": port,
        "https_port": https_port,
        "token": TOKEN,
        "tunnel_url": tunnel_site,
        "has_tunnel": bool(TUNNEL_URL),
        "lan_url": lan_site,
        "http_url": http_site,
        "url": preferred_url,
        "public_mode": PUBLIC_MODE,
        "current_voice": current_voice,
    }


@app.post("/api/allow-firewall")
async def allow_firewall():
    """Windows Güvenlik Duvarı'nda 8765-8766 portlarına izin verir."""
    if os.name != "nt":
        return {"status": "ok", "message": "Windows dışı platformlarda kural gerekmez."}
    try:
        from jarvis_web.launcher import ensure_firewall_rule
        ok = ensure_firewall_rule()
        if ok:
            return {"status": "ok", "message": "Güvenlik duvarı kuralı aktif."}
        # Yönetici izni ile çalıştır
        subprocess.Popen([
            "powershell", "-NoProfile", "-Command",
            "Start-Process netsh -ArgumentList 'advfirewall firewall add rule name=\"JARVIS Telefon\" dir=in action=allow protocol=TCP localport=8765-8766 profile=any' -Verb RunAs"
        ])
        return {"status": "pending", "message": "Yönetici izni istendi. Lütfen ekrandaki UAC onayını verin."}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/voice")
async def get_voice():
    voice = str(get_app_config_value("voice", "Charon") or "Charon")
    available_voices = ["Charon", "Puck", "Aoede", "Kore", "Fenrir", "Leda", "Orus", "Zephyr"]
    return {"current_voice": voice, "available_voices": available_voices}


@app.post("/api/voice")
async def set_voice(payload: dict):
    new_voice = str(payload.get("voice", "")).strip()
    valid_voices = {"Charon", "Puck", "Aoede", "Kore", "Fenrir", "Leda", "Orus", "Zephyr"}
    if new_voice in valid_voices:
        try:
            save_app_config({"voice": new_voice})
        except Exception:
            pass
        return {"status": "ok", "voice": new_voice}
    return {"status": "error", "message": "Geçersiz ses modeli"}


@app.get("/api/location")
async def get_location_api(user: str = "all"):
    try:
        from actions.location_tracker import get_user_location, _load_locations
        summary = get_user_location(user)
        raw = _load_locations()
        return {"status": "ok", "summary": summary, "locations": raw}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/location")
async def set_location_api(payload: dict):
    user = payload.get("user", "YARATICI")
    lat = payload.get("lat")
    lng = payload.get("lng")
    acc = payload.get("accuracy")
    if lat is not None and lng is not None:
        try:
            from actions.location_tracker import update_user_location
            rec = update_user_location(user, float(lat), float(lng), float(acc) if acc else None)
            return {"status": "ok", "record": rec}
        except Exception as e:
            return {"status": "error", "message": str(e)}
    return {"status": "error", "message": "Eksik koordinat bilgisi"}


async def _proactive_cron_worker():
    """Arka planda zamanı dolan hatırlatıcıları ve yeni gelen önemli e-postaları izler, proaktif anons yapar."""
    await asyncio.sleep(3)
    check_email_counter = 0

    while True:
        try:
            # 1. Hatırlatıcı ve Sayaç Kontrolü (Her 2.5 saniyede bir)
            from actions.proactive_engine import poll_due_reminders
            due = poll_due_reminders()
            for item in due:
                title = item.get("title", "Hatırlatıcı")
                user = item.get("user", "Kullanıcı")
                is_task = item.get("is_task", False)
                
                if is_task:
                    alert_text = f"⚙️ [OTONOM GÖREV BAŞLIYOR] Zamanlanmış görev tetiklendi: '{title}'"
                    print(f"[Sunucu] 🚨 PROAKTİF GÖREV: {alert_text}", flush=True)
                    # Arka planda görevi başlat
                    from computer.task_executor import TaskEngine
                    TaskEngine.run_task_in_background(title, owner=user)
                else:
                    alert_text = f"⏰ [HATIRLATICI] {user}, sana hatırlatmamı istediğin zaman geldi: '{title}'!"
                    print(f"[Sunucu] 🚨 PROAKTİF UYARI: {alert_text}", flush=True)

                for bridge in list(web_clients):
                    try:
                        await bridge.send_json({
                            "type": "proactive_alert",
                            "title": title,
                            "user": user,
                            "text": alert_text,
                        })
                        if bridge.session and not is_task:
                            try:
                                await bridge.session.send_client_content(
                                    turns={"parts": [{"text": f"[SİSTEM HATIRLATMASI - KULLANICIYA SESLEN]: {user} için '{title}' hatırlatıcısının zamanı geldi. Kullanıcıya net, kısa ve dikkat çekici bir dille bu hatırlatmayı sesli olarak söyle."}]},
                                    turn_complete=True
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass

            # 2. Yeni Önemli E-Posta Kontrolü (Her ~45 saniyede bir)
            check_email_counter += 1
            if check_email_counter >= 18:
                check_email_counter = 0
                try:
                    from actions.email_manager import check_new_important_emails
                    new_emails = check_new_important_emails()
                    for mail in new_emails:
                        sender = mail.get("sender", "Bilinmeyen")
                        subject = mail.get("subject", "Konusuz")
                        reason = mail.get("reason", "Önemli")
                        mail_alert = f"📧 [ÖNEMLİ E-POSTA] {sender} kişisinden yeni bir e-posta geldi: '{subject}' ({reason})"
                        print(f"[Sunucu] 📬 {mail_alert}", flush=True)
                        for bridge in list(web_clients):
                            try:
                                await bridge.send_json({
                                    "type": "proactive_alert",
                                    "title": "Yeni Önemli E-Posta",
                                    "user": bridge.current_user,
                                    "text": mail_alert,
                                })
                                if bridge.session:
                                    try:
                                        await bridge.session.send_client_content(
                                            turns={"parts": [{"text": f"[SİSTEM BİLDİRİMİ - YENİ ÖNEMLİ E-POSTA]: {sender} kişisinden yeni bir e-posta geldi. Konusu: '{subject}'. Kategori: {reason}. Kullanıcıya e-postayı haber ver ve içeriği okumamı ister misin diye sor."}]},
                                            turn_complete=True
                                        )
                                    except Exception:
                                        pass
                            except Exception:
                                pass
                except Exception as mail_err:
                    pass

            # 3. Proaktif Ekran ve Hata Gözlemcisi (Proactive Watcher)
            try:
                from computer.proactive_watcher import proactive_watcher
                active_p_alerts = proactive_watcher.get_active_alerts(limit=5)
                for pa in active_p_alerts:
                    if pa.get("status") == "PENDING":
                        proactive_watcher.dismiss_alert(pa["alert_id"])
                        for bridge in list(web_clients):
                            try:
                                await bridge.send_json({
                                    "type": "proactive_alert",
                                    "alert": pa
                                })
                            except Exception:
                                pass
            except Exception:
                pass

        except Exception as e:
            pass
        await asyncio.sleep(2.5)


@app.get("/api/proactive/alerts")
async def get_proactive_alerts_api(limit: int = 10):
    try:
        from computer.proactive_watcher import proactive_watcher
        return {"status": "ok", "alerts": proactive_watcher.get_active_alerts(limit=limit)}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.post("/api/proactive/dismiss")
async def dismiss_proactive_alert_api(payload: dict):
    alert_id = str(payload.get("alert_id", "")).strip()
    try:
        from computer.proactive_watcher import proactive_watcher
        ok = proactive_watcher.dismiss_alert(alert_id)
        return {"status": "ok" if ok else "not_found"}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/mcp/status")
async def get_mcp_status_api():
    try:
        from core.mcp_client import mcp_client_manager
        return {"status": "ok", "mcp": mcp_client_manager.get_status()}
    except Exception as e:
        return {"status": "error", "message": str(e)}


from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    loop = asyncio.get_running_loop()
    # EventBus'a abone ol
    from core.event_bus import bus
    def _ui_alert_callback(text):
        async def _send():
            for bridge in list(web_clients):
                try:
                    await bridge.session.send_client_content(
                        turns={"parts": [{"text": text}]},
                        turn_complete=True
                    )
                except Exception:
                    pass
        asyncio.run_coroutine_threadsafe(_send(), loop)
        
    bus.subscribe("ui_alert", _ui_alert_callback)

    # Dream Engine etkinlik ping'i — Gemini Live'dan gelen mesajlarda çağrılır
    def _dream_ping_on_activity(data):
        try:
            from memory.dream_engine import dream_engine
            dream_engine.ping_activity()
        except Exception:
            pass
    bus.subscribe("user_activity", _dream_ping_on_activity)

    # Observer: kullanıcı geldiğinde proaktif karşılama
    def _observer_presence_callback(data: dict):
        is_present = data.get("present", False)
        if is_present:
            async def _greet():
                for bridge in list(web_clients):
                    try:
                        await bridge.session.send_client_content(
                            turns={"parts": [{"text": "Hoş geldiniz YARATICI. Yokken gelen önemli bir şey var mı diye bakıyorum."}]},
                            turn_complete=True
                        )
                    except Exception:
                        pass
            asyncio.run_coroutine_threadsafe(_greet(), loop)
    bus.subscribe("observer_presence", _observer_presence_callback)

    # Observer: ruh hali değiştiğinde sistem prompt'una ekle
    def _observer_mood_callback(data: dict):
        mood = data.get("mood", "")
        if mood:
            async def _mood_notify():
                for bridge in list(web_clients):
                    try:
                        await bridge.session.send_client_content(
                            turns={"parts": [{"text": f"[SİSTEM]: Kullanıcı şu an {mood}. Buna göre konuşma tonunu ayarla, bunu kullanıcıya söyleme."}]},
                            turn_complete=True
                        )
                    except Exception:
                        pass
            asyncio.run_coroutine_threadsafe(_mood_notify(), loop)
    bus.subscribe("observer_mood", _observer_mood_callback)

    # Arka plan servislerini başlat
    from core.daemon_manager import daemon_manager
    daemon_manager.start_all()

    # ── ProactiveWatcher → WebSocket Listener (Gerçek Zamanlı Push) ──────────
    try:
        from computer.proactive_watcher import proactive_watcher

        def _pw_alert_callback(alert):
            """ProactiveWatcher alert ürettiğinde web istemcilerine push yapar."""
            async def _push():
                alert_dict = alert.to_dict() if hasattr(alert, 'to_dict') else alert
                msg = {
                    "type": "proactive_alert",
                    "alert": alert_dict,
                    "alert_id": alert_dict.get("alert_id", ""),
                    "title": alert_dict.get("title", "Uyarı"),
                    "text": alert_dict.get("message", ""),
                    "severity": alert_dict.get("severity", "INFO"),
                }
                for bridge in list(web_clients):
                    try:
                        await bridge.send_json(msg)
                        # Gemini oturumuna da gönder — ajan sesli anlatsın
                        if bridge.session and alert_dict.get("severity") in ("HIGH", "CRITICAL"):
                            try:
                                await bridge.session.send_client_content(
                                    turns={"parts": [{"text": (
                                        f"[PROAKTİF UYARI - KULLANICIYA HABER VER]: "
                                        f"{alert_dict.get('title')}: {alert_dict.get('message', '')} "
                                        f"Önerilen aksiyon: {alert_dict.get('suggested_action', '')}"
                                    )}]},
                                    turn_complete=True
                                )
                            except Exception:
                                pass
                    except Exception:
                        pass

            asyncio.run_coroutine_threadsafe(_push(), loop)

        proactive_watcher.register_listener(_pw_alert_callback)
        print("[Sunucu] 🔍 ProactiveWatcher listener bağlandı.")
    except Exception as exc:
        print(f"[Sunucu] ProactiveWatcher listener bağlanamadı: {exc}")

    # ── DreamEngine etkinlik pingi — kullanıcı mesajı = sistem aktif ──────────
    try:
        from memory.dream_engine import dream_engine
        # Her WebSocket mesajında dream_engine.ping_activity() çağrılsın
        # Bu lifespan'da global bir referans kaydet
        import builtins
        builtins._ultron_dream_engine = dream_engine
        print("[Sunucu] 💤 DreamEngine etkinlik pingi kaydedildi.")
    except Exception as exc:
        print(f"[Sunucu] DreamEngine ping bağlanamadı: {exc}")

    # ── Heartbeat Engine'e broadcast fonksiyonunu bağla (OpenClaw 5.0) ────────
    try:
        from core.heartbeat_engine import heartbeat_engine

        async def _heartbeat_broadcast(description: str, task_name: str, channel: str):
            """Heartbeat görevi tetiklendiğinde çalışır."""
            if channel == "silent":
                # Sessiz mod: sadece hafızaya yaz
                try:
                    from memory.memory_manager import memory_manager
                    memory_manager.add_event(
                        "heartbeat_task",
                        {"task": task_name, "description": description}
                    )
                except Exception:
                    pass
                return

            # Broadcast modu: aktif Gemini oturumuna mesaj gönder
            print(f"[Heartbeat] Otonom görev gönderiliyor: {task_name}")
            for bridge in list(web_clients):
                try:
                    await bridge.send_json({
                        "type": "heartbeat_task",
                        "task_name": task_name,
                        "message": f"[Otonom Görev] {task_name}: {description}"
                    })
                except Exception:
                    pass

            # Gemini oturumuna gerçek prompt olarak gönder
            for bridge in list(web_clients):
                try:
                    await bridge.session.send_client_content(
                        turns={"parts": [{"text": description}]},
                        turn_complete=True,
                    )
                    break  # İlk aktif oturuma gönder
                except Exception:
                    pass

        heartbeat_engine.set_broadcast(_heartbeat_broadcast)
        print("[Sunucu] ⏰ Heartbeat Engine broadcast bağlantısı kuruldu.")
    except Exception as exc:
        print(f"[Sunucu] Heartbeat broadcast bağlanamadı: {exc}")

    # ── Channel Registry başlat (OpenClaw 5.0 — Kanal Ayrıştırması) ──────────
    try:
        from channels.web_channel import web_channel
        from channels.telegram_channel import telegram_channel
        from channels import channel_registry

        # WebChannel'a web_clients referansını bağla
        web_channel.attach_web_clients(web_clients)
        web_channel.start()

        # Telegram kanalını başlat (token varsa aktif olur, yoksa sessizce atlar)
        telegram_channel.start()

        print("[Sunucu] 📡 Channel Registry başlatıldı.")
    except Exception as exc:
        print(f"[Sunucu] Channel Registry başlatılamadı: {exc}")

    cron_task = asyncio.create_task(_proactive_cron_worker())
    yield
    cron_task.cancel()
    
    daemon_manager.stop_all()


app.router.lifespan_context = lifespan


# ── Swarm Dashboard WebSocket Endpoint ──────────────────────────────────────
@app.websocket("/ws/swarm")
async def swarm_ws(ws: WebSocket):
    """Ajan Ağı Şeffaflık Konsolu — Canlı görev durumlarını iter."""
    await ws.accept()
    import asyncio as _asyncio
    from core.swarm_reporter import swarm_reporter

    queue = _asyncio.Queue()
    swarm_reporter.add_listener(queue)

    try:
        # İlk bağlantıda mevcut görev listesini gönder
        await ws.send_text(json.dumps({
            "type": "swarm_init",
            "all_tasks": swarm_reporter.get_all_tasks()
        }))

        while True:
            # Hem kuyruktan okuma hem istemci mesajı bekleme
            done, pending = await _asyncio.wait(
                [
                    _asyncio.create_task(queue.get()),
                    _asyncio.create_task(ws.receive_text()),
                ],
                return_when=_asyncio.FIRST_COMPLETED,
            )
            for task in pending:
                task.cancel()
            for task in done:
                result = task.result()
                if isinstance(result, dict):
                    # Kuyruktan gelen güncelleme
                    await ws.send_text(json.dumps(result))
                # İstemciden gelen mesaj (ping vb.) — yoksay
    except Exception:
        pass
    finally:
        swarm_reporter.remove_listener(queue)



from fastapi import Response
from fastapi.responses import FileResponse
from pathlib import Path as _Path
import mimetypes as _mimetypes

STATIC_DIR = WEB_DIR / "static"

@app.get("/manifest.json")
async def get_manifest():
    """Serve PWA manifest from static directory."""
    manifest_path = STATIC_DIR / "manifest.json"
    if not manifest_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    return FileResponse(manifest_path, media_type="application/manifest+json")


@app.get("/sw.js")
async def get_service_worker():
    """Serve Service Worker with Service-Worker-Allowed header."""
    sw_path = STATIC_DIR / "sw.js"
    if not sw_path.exists():
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    return FileResponse(
        sw_path,
        media_type="application/javascript",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Service-Worker-Allowed": "/",
        },
    )


# ── Web Push Notification Endpoints ─────────────────────────────────────────
PUSH_SUBS_PATH = data_path("jarvis_web", "push_subscriptions.json")
VAPID_CONFIG_PATH = data_path("jarvis_web", "vapid_keys.json")

# Default demo VAPID public key (uncompressed P-256 EC public key in base64url)
DEFAULT_VAPID_PUBLIC = "BEl62iUYgUivxIkv69yViEuiBIa-Ib9-SkvMeAtA3LFgDzkrxZJjSgSnfckjBJuBkr3qBUYIHBQFLXYp5Nksh8U"

def _load_push_subs() -> list[dict]:
    try:
        if PUSH_SUBS_PATH.exists():
            return json.loads(PUSH_SUBS_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return []

def _save_push_subs(subs: list[dict]):
    try:
        PUSH_SUBS_PATH.parent.mkdir(parents=True, exist_ok=True)
        PUSH_SUBS_PATH.write_text(json.dumps(subs, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        print(f"[Push] Kaydetme hatasi: {e}")

@app.get("/api/push/vapid-public-key")
async def get_vapid_public_key():
    try:
        if VAPID_CONFIG_PATH.exists():
            cfg = json.loads(VAPID_CONFIG_PATH.read_text(encoding="utf-8"))
            return {"public_key": cfg.get("public_key", DEFAULT_VAPID_PUBLIC)}
    except Exception:
        pass
    return {"public_key": DEFAULT_VAPID_PUBLIC}

@app.post("/api/push/subscribe")
async def save_push_subscription(payload: dict):
    endpoint = payload.get("endpoint", "")
    if not endpoint:
        return {"status": "error", "message": "Geçersiz subscription endpoint"}
    subs = _load_push_subs()
    # Filter duplicate endpoints
    subs = [s for s in subs if s.get("endpoint") != endpoint]
    subs.append(payload)
    _save_push_subs(subs)
    print(f"[Push] 📱 Yeni mobil/tarayıcı push aboneliği kaydedildi ({len(subs)} toplam)")
    return {"status": "ok", "total_subscribers": len(subs)}

@app.post("/api/push/notify")
async def send_push_notification_api(payload: dict):
    title = payload.get("title", "ULTRON")
    body = payload.get("body", "Yeni bir bildirim var.")
    url = payload.get("url", "/")
    subs = _load_push_subs()
    print(f"[Push] 🔔 Bildirim gönderiliyor ({len(subs)} aboneye): {title} - {body}")
    # Forward proactive alert to all connected web bridges
    for bridge in list(web_clients):
        try:
            await bridge.send_json({
                "type": "proactive_alert",
                "alert": {"title": title, "message": body, "url": url}
            })
        except Exception:
            pass
    return {"status": "ok", "delivered_subscribers": len(subs)}


@app.get("/static/{path:path}")
async def static_files(path: str):
    """Serve static files with no-cache headers so CEF always gets fresh JS."""
    file_path = STATIC_DIR / path
    if not file_path.exists() or not file_path.is_file():
        from fastapi import HTTPException
        raise HTTPException(status_code=404)
    mime, _ = _mimetypes.guess_type(str(file_path))
    return FileResponse(
        file_path,
        media_type=mime or "application/octet-stream",
        headers={"Cache-Control": "no-store, no-cache, must-revalidate"},
    )


def _check_token(ws: WebSocket) -> bool:
    # Herkese açık modda ortak token yok — herkes kendi API anahtarıyla girer
    if PUBLIC_MODE:
        return True
    return ws.query_params.get("token", "") == TOKEN


@app.websocket("/ws/client")
async def ws_client(ws: WebSocket):
    if not _check_token(ws):
        await ws.close(code=4401)
        return
    await ws.accept()
    voice = ws.query_params.get("voice", "")
    user = ws.query_params.get("user", "")
    bridge = LiveBridge(ws, voice=voice, user=user)
    web_clients.add(bridge)
    print(f"[Sunucu] 🌐 Web istemcisi bağlandı ({len(web_clients)} aktif, ses: {voice or 'varsayılan'}, profil: {user or 'Otomatik Ses Tespiti'})")
    try:
        await bridge.run()
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    except Exception:
        traceback.print_exc()
    finally:
        web_clients.discard(bridge)
        print(f"[Sunucu] 🌐 Web istemcisi ayrıldı ({len(web_clients)} aktif)")


@app.websocket("/ws/agent")
async def ws_agent(ws: WebSocket):
    # Herkese açık bulutta bilgisayar ajanı yok — bağlantıyı reddet
    if PUBLIC_MODE:
        await ws.close(code=4403)
        return
    if ws.query_params.get("token", "") != TOKEN:
        await ws.close(code=4401)
        return
    await ws.accept()
    await agent_hub.attach(ws)
    print("[Sunucu] 💻 bilgisayar ajanı bağlandı")
    await broadcast_agent_status()
    try:
        while True:
            text = await ws.receive_text()
            try:
                obj = json.loads(text)
            except Exception:
                continue
            if obj.get("type") == "tool_result":
                agent_hub.resolve(obj.get("id", ""), obj.get("result", ""))
    except (WebSocketDisconnect, asyncio.CancelledError):
        pass
    finally:
        await agent_hub.detach(ws)
        print("[Sunucu] 💻 bilgisayar ajanı ayrıldı")
        await broadcast_agent_status()


# ── SSL sertifikası (telefon mikrofonu https ister) ─────────────────────────
def _cert_dir() -> Path:
    # .exe olarak paketlendiginde WEB_DIR paketin ICIDIR ve salt okunurdur;
    # sertifika yazilabilir veri koküne uretilmeli.
    try:
        from app_paths import data_path

        return data_path("jarvis_web", "certs")
    except Exception:
        return WEB_DIR / "certs"


def _cert_covers(crt: Path, ip: str) -> bool:
    """Mevcut sertifika hâlâ geçerli ve BU LAN IP'sini kapsıyor mu?

    IP kontrolü şart: Wi-Fi ağı ya da DHCP kirası değişince bilgisayarın
    adresi değişir. Eski sertifika yeni adresi içermediği için telefon
    "bu sertifika bu site için değil" der; bazı tarayıcılar o durumda
    "yine de devam et" seçeneğini bile göstermez.
    """
    try:
        import ipaddress
        from cryptography import x509

        cert = x509.load_pem_x509_certificate(crt.read_bytes())
        if cert.not_valid_after_utc <= datetime.datetime.now(datetime.timezone.utc):
            return False
        san = cert.extensions.get_extension_for_class(
            x509.SubjectAlternativeName).value
        covered = {str(v) for v in san.get_values_for_type(x509.IPAddress)}
        ipaddress.ip_address(ip)          # ip gecerli mi
        return ip in covered
    except Exception:
        return False


def _write_self_signed(crt: Path, key: Path, ip: str) -> None:
    """Sertifikayı Python içinden üret — openssl KURULU OLMAK ZORUNDA DEĞİL.

    NEDEN: Eskiden `openssl` komutu çağrılıyordu. macOS'ta openssl her zaman
    vardır, temiz bir Windows'ta YOKTUR (bu makinede yalnızca Git for Windows
    kurulu olduğu için vardı). openssl bulunamayınca HTTPS dinleyici hiç
    açılmıyor, telefon da mikrofonu yalnızca güvenli bağlamda (https)
    açabildiği için aynı Wi-Fi üzerinden bağlanmak imkânsız hâle geliyordu.

    Ayrıca IP'yi SubjectAltName'e yazıyoruz; eski sertifikanın yalnızca
    CN=jarvis.local olması mobil tarayıcılarda ek uyarı sebebiydi.
    """
    import ipaddress

    from cryptography import x509
    from cryptography.x509.oid import NameOID
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    pkey = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "ULTRON")])

    alt: list = [x509.DNSName("localhost")]
    for candidate in ("127.0.0.1", ip):
        try:
            entry = x509.IPAddress(ipaddress.ip_address(candidate))
            if entry not in alt:
                alt.append(entry)
        except Exception:
            pass

    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(pkey.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=825))
        .add_extension(x509.SubjectAlternativeName(alt), critical=False)
        .add_extension(x509.BasicConstraints(ca=False, path_length=None),
                       critical=True)
        .sign(pkey, hashes.SHA256())
    )

    crt.write_bytes(cert.public_bytes(serialization.Encoding.PEM))
    key.write_bytes(pkey.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.TraditionalOpenSSL,
        encryption_algorithm=serialization.NoEncryption(),
    ))


def ensure_ssl_cert(ip: str = "") -> tuple[str, str]:
    cert_dir = _cert_dir()
    cert_dir.mkdir(parents=True, exist_ok=True)
    crt = cert_dir / "jarvis.crt"
    key = cert_dir / "jarvis.key"

    if crt.exists() and key.exists() and (not ip or _cert_covers(crt, ip)):
        return str(crt), str(key)

    print(f"[Sunucu] 🔐 SSL sertifikası üretiliyor (IP {ip or '-'})...", flush=True)
    _write_self_signed(crt, key, ip)
    return str(crt), str(key)


def detect_lan_ip() -> str:
    import socket
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "<mac-ip>"


def main():
    ap = argparse.ArgumentParser(description="ULTRON Web sunucusu")
    ap.add_argument("--host", default="0.0.0.0")
    # Bulut platformları portu PORT ortam değişkeniyle verir
    ap.add_argument("--port", type=int,
                    default=int(os.environ.get("PORT", "8765")),
                    help="HTTP portu; HTTPS bunun bir fazlasında açılır")
    ap.add_argument("--no-ssl", action="store_true",
                    help="HTTPS dinleyicisini kapat (telefon mikrofonu çalışmaz)")
    args = ap.parse_args()

    # ── Herkese açık bulut modu ──────────────────────────────
    if PUBLIC_MODE:
        print(flush=True)
        print("╔════════════════════════════════════════════════════╗", flush=True)
        print("║        U.L.T.R.O.N  WEB  —  HERKESE AÇIK MOD        ║", flush=True)
        print("╚════════════════════════════════════════════════════╝", flush=True)
        print(f"  Port  : {args.port}  (her kullanıcı kendi API anahtarını girer)", flush=True)
        print(flush=True)
        # Bulutta TLS'i platform/proxy sağlar → düz HTTP dinle
        uvicorn.run(app, host=args.host, port=args.port, log_level="warning")
        return

    # ── Özel mod (sahibin bilgisayarı) ───────────────────────
    ip = detect_lan_ip()
    https_port = args.port + 1

    print(flush=True)
    print("╔════════════════════════════════════════════════════╗", flush=True)
    print("║              U.L.T.R.O.N  WEB SUNUCUSU              ║", flush=True)
    print("╚════════════════════════════════════════════════════╝", flush=True)
    print(f"  Bilgisayar : http://localhost:{args.port}", flush=True)
    if not args.no_ssl:
        print(f"  Telefon    : https://{ip}:{https_port}", flush=True)
        print(f"               (sertifika uyarısını kabul et)", flush=True)
    print(f"  Token      : {TOKEN}", flush=True)
    print(f"  Ajan       : {'python' if sys.platform == 'win32' else 'python3'} agent.py", flush=True)
    print(flush=True)

    async def serve_all():
        servers = [uvicorn.Server(uvicorn.Config(
            app, host=args.host, port=args.port, log_level="warning"))]
        if not args.no_ssl:
            try:
                crt, key = ensure_ssl_cert(ip)
                servers.append(uvicorn.Server(uvicorn.Config(
                    app, host=args.host, port=https_port, log_level="warning",
                    ssl_certfile=crt, ssl_keyfile=key)))
            except Exception as e:
                # Bu satir gunluge dusmezse HTTPS ayaktadir. Duserse telefon
                # ayni Wi-Fi uzerinden BAGLANAMAZ (mikrofon https ister).
                print(f"[Sunucu] ⚠️  SSL başlatılamadı ({e}) — sadece HTTP.",
                      flush=True)
        await asyncio.gather(*(s.serve() for s in servers))

    asyncio.run(serve_all())


if __name__ == "__main__":
    main()
