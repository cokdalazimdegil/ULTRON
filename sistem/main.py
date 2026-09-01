#!/usr/bin/env python3
"""
ULTRON macOS & Windows — Cinematic Webview wrapper
"""
import os
import sys
import time
import subprocess
import threading
import atexit
from pathlib import Path

# Add UI and server paths
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from actions.platform_utils import acquire_single_instance, focus_window, configure_console_output
from app_config import load_app_config, save_app_config

configure_console_output()

server_process = None
agent_process = None

def cleanup_subprocesses():
    print("[ULTRON] Kapatılıyor, alt servisler durduruluyor...")
    if server_process and server_process.poll() is None:
        server_process.terminate()
    if agent_process and agent_process.poll() is None:
        agent_process.terminate()

atexit.register(cleanup_subprocesses)

def start_server(token):
    global server_process
    print("[ULTRON] Yerel sinematik UI sunucusu baslatiliyor...")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["ULTRON_WEB_TOKEN"] = token  # Server uses this token for auth
    
    server_process = subprocess.Popen(
        [sys.executable, str(BASE_DIR / "jarvis_web" / "server.py"), "--port", "8765", "--no-ssl"],
        stdout=None,
        stderr=None,
        env=env
    )

def start_agent(token):
    global agent_process
    print("[ULTRON] Yerel sistem ajanı baslatiliyor...")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["ULTRON_WEB_TOKEN"] = token
    env["JARVIS_WEB_TOKEN"] = token
    
    agent_process = subprocess.Popen(
        [sys.executable, str(BASE_DIR / "jarvis_web" / "agent.py"), "--server", "ws://127.0.0.1:8765", "--token", token],
        stdout=None,
        stderr=None,
        env=env
    )

def main():
    if "--selftest" in sys.argv:
        raise SystemExit(0)

    is_web = "--web" in sys.argv

    if not acquire_single_instance():
        print("[ULTRON] Zaten calisiyor — mevcut pencere one getiriliyor.")
        if not is_web:
            focus_window("U.L.T.R.O.N")
        return

    # 1. Start backend services
    import secrets
    
    # Ensure token exists
    config = load_app_config()
    token = config.get("ultron_web_token", "")
    if not token:
        token = secrets.token_hex(8)
        config["ultron_web_token"] = token
        save_app_config(config)

    global server_process
    print("[ULTRON] Sunucu baslatiliyor...")
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["ULTRON_WEB_TOKEN"] = token  # Server uses this token for auth
    
    server_args = [sys.executable, str(BASE_DIR / "jarvis_web" / "server.py"), "--port", "8765"]
    if not is_web:
        server_args.append("--no-ssl")

    server_process = subprocess.Popen(
        server_args,
        stdout=None,
        stderr=None,
        env=env
    )
    
    # Wait for server to fully start
    time.sleep(4.0)
    
    start_agent(token)

    if is_web:
        print("[ULTRON] Telefon/Web modu aktif. Arayuz tarayicida calisacak.")
        print("[ULTRON] Kapatmak icin bu pencereyi (CTRL+C) kapatin.")
        try:
            server_process.wait()
        except KeyboardInterrupt:
            pass
        return

    # 2. Launch pywebview window
    import webview
    
    url = f"http://127.0.0.1:8765/?t={token}"
    
    print("[ULTRON] Sinematik 3D UI baslatiliyor...")
    
    window = webview.create_window(
        "U.L.T.R.O.N", 
        url,
        fullscreen=True,
        easy_drag=True,
        background_color="#000000"
    )
    
    webview.start(private_mode=True, debug=False)

if __name__ == "__main__":
    main()
