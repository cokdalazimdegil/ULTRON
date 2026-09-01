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

# Renkler (Sleek Modern Raycast/Spotlight teması)
BG_COLOR      = "#1c1c1e"       # Koyu Apple gri
BORDER_COLOR  = "#333336"       # İnce çerçeve
TEXT_COLOR    = "#f5f5f7"       # Parlak beyaz (metin)
INPUT_BG      = "#2c2c2e"       # Giriş alanı hafif daha açık
ACCENT        = "#0a84ff"       # Modern mavi
RESPONSE_FG   = "#d1d1d6"       # Yanıt metni (hafif gri)
DIM_COLOR     = "#8e8e93"       # Pasif metin

HOTKEY        = "alt+space"
WS_TIMEOUT    = 10.0
FONT_MAIN     = ("Segoe UI", 11)
FONT_BOLD     = ("Segoe UI", 11, "bold")
FONT_TITLE    = ("Segoe UI", 12, "bold")
FONT_SMALL    = ("Segoe UI", 9)


class DesktopHUD:
    """
    Şeffaf, borderless tkinter penceresi. Modern, minimal UI.
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
                return f"ws://{cfg.get('host', '127.0.0.1')}:{cfg.get('port', 8765)}"
        except Exception:
            pass
        return "ws://127.0.0.1:8765"

    def start(self):
        """HUD'u ayrı bir işlem (subprocess) olarak başlatır."""
        import sys
        import subprocess
        from pathlib import Path

        script_path = Path(__file__).resolve()
        sistem_dir = script_path.parent.parent  # sistem/

        # Sadece ana süreçten çağrıldığında alt süreç başlat (sonsuz döngüyü önle)
        if not hasattr(sys, "frozen") and __name__ != "__main__":
            try:
                env = os.environ.copy()
                self._process = subprocess.Popen(
                    [sys.executable, str(script_path)],
                    cwd=str(sistem_dir),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    env=env,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
                )
                logger.info("✅ [DesktopHUD] Masaüstü HUD başlatıldı (Subprocess).")
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
        root.attributes("-alpha", 0.96)
        root.configure(bg=BG_COLOR)

        # Ekranın ortasına yerleştir
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w, h = 650, 350
        x = (sw - w) // 2
        y = int(sh * 0.2)
        root.geometry(f"{w}x{h}+{x}+{y}")

        # Sürüklenebilir pencere
        root.bind("<ButtonPress-1>", self._start_drag)
        root.bind("<B1-Motion>", self._on_drag)

        # Esc ile kapat
        root.bind("<Escape>", lambda e: self.hide())

    def _setup_widgets(self):
        root = self._root

        # Dış çerçeve (çok ince, modern sınır)
        frame = tk.Frame(root, bg=BORDER_COLOR, padx=1, pady=1)
        frame.pack(fill=tk.BOTH, expand=True)

        inner = tk.Frame(frame, bg=BG_COLOR, padx=20, pady=20)
        inner.pack(fill=tk.BOTH, expand=True)

        # Başlık satırı
        header = tk.Frame(inner, bg=BG_COLOR)
        header.pack(fill=tk.X, pady=(0, 15))

        title_lbl = tk.Label(
            header, text="U.L.T.R.O.N", fg=TEXT_COLOR, bg=BG_COLOR,
            font=FONT_TITLE, anchor="w"
        )
        title_lbl.pack(side=tk.LEFT)

        # Swarm agent sayacı
        self._status_var = tk.StringVar(value="Hazır")
        status_lbl = tk.Label(
            header, textvariable=self._status_var, fg=DIM_COLOR,
            bg=BG_COLOR, font=FONT_SMALL, anchor="e"
        )
        status_lbl.pack(side=tk.RIGHT)

        # Komut giriş alanı (Üstte)
        input_frame = tk.Frame(inner, bg=INPUT_BG, padx=15, pady=12)
        input_frame.pack(fill=tk.X, pady=(0, 15))

        prompt_lbl = tk.Label(
            input_frame, text="✨", fg=ACCENT, bg=INPUT_BG,
            font=FONT_TITLE
        )
        prompt_lbl.pack(side=tk.LEFT, padx=(0, 10))

        self._input_var = tk.StringVar()
        entry = tk.Entry(
            input_frame, textvariable=self._input_var,
            bg=INPUT_BG, fg=TEXT_COLOR, insertbackground=ACCENT,
            font=FONT_MAIN, borderwidth=0, highlightthickness=0,
        )
        entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        entry.bind("<Return>", self._on_submit)
        entry.focus_set()
        self._entry = entry

        # Yanıt alanı (Altta)
        self._response_text = tk.Text(
            inner, bg=BG_COLOR, fg=RESPONSE_FG,
            font=FONT_MAIN, wrap=tk.WORD,
            state=tk.DISABLED, borderwidth=0, highlightthickness=0,
            height=9,
        )
        self._response_text.pack(fill=tk.BOTH, expand=True)

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
        self._msg_queue.put(("response", f"İşleniyor: {text}"))
        self._msg_queue.put(("status", "Düşünüyor..."))
        threading.Thread(target=self._send_command, args=(text,), daemon=True).start()

    def _send_command(self, text: str):
        """Komutu sunucuya gönderir, yanıtı alır."""
        try:
            import websockets.sync.client as _wsc

            token = self._get_token()
            url = self._server_url.replace("ws://", "ws://") + f"/ws/live?token={token}"

            with _wsc.connect(url, open_timeout=5) as ws:
                ws.send(json.dumps({"type": "text", "text": text}))
                self._msg_queue.put(("status", "Yanıt bekleniyor..."))
                # İlk yanıt mesajını bekle
                response = ws.recv(timeout=WS_TIMEOUT)
                data = json.loads(response)
                reply = data.get("text") or data.get("content") or str(data)
                self._msg_queue.put(("response", reply[:1500]))
        except Exception as exc:
            self._msg_queue.put(("response", f"Sunucu bağlantısı kurulamadı.\n{exc}"))
        finally:
            self._msg_queue.put(("status", "Hazır"))

    def _get_token(self) -> str:
        """Token'ı önce ortam değişkeninden, yoksa config dosyasından okur."""
        env_token = os.environ.get("ULTRON_WEB_TOKEN", "").strip()
        if env_token:
            return env_token
        try:
            from app_paths import data_path
            cfg = json.loads(data_path("jarvis_web", "web_config.json").read_text(encoding="utf-8"))
            return cfg.get("token", "")
        except Exception:
            return ""

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
