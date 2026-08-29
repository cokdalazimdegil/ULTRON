"""
ULTRON Desktop HUD — Şeffaf Masaüstü Komut Arayüzü
──────────────────────────────────────────────────
Alt+Space ile ekranın üstüne şeffaf, borderless bir komut kutusu açar.
Sunucuya WebSocket üzerinden bağlanır, yanıtları HUD'da gösterir.

Bağımlılıklar: tkinter (Python built-in), keyboard (requirements.txt)
"""

from __future__ import annotations

import json
import logging
import os
import queue
import threading
import time
import tkinter as tk
from tkinter import font as tkfont
from typing import Optional

logger = logging.getLogger("ultron.computer.desktop_hud")

# Renkler (Ultron teması)
BG_COLOR      = "#080010"
BORDER_COLOR  = "#00ccff"
TEXT_COLOR    = "#ffddcc"
INPUT_BG      = "#0a0018"
ACCENT        = "#ff4422"
RESPONSE_FG   = "#00ff88"
DIM_COLOR     = "#444444"

HOTKEY        = "alt+space"
WS_TIMEOUT    = 10.0


class DesktopHUD:
    """
    Şeffaf, borderless tkinter penceresi.
    Alt+Space ile gösterilir/gizlenir.
    Komutlar WebSocket üzerinden server.py'ye gönderilir.
    """

    def __init__(self):
        self._visible = False
        self._root: Optional[tk.Tk] = None
        self._input_var: Optional[tk.StringVar] = None
        self._response_text: Optional[tk.Text] = None
        self._status_var: Optional[tk.StringVar] = None
        self._ws = None
        self._ws_thread: Optional[threading.Thread] = None
        self._msg_queue: queue.Queue = queue.Queue()
        self._hotkey_registered = False
        self._server_url = self._get_server_url()

    def _get_server_url(self) -> str:
        """Sunucu URL'sini config'ten okur."""
        try:
            from app_paths import data_path
            cfg_path = data_path("jarvis_web", "web_config.json")
            if cfg_path.exists():
                cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
                port = cfg.get("port", 8765)
                return f"ws://localhost:{port}"
        except Exception:
            pass
        return "ws://localhost:8765"

    def start(self):
        """HUD'u ayrı bir işlem (subprocess) olarak başlatır."""
        import sys
        import subprocess
        from pathlib import Path
        
        script_path = Path(__file__).resolve()
        
        # Sadece ana süreçten çağrıldığında alt süreç başlat (sonsuz döngüyü önle)
        if not hasattr(sys, "frozen") and __name__ != "__main__":
            try:
                self._process = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                logger.info("[DesktopHUD] 🖥️ Masaüstü HUD başlatıldı (Subprocess).")
            except Exception as exc:
                logger.error(f"[DesktopHUD] Subprocess başlatma hatası: {exc}")

    def stop(self):
        """HUD sürecini sonlandırır."""
        try:
            if hasattr(self, "_process") and self._process:
                self._process.terminate()
        except Exception:
            pass

    # ── Tkinter Penceresi ─────────────────────────────────────────────────────

    def _run_tk(self):
        """Tkinter event loop — ayrı thread'de çalışır."""
        try:
            self._root = tk.Tk()
            self._root.withdraw()  # Başlangıçta gizli
            self._setup_window()
            self._setup_widgets()
            # Mesaj kuyruğunu periyodik kontrol et
            self._root.after(100, self._process_queue)
            self._root.mainloop()
        except Exception as exc:
            logger.error(f"[DesktopHUD] Tkinter hatası: {exc}")

    def _setup_window(self):
        root = self._root
        root.title("ULTRON HUD")
        root.overrideredirect(True)    # Başlık çubuğu yok
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.93)
        root.configure(bg=BG_COLOR)

        # Ekranın ortasına yerleştir
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w, h = 620, 320
        x = (sw - w) // 2
        y = int(sh * 0.25)
        root.geometry(f"{w}x{h}+{x}+{y}")

        # Sürüklenebilir pencere
        root.bind("<ButtonPress-1>", self._start_drag)
        root.bind("<B1-Motion>", self._on_drag)

        # Esc ile kapat
        root.bind("<Escape>", lambda e: self.hide())

    def _setup_widgets(self):
        root = self._root

        # Dış çerçeve (neon kenarlık efekti)
        frame = tk.Frame(root, bg=BORDER_COLOR, padx=1, pady=1)
        frame.pack(fill=tk.BOTH, expand=True, padx=2, pady=2)

        inner = tk.Frame(frame, bg=BG_COLOR, padx=12, pady=10)
        inner.pack(fill=tk.BOTH, expand=True)

        # Başlık satırı
        header = tk.Frame(inner, bg=BG_COLOR)
        header.pack(fill=tk.X, pady=(0, 8))

        title_lbl = tk.Label(
            header, text="⚡ U.L.T.R.O.N", fg=BORDER_COLOR, bg=BG_COLOR,
            font=("Courier New", 11, "bold"), anchor="w"
        )
        title_lbl.pack(side=tk.LEFT)

        # Swarm agent sayacı
        self._status_var = tk.StringVar(value="● HAZIR")
        status_lbl = tk.Label(
            header, textvariable=self._status_var, fg=DIM_COLOR,
            bg=BG_COLOR, font=("Courier New", 9), anchor="e"
        )
        status_lbl.pack(side=tk.RIGHT)

        # Yanıt alanı
        resp_frame = tk.Frame(inner, bg=INPUT_BG, padx=8, pady=6)
        resp_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 8))

        self._response_text = tk.Text(
            resp_frame, bg=INPUT_BG, fg=RESPONSE_FG,
            font=("Courier New", 10), wrap=tk.WORD,
            state=tk.DISABLED, borderwidth=0, highlightthickness=0,
            height=8,
        )
        self._response_text.pack(fill=tk.BOTH, expand=True)

        # Komut giriş alanı
        input_frame = tk.Frame(inner, bg=BORDER_COLOR, padx=1, pady=1)
        input_frame.pack(fill=tk.X)

        input_inner = tk.Frame(input_frame, bg=INPUT_BG, padx=8, pady=6)
        input_inner.pack(fill=tk.BOTH)

        prompt_lbl = tk.Label(
            input_inner, text="›", fg=ACCENT, bg=INPUT_BG,
            font=("Courier New", 14, "bold")
        )
        prompt_lbl.pack(side=tk.LEFT, padx=(0, 6))

        self._input_var = tk.StringVar()
        entry = tk.Entry(
            input_inner, textvariable=self._input_var,
            bg=INPUT_BG, fg=TEXT_COLOR, insertbackground=BORDER_COLOR,
            font=("Courier New", 11), borderwidth=0, highlightthickness=0,
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entry.bind("<Return>", self._on_submit)
        entry.focus_set()
        self._entry = entry

    # ── Sürükleme ─────────────────────────────────────────────────────────────

    def _start_drag(self, event):
        self._drag_x = event.x
        self._drag_y = event.y

    def _on_drag(self, event):
        try:
            x = self._root.winfo_x() + event.x - self._drag_x
            y = self._root.winfo_y() + event.y - self._drag_y
            self._root.geometry(f"+{x}+{y}")
        except Exception:
            pass

    # ── Göster / Gizle ────────────────────────────────────────────────────────

    def show(self):
        self._msg_queue.put(("show", None))

    def hide(self):
        self._msg_queue.put(("hide", None))

    def toggle(self):
        if self._visible:
            self.hide()
        else:
            self.show()

    def _process_queue(self):
        """Tkinter thread'inde kuyruktaki komutları işler."""
        try:
            while True:
                cmd, data = self._msg_queue.get_nowait()
                if cmd == "show":
                    self._root.deiconify()
                    self._root.lift()
                    self._root.attributes("-topmost", True)
                    self._visible = True
                    try:
                        self._entry.focus_set()
                    except Exception:
                        pass
                elif cmd == "hide":
                    self._root.withdraw()
                    self._visible = False
                elif cmd == "response":
                    self._show_response(data)
                elif cmd == "status":
                    if self._status_var:
                        self._status_var.set(data)
        except queue.Empty:
            pass
        finally:
            if self._root:
                self._root.after(100, self._process_queue)

    def _show_response(self, text: str):
        if not self._response_text:
            return
        self._response_text.configure(state=tk.NORMAL)
        self._response_text.delete("1.0", tk.END)
        self._response_text.insert(tk.END, text)
        self._response_text.configure(state=tk.DISABLED)

    # ── Komut Gönderme ────────────────────────────────────────────────────────

    def _on_submit(self, event=None):
        text = (self._input_var.get() or "").strip()
        if not text:
            return
        self._input_var.set("")
        self._msg_queue.put(("response", f"⏳ Gönderiliyor: {text}"))
        self._msg_queue.put(("status", "● DÜŞÜNÜYOR..."))
        threading.Thread(target=self._send_command, args=(text,), daemon=True).start()

    def _send_command(self, text: str):
        """Komutu sunucuya gönderir, yanıtı alır."""
        try:
            import websockets.sync.client as _wsc

            token = self._get_token()
            url = self._server_url.replace("ws://", "ws://") + f"/ws/live?token={token}"

            with _wsc.connect(url, open_timeout=5) as ws:
                ws.send(json.dumps({"type": "text", "text": text}))
                self._msg_queue.put(("status", "● YANIT BEKLENİYOR..."))
                # İlk yanıt mesajını bekle
                response = ws.recv(timeout=WS_TIMEOUT)
                data = json.loads(response)
                reply = data.get("text") or data.get("content") or str(data)
                self._msg_queue.put(("response", reply[:800]))
        except Exception as exc:
            self._msg_queue.put(("response", f"⚠️ Sunucu bağlantısı kurulamadı.\n{exc}"))
        finally:
            self._msg_queue.put(("status", "● HAZIR"))

    def _get_token(self) -> str:
        try:
            from app_paths import data_path
            cfg = json.loads(data_path("jarvis_web", "web_config.json").read_text(encoding="utf-8"))
            return cfg.get("token", "")
        except Exception:
            return os.environ.get("ULTRON_WEB_TOKEN", "")

    # ── Global Hotkey ─────────────────────────────────────────────────────────

    def _register_hotkey(self):
        """keyboard paketi ile global hotkey kaydeder. Başarısız olursa sessizce atlar."""
        try:
            import keyboard  # type: ignore
            keyboard.add_hotkey(HOTKEY, self.toggle)
            self._hotkey_registered = True
            logger.info(f"[DesktopHUD] ⌨️ Hotkey kayıt edildi: {HOTKEY}")
        except ImportError:
            logger.warning("[DesktopHUD] 'keyboard' paketi yok — hotkey devre dışı. pip install keyboard")
        except Exception as exc:
            logger.warning(f"[DesktopHUD] Hotkey kaydedilemedi (yönetici yetkisi gerekebilir): {exc}")

    # ── Swarm Bağlantısı ──────────────────────────────────────────────────────

    def update_swarm_status(self, active_count: int):
        """SwarmReporter'dan çağrılır — aktif ajan sayısını günceller."""
        if active_count > 0:
            self._msg_queue.put(("status", f"⚡ {active_count} AJAN AKTİF"))
        else:
            self._msg_queue.put(("status", "● HAZIR"))


# Global singleton
desktop_hud = DesktopHUD()


if __name__ == "__main__":
    # Konfigürasyon ve loglama ayarları alt süreç için
    logging.basicConfig(level=logging.INFO)
    import threading
    threading.Thread(target=desktop_hud._register_hotkey, daemon=True).start()
    desktop_hud._run_tk()
