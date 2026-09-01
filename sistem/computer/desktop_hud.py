"""
ULTRON Desktop HUD v2 — Şeffaf Masaüstü Komut Arayüzü
──────────────────────────────────────────────────────
Alt+Space ile ekranın üstüne şeffaf, borderless bir komut kutusu açar.
Sunucuya kalıcı WebSocket bağlantısı kurar; yanıtları sohbet günlüğü
biçiminde gösterir.

Özellikler
----------
• Alt+Space               : HUD göster / gizle (fade animasyonlu)
• ↑ / ↓                   : komut geçmişi
• /help /clear /theme /ping /center /exit : slash komutları
• /theme reactor | ultron : mavi (Arc Reactor) / kırmızı (Ultron) tema
• Pencere konumu + tema hatırlanır (hud_state.json)
• Otomatik yeniden bağlanma + bağlantı göstergesi (● yeşil/kırmızı)
• Tek örnek kilidi, DPI uyumu, Windows 11 yuvarlak köşe

Bağımlılıklar: tkinter (built-in), websockets >= 11, keyboard (opsiyonel)
"""

from __future__ import annotations

import json
import logging
import os
import queue
import socket
import sys
import threading
import time
import tkinter as tk
import urllib.parse
from pathlib import Path
from typing import Optional

logger = logging.getLogger("ultron.computer.desktop_hud")

# ── Palet (koyu, modern) ──────────────────────────────────────────────────
BG_COLOR     = "#161618"      # Arkaplan
BORDER_COLOR = "#2c2c2e"      # İnce çerçeve
TEXT_COLOR   = "#f5f5f7"      # Parlak metin
INPUT_BG     = "#232326"      # Giriş alanı
RESPONSE_FG  = "#c7c7cc"      # Yanıt metni
DIM_COLOR    = "#636366"      # Pasif metin
OK_COLOR     = "#30d158"      # Bağlı
ERR_COLOR    = "#ff453a"      # Hata / bağlı değil
WARN_COLOR   = "#ffd60a"      # Uyarı

THEMES: dict[str, dict[str, str]] = {
    "reactor": {"accent": "#0a84ff", "glow": "#5eb0ff", "label": "ARC REACTOR"},
    "ultron":  {"accent": "#ff453a", "glow": "#ff8a80", "label": "ULTRON"},
}

HOTKEY       = "alt+space"
RECV_TICK    = 0.1      # WS dinleme adımı (sn)
RETRY_MAX    = 10.0     # yeniden bağlanma bekleme üst sınırı (sn)
IDLE_TIMEOUT = 25.0     # yanıt gelmezse "düşünme" durumunu bitir (sn)
ALPHA_ON     = 0.97     # görünürken opaklık
HUD_W, HUD_H = 660, 380
LOCK_PORT    = 8766     # tek-örnek kilidi (localhost)

FONT_MAIN  = ("Segoe UI", 11)
FONT_BOLD  = ("Segoe UI", 11, "bold")
FONT_TITLE = ("Segoe UI", 12, "bold")
FONT_SMALL = ("Segoe UI", 9)

_LOCK_SOCKET: Optional[socket.socket] = None


def ensure_single_instance() -> bool:
    """Aynı makinede ikinci HUD örneğinin açılmasını engeller."""
    global _LOCK_SOCKET
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.bind(("127.0.0.1", LOCK_PORT))
        _LOCK_SOCKET = s
        return True
    except OSError:
        return False


class DesktopHUD:
    """
    Şeffaf, borderless tkinter penceresi. Alt+Space ile gösterilir/gizlenir.
    Kalıcı WebSocket bağlantısı üzerinden server.py ile konuşur.
    Dış arayüz korunmuştur: start(), stop(), show(), hide(), toggle(),
    update_swarm_status()
    """

    _PH = "ULTRON'a komut ver…   ( /help )"

    def __init__(self) -> None:
        self._visible = False
        self._root: Optional[tk.Tk] = None
        self._input_var: Optional[tk.StringVar] = None
        self._response_text: Optional[tk.Text] = None
        self._status_var = tk.StringVar(value="BAŞLATILIYOR")
        self._msg_queue: queue.Queue = queue.Queue()
        self._hotkey_registered = False
        self._server_url = self._get_server_url()

        # ── WebSocket işçisi ──
        self._ws = None
        self._connected = False
        self._send_queue: queue.Queue = queue.Queue()
        self._stop_event = threading.Event()
        self._ws_thread: Optional[threading.Thread] = None

        # ── UI durumu ──
        self._entry = None
        self._entry_focus = False
        self._history: list[str] = []
        self._history_idx = 0
        self._resp_new = True          # yeni yanıt bloğu başlayacak mı?
        self._thinking = False
        self._last_rx = 0.0
        self._alpha_target = ALPHA_ON
        self._alpha_animating = False
        self._conn_state = False
        self._theme_name = "reactor"
        self._pos: Optional[tuple[int, int]] = None
        self._state_path = self._resolve_state_path()
        self._load_state()

    # ── Yapılandırma / Kalıcılık ──────────────────────────────────────────

    @staticmethod
    def _resolve_state_path() -> Path:
        try:
            from app_paths import data_path
            return Path(str(data_path("desktop_hud", "hud_state.json")))
        except Exception:
            return Path.home() / ".ultron_hud_state.json"

    def _get_server_url(self) -> str:
        """Sunucu URL'sini config'ten okur."""
        try:
            from app_paths import data_path
            cfg_path = data_path("jarvis_web", "web_config.json")
            if cfg_path.exists():
                cfg = json.loads(Path(str(cfg_path)).read_text(encoding="utf-8"))
                return f"ws://{cfg.get('host', '127.0.0.1')}:{cfg.get('port', 8765)}"
        except Exception:
            pass
        return "ws://127.0.0.1:8765"

    def _get_token(self) -> str:
        """Token'ı önce ortam değişkeninden, yoksa config dosyasından okur."""
        env_token = os.environ.get("ULTRON_WEB_TOKEN", "").strip()
        if env_token:
            return env_token
        try:
            from app_paths import data_path
            cfg = json.loads(
                Path(str(data_path("jarvis_web", "web_config.json"))).read_text(encoding="utf-8")
            )
            return cfg.get("token", "")
        except Exception:
            return ""

    def _load_state(self) -> None:
        try:
            if self._state_path.exists():
                st = json.loads(self._state_path.read_text(encoding="utf-8"))
                if st.get("x") is not None:
                    self._pos = (int(st["x"]), int(st["y"]))
                if st.get("theme") in THEMES:
                    self._theme_name = st["theme"]
        except Exception:
            pass

    def _save_state(self) -> None:
        try:
            if self._root is None:
                return
            self._state_path.parent.mkdir(parents=True, exist_ok=True)
            self._state_path.write_text(json.dumps({
                "x": self._root.winfo_x(),
                "y": self._root.winfo_y(),
                "theme": self._theme_name,
            }), encoding="utf-8")
        except Exception:
            pass

    def _theme(self) -> dict[str, str]:
        return THEMES.get(self._theme_name, THEMES["reactor"])

    # ── Süreç Yönetimi (dış arayüz) ───────────────────────────────────────

    def start(self):
        """HUD'u ayrı bir süreç (subprocess) olarak başlatır."""
        if getattr(sys, "frozen", False) or __name__ == "__main__":
            return
        proc = getattr(self, "_process", None)
        if proc is not None and proc.poll() is None:
            return  # zaten çalışıyor

        import subprocess
        script_path = Path(__file__).resolve()
        try:
            flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
            self._process = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=str(script_path.parent.parent),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=flags,
            )
            logger.info("✅ [DesktopHUD] Masaüstü HUD başlatıldı (subprocess).")
        except Exception as exc:
            logger.error("[DesktopHUD] Subprocess başlatılamadı: %s", exc)

    def stop(self):
        """HUD sürecini sonlandırır."""
        self._stop_event.set()
        try:
            proc = getattr(self, "_process", None)
            if proc is not None:
                proc.terminate()
        except Exception:
            pass

    # ── Tkinter Penceresi ─────────────────────────────────────────────────

    def _run_tk(self):
        try:
            self._root = tk.Tk()
            self._root.withdraw()
            self._setup_window()
            self._setup_widgets()
            self._apply_theme()
            self._boot_message()
            self._root.after(80, self._process_queue)
            self._root.after(400, self._start_ws_worker)
            self._root.mainloop()
        except Exception as exc:
            logger.error("[DesktopHUD] Tkinter hatası: %s", exc)
        finally:
            self._stop_event.set()
            logger.info("[DesktopHUD] HUD kapatıldı.")

    def _setup_window(self):
        root = self._root
        root.title("ULTRON HUD")
        root.overrideredirect(True)
        root.attributes("-topmost", True)
        root.attributes("-alpha", 0.0)
        root.configure(bg=BG_COLOR)

        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        x = self._pos[0] if self._pos else (sw - HUD_W) // 2
        y = self._pos[1] if self._pos else int(sh * 0.18)
        x = max(0, min(x, sw - HUD_W))   # ekran dışına taşmayı engelle
        y = max(0, min(y, sh - HUD_H))
        root.geometry(f"{HUD_W}x{HUD_H}+{x}+{y}")

        root.bind("<ButtonPress-1>", self._start_drag)
        root.bind("<B1-Motion>", self._on_drag)
        root.bind("<ButtonRelease-1>", lambda e: self._save_state())
        root.bind("<Escape>", lambda e: self.hide())
        root.bind("<Control-l>", lambda e: self._clear_log())
        root.bind("<Control-q>", lambda e: self._quit())
        self._apply_round_corners()

    def _apply_round_corners(self):
        """Windows 11'de yuvarlak köşe (kozmetik — hata verirse sessizce atlanır)."""
        if os.name != "nt":
            return
        try:
            import ctypes
            self._root.update_idletasks()
            hwnd = self._root.winfo_id()
            parent = ctypes.windll.user32.GetParent(hwnd)
            if parent:
                hwnd = parent
            val = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                hwnd, 33, ctypes.byref(val), ctypes.sizeof(val)
            )
        except Exception:
            pass

    def _setup_widgets(self):
        root = self._root

        self._outer = tk.Frame(root, bg=BORDER_COLOR)
        self._outer.pack(fill=tk.BOTH, expand=True, padx=1, pady=1)

        inner = tk.Frame(self._outer, bg=BG_COLOR)
        inner.pack(fill=tk.BOTH, expand=True, padx=18, pady=14)

        # ── Başlık ──
        header = tk.Frame(inner, bg=BG_COLOR)
        header.pack(fill=tk.X, pady=(0, 12))

        self._title_lbl = tk.Label(header, text="U L T R O N", fg=TEXT_COLOR,
                                   bg=BG_COLOR, font=FONT_TITLE)
        self._title_lbl.pack(side=tk.LEFT)

        self._conn_lbl = tk.Label(header, text="●", fg=ERR_COLOR, bg=BG_COLOR, font=FONT_SMALL)
        self._conn_lbl.pack(side=tk.RIGHT, padx=(0, 6))

        self._status_lbl = tk.Label(header, textvariable=self._status_var,
                                    fg=DIM_COLOR, bg=BG_COLOR, font=FONT_SMALL)
        self._status_lbl.pack(side=tk.RIGHT)

        # ── Giriş (odaklanınca accent renkli çerçeve) ──
        self._input_border = tk.Frame(inner, bg=BORDER_COLOR)
        self._input_border.pack(fill=tk.X, pady=(0, 12))

        input_frame = tk.Frame(self._input_border, bg=INPUT_BG, padx=14, pady=10)
        input_frame.pack(fill=tk.X, padx=1, pady=1)

        self._prompt_lbl = tk.Label(input_frame, text="◈", fg=THEMES["reactor"]["accent"],
                                    bg=INPUT_BG, font=FONT_TITLE)
        self._prompt_lbl.pack(side=tk.LEFT, padx=(0, 10))

        self._input_var = tk.StringVar()
        self._entry = tk.Entry(
            input_frame, textvariable=self._input_var,
            bg=INPUT_BG, fg=TEXT_COLOR, insertbackground=THEMES["reactor"]["accent"],
            font=FONT_MAIN, borderwidth=0, highlightthickness=0,
        )
        self._entry.pack(side=tk.LEFT, fill=tk.X, expand=True)
        self._entry.bind("<Return>", self._on_submit)
        self._entry.bind("<Up>", self._history_prev)
        self._entry.bind("<Down>", self._history_next)
        self._entry.bind("<FocusIn>", self._on_focus_in)
        self._entry.bind("<FocusOut>", self._on_focus_out)

        # ── Yanıt günlüğü ──
        log_wrap = tk.Frame(inner, bg=BG_COLOR)
        log_wrap.pack(fill=tk.BOTH, expand=True)

        self._scroll = tk.Scrollbar(log_wrap, width=6, bd=0, elementborderwidth=0,
                                    bg=BG_COLOR, troughcolor=BG_COLOR,
                                    activerelief=tk.FLAT, highlightthickness=0)
        self._scroll.pack(side=tk.RIGHT, fill=tk.Y)

        self._response_text = tk.Text(
            log_wrap, bg=BG_COLOR, fg=RESPONSE_FG, font=FONT_MAIN,
            wrap=tk.WORD, state=tk.DISABLED, borderwidth=0, highlightthickness=0,
            cursor="arrow", padx=4, spacing3=2, yscrollcommand=self._scroll.set,
        )
        self._response_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._scroll.config(command=self._response_text.yview)
        self._response_text.bind("<Button-1>", lambda e: self._entry.focus_set())
        self._bind_mouse_wheel()

        self._setup_tags()

        # ── Alt ipucu satırı ──
        tk.Label(inner, text="⏎ gönder · ↑↓ geçmiş · Esc gizle · Ctrl+L temizle · /help",
                 fg=DIM_COLOR, bg=BG_COLOR, font=FONT_SMALL).pack(fill=tk.X, pady=(8, 0))

    def _setup_tags(self):
        t = self._response_text
        t.tag_configure("user", foreground=self._theme()["glow"], font=FONT_BOLD)
        t.tag_configure("resp", foreground=RESPONSE_FG)
        t.tag_configure("sys",  foreground=DIM_COLOR, font=FONT_SMALL)
        t.tag_configure("err",  foreground=ERR_COLOR)
        t.tag_configure("ok",   foreground=OK_COLOR)
        t.tag_configure("warn", foreground=WARN_COLOR)

    def _bind_mouse_wheel(self):
        t = self._response_text
        if sys.platform == "darwin":
            t.bind("<MouseWheel>", lambda e: t.yview_scroll(-1 * e.delta, "units"))
        elif os.name == "nt":
            t.bind("<MouseWheel>", lambda e: t.yview_scroll(-1 * int(e.delta / 120), "units"))
        else:
            t.bind("<Button-4>", lambda e: t.yview_scroll(-1, "units"))
            t.bind("<Button-5>", lambda e: t.yview_scroll(1, "units"))

    def _apply_theme(self):
        th = self._theme()
        try:
            self._prompt_lbl.configure(fg=th["accent"])
            self._entry.configure(insertbackground=th["accent"])
            self._response_text.tag_configure("user", foreground=th["glow"])
            if self._entry_focus:
                self._input_border.configure(bg=th["accent"])
        except Exception:
            pass

    def _boot_message(self):
        self._log("sys", f"ULTRON v2.0 · tema: {self._theme()['label']}")
        self._log("sys", "Sunucuya bağlanılıyor…")

    # ── Placeholder ───────────────────────────────────────────────────────

    def _on_focus_in(self, _=None):
        self._entry_focus = True
        self._input_border.configure(bg=self._theme()["accent"])
        if self._input_var.get() == self._PH:
            self._input_var.set("")
            self._entry.configure(fg=TEXT_COLOR)

    def _on_focus_out(self, _=None):
        self._entry_focus = False
        self._input_border.configure(bg=BORDER_COLOR)
        if not self._input_var.get():
            self._input_var.set(self._PH)
            self._entry.configure(fg=DIM_COLOR)

    # ── Sürükleme ─────────────────────────────────────────────────────────

    def _start_drag(self, event):
        self._drag_x, self._drag_y = event.x, event.y

    def _on_drag(self, event):
        try:
            x = self._root.winfo_x() + event.x - self._drag_x
            y = self._root.winfo_y() + event.y - self._drag_y
            self._root.geometry(f"+{x}+{y}")
        except Exception:
            pass

    # ── Göster / Gizle (fade animasyonlu) ────────────────────────────────

    def show(self):
        self._msg_queue.put(("show", None))

    def hide(self):
        self._msg_queue.put(("hide", None))

    def toggle(self):
        self._msg_queue.put(("hide" if self._visible else "show", None))

    def _do_show(self):
        if self._root is None:
            return
        if self._visible:
            self._root.lift()
            try:
                self._entry.focus_set()
            except Exception:
                pass
            return
        self._root.attributes("-alpha", 0.0)
        self._root.deiconify()
        self._root.lift()
        self._root.attributes("-topmost", True)
        self._visible = True
        try:
            self._root.focus_force()
            self._entry.focus_set()
        except Exception:
            pass
        self._animate_alpha(ALPHA_ON)

    def _do_hide(self):
        if self._root is None or not self._visible:
            return
        self._visible = False
        self._save_state()
        self._animate_alpha(0.0)

    def _animate_alpha(self, target: float):
        self._alpha_target = target
        if not self._alpha_animating:
            self._alpha_animating = True
            self._alpha_step()

    def _alpha_step(self):
        root = self._root
        if root is None:
            self._alpha_animating = False
            return
        try:
            cur = root.attributes("-alpha")
        except tk.TclError:
            self._alpha_animating = False
            return
        diff = self._alpha_target - cur
        if abs(diff) <= 0.04:
            root.attributes("-alpha", self._alpha_target)
            self._alpha_animating = False
            if self._alpha_target == 0.0:
                root.withdraw()
            return
        root.attributes("-alpha", cur + diff * 0.3)
        root.after(10, self._alpha_step)

    # ── Mesaj kuyruğu (UI thread) ─────────────────────────────────────────

    def _process_queue(self):
        try:
            while True:
                cmd, data = self._msg_queue.get_nowait()
                if cmd == "show":
                    self._do_show()
                elif cmd == "hide":
                    self._do_hide()
                elif cmd == "quit":
                    self._quit()
                elif cmd == "log":
                    self._log(data[0], data[1])
                elif cmd == "response":
                    self._show_response(data)
                elif cmd == "status":
                    self._set_status(data)
                elif cmd == "conn":
                    self._set_conn(data)
                elif cmd == "sent":
                    self._resp_new = True
                    self._start_thinking()
        except queue.Empty:
            pass

        # Zaman aşımı: sunucu hiç yanıt vermedi
        if self._thinking and self._last_rx and \
                time.monotonic() - self._last_rx > IDLE_TIMEOUT:
            self._stop_thinking()
            self._log("warn", "⏱ Zaman aşımı — sunucudan yanıt alınamadı.")
            self._set_status("HAZIR")

        try:
            if self._root is not None:
                self._root.after(80, self._process_queue)
        except tk.TclError:
            pass

    def _log(self, tag: str, text: str):
        t = self._response_text
        if not t:
            return
        t.configure(state=tk.NORMAL)
        if t.index("end-1c") != "1.0":
            t.insert(tk.END, "\n")
        t.insert(tk.END, text, tag)
        t.see(tk.END)
        t.configure(state=tk.DISABLED)

    def _clear_log(self):
        t = self._response_text
        t.configure(state=tk.NORMAL)
        t.delete("1.0", tk.END)
        t.configure(state=tk.DISABLED)
        self._resp_new = True

    def _set_status(self, text: str, accent: bool = False):
        self._status_var.set(text)
        try:
            self._status_lbl.configure(
                fg=self._theme()["accent"] if accent else DIM_COLOR)
        except Exception:
            pass

    def _set_conn(self, ok: bool):
        self._conn_lbl.configure(fg=OK_COLOR if ok else ERR_COLOR)
        if ok != self._conn_state:
            if ok:
                self._log("ok", "● Sunucu bağlantısı kuruldu.")
                self._set_status("HAZIR")
            else:
                self._log("err", "● Sunucu bağlantısı koptu — yeniden bağlanılıyor…")
                self._set_status("ÇEVRİMDIŞI · yeniden deneniyor")
        self._conn_state = ok

    # ── "Düşünüyor" animasyonu ────────────────────────────────────────────

    def _start_thinking(self):
        self._thinking = True
        self._last_rx = time.monotonic()
        self._think_step(0)

    def _think_step(self, n: int):
        if not self._thinking or not self._root:
            return
        dots = "·" * (n % 4)
        self._set_status(f"◈ DÜŞÜNÜYOR {dots}".rstrip(), accent=True)
        self._root.after(280, lambda: self._think_step(n + 1))

    def _stop_thinking(self):
        self._thinking = False

    # ── Yanıt gösterimi (streaming uyumlu) ────────────────────────────────

    def _show_response(self, text: str):
        if not text:
            return
        if self._thinking:
            self._stop_thinking()
            self._set_status("YANIT ALINDI", accent=True)
            self._root.after(
                1800, lambda: (not self._thinking) and self._set_status("HAZIR"))
        t = self._response_text
        t.configure(state=tk.NORMAL)
        if self._resp_new:
            if t.index("end-1c") != "1.0":
                t.insert(tk.END, "\n")
            self._resp_new = False
        else:
            t.insert(tk.END, " ")
        t.insert(tk.END, text, "resp")
        t.see(tk.END)
        t.configure(state=tk.DISABLED)

    # ── Komut Geçmişi ─────────────────────────────────────────────────────

    def _history_prev(self, _event=None):
        if not self._history:
            return "break"
        if self._history_idx > 0:
            self._history_idx -= 1
            self._input_var.set(self._history[self._history_idx])
            self._entry.icursor(tk.END)
        return "break"

    def _history_next(self, _event=None):
        if not self._history:
            return "break"
        if self._history_idx < len(self._history) - 1:
            self._history_idx += 1
            self._input_var.set(self._history[self._history_idx])
        else:
            self._history_idx = len(self._history)
            self._input_var.set("")
        self._entry.icursor(tk.END)
        return "break"

    # ── Komut Gönderme ────────────────────────────────────────────────────

    def _on_submit(self, _event=None):
        text = (self._input_var.get() or "").strip()
        if not text or text == self._PH:
            self._input_var.set("")
            return
        self._input_var.set("")
        self._history.append(text)
        self._history_idx = len(self._history)

        if text.startswith("/"):
            self._handle_slash(text)
            return

        self._log("user", "▸ " + text)
        if not self._connected:
            self._log("err", "✖ Sunucu çevrimdışı — komut iletilemedi.")
            return
        self._send_queue.put(text)

    def _handle_slash(self, text: str):
        parts = text[1:].split(maxsplit=1)
        cmd = parts[0].lower() if parts else ""
        arg = parts[1].strip() if len(parts) > 1 else ""

        if cmd in ("h", "help", "?"):
            self._log("sys",
                      "Komutlar:\n"
                      "  /help                — bu yardım\n"
                      "  /clear               — günlüğü temizle\n"
                      "  /theme reactor|ultron — renk teması\n"
                      "  /ping                — bağlantı testi\n"
                      "  /center              — pencereyi ortala\n"
                      "  /exit                — HUD'u kapat")
        elif cmd == "clear":
            self._clear_log()
        elif cmd == "theme":
            if arg in THEMES:
                self._theme_name = arg
                self._apply_theme()
                self._save_state()
                self._log("ok", f"Tema: {self._theme()['label']}")
            else:
                self._log("warn", f"Tema seçenekleri: {', '.join(THEMES)}")
        elif cmd == "ping":
            if self._connected:
                self._log("ok", f"● Bağlantı aktif → {self._server_url}")
            else:
                self._log("err", "● Sunucuya bağlantı yok.")
        elif cmd == "center":
            sw = self._root.winfo_screenwidth()
            sh = self._root.winfo_screenheight()
            self._root.geometry(f"+{(sw - HUD_W) // 2}+{int(sh * 0.18)}")
            self._save_state()
        elif cmd in ("exit", "quit", "q"):
            self._quit()
        else:
            self._log("warn", f"Bilinmeyen komut: /{cmd} — /help dene.")

    def _quit(self):
        self._save_state()
        self._stop_event.set()
        try:
            self._root.destroy()
        except Exception:
            pass

    # ── WebSocket işçisi (kalıcı bağlantı) ────────────────────────────────

    def _start_ws_worker(self):
        if self._ws_thread and self._ws_thread.is_alive():
            return
        self._stop_event.clear()
        self._ws_thread = threading.Thread(
            target=self._ws_worker, daemon=True, name="hud-ws")
        self._ws_thread.start()

    def _ws_worker(self):
        """Dinler, gönderir; koparsa üstel beklemeyle yeniden bağlanır."""
        retry = 1.0
        while not self._stop_event.is_set():
            try:
                import websockets.sync.client as wsc
                token = urllib.parse.quote(self._get_token())
                url = f"{self._server_url}/ws/live?token={token}"
                self._ws = wsc.connect(url, open_timeout=5)
                self._connected = True
                retry = 1.0
                self._msg_queue.put(("conn", True))
                logger.info("[DesktopHUD] WebSocket bağlı: %s", self._server_url)

                while not self._stop_event.is_set():
                    try:
                        raw = self._ws.recv(timeout=RECV_TICK)
                        if raw:
                            self._handle_message(raw)
                    except TimeoutError:
                        pass
                    try:
                        text = self._send_queue.get_nowait()
                        self._ws.send(json.dumps({"type": "text", "text": text}))
                        self._msg_queue.put(("sent", text))
                    except queue.Empty:
                        pass
            except Exception as exc:
                if not self._stop_event.is_set():
                    self._msg_queue.put(("conn", False))
                    logger.warning("[DesktopHUD] WebSocket koptu (%s) — %.1f sn içinde yeniden bağlanılacak",
                                   exc, retry)
                    self._stop_event.wait(retry)
                    retry = min(retry * 2, RETRY_MAX)
            finally:
                try:
                    if self._ws is not None:
                        self._ws.close()
                except Exception:
                    pass
                self._ws = None
                self._connected = False

    def _handle_message(self, raw):
        self._last_rx = time.monotonic()
        try:
            data = json.loads(raw)
        except Exception:
            self._msg_queue.put(("response", str(raw)[:800]))
            return
        if not isinstance(data, dict):
            self._msg_queue.put(("response", str(data)[:800]))
            return

        mtype = str(data.get("type", "")).lower()
        if mtype in ("text", "response", "assistant", "message", "content"):
            payload = data.get("text") or data.get("content") or data.get("message") or ""
            self._msg_queue.put(("response", str(payload)))
        elif mtype == "status":
            self._msg_queue.put(("status", str(data.get("status") or data.get("text") or "")))
        elif mtype == "swarm":
            try:
                self.update_swarm_status(int(data.get("active", 0)))
            except Exception:
                pass
        elif mtype in ("pong", "heartbeat", "ack", "tts"):
            pass  # yoksay
        else:
            payload = data.get("text") or data.get("content") or data.get("data")
            if payload:
                self._msg_queue.put(("response", str(payload)[:800]))

    # ── Global Hotkey ─────────────────────────────────────────────────────

    def _register_hotkey(self):
        """keyboard paketi ile global hotkey kaydeder. Başarısız olursa sessizce atlar."""
        try:
            import keyboard  # type: ignore
            keyboard.add_hotkey(HOTKEY, self.toggle)  # toggle queue kullanır → thread-safe
            self._hotkey_registered = True
            logger.info("[DesktopHUD] ⌨️ Hotkey kayıt edildi: %s", HOTKEY)
        except ImportError:
            logger.warning("[DesktopHUD] 'keyboard' paketi yok — hotkey devre dışı. pip install keyboard")
        except Exception as exc:
            logger.warning("[DesktopHUD] Hotkey kaydedilemedi (yönetici yetkisi gerekebilir): %s", exc)

    # ── Swarm Bağlantısı ──────────────────────────────────────────────────

    def update_swarm_status(self, active_count: int):
        """SwarmReporter'dan çağrılır — aktif ajan sayısını günceller."""
        txt = f"⚡ {active_count} AJAN AKTİF" if active_count > 0 else "HAZIR"
        self._msg_queue.put(("status", txt))


# Global singleton
desktop_hud = DesktopHUD()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
    )

    # Windows: DPI farkındalığı (bulanık metni önler)
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass

    if not ensure_single_instance():
        logger.info("[DesktopHUD] HUD zaten çalışıyor — bu örnek kapatılıyor.")
        sys.exit(0)

    threading.Thread(target=desktop_hud._register_hotkey, daemon=True, name="hud-hotkey").start()
    desktop_hud._run_tk()
