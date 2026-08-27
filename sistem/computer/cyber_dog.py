"""
ULTRON Cyber-Dog (Otonom Siber Güvenlik Kalkanı)
────────────────────────────────────────────────
• Arka planda psutil ile aktif işlemleri (process) tarar.
• Kripto madenci, keylogger veya şüpheli kaynak tüketen bir işlem bulduğunda
  durumu Gemini modeline göndererek "Tehdit mi?" diye sorar.
• Tehdit onaylanırsa işlemi acımasızca (SIGKILL) öldürür ve raporlar.
"""

import time
import psutil
import threading
import logging
import uuid
import platform
from typing import Optional, Callable

from orchestrator.gemini_reasoning import query_gemini_reasoning

logger = logging.getLogger("ultron.computer.cyberdog")

SUSPICIOUS_KEYWORDS = ["miner", "xmrig", "trojan", "keylogger", "ransomware", "crypt", "hack", "stealer"]
SAFE_PROCESSES = ["chrome.exe", "code.exe", "python.exe", "explorer.exe", "system", "svchost.exe", "taskmgr.exe"]

class CyberDogEngine:
    """Otonom Siber Güvenlik Bekçi Köpeği."""
    
    def __init__(self, patrol_interval_sec: float = 45.0):
        self.patrol_interval_sec = patrol_interval_sec
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cooldown_period = 300 # 5 dk
        self._cooldowns = {}
        
    def start_patrol(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._patrol_loop, name="CyberDog", daemon=True)
        self._thread.start()
        logger.info("[Cyber-Dog] 🐕 Devriye başlatıldı.")
        
    def stop_patrol(self):
        self._running = False

    def _notify(self, text: str):
        from core.event_bus import bus
        bus.publish("ui_alert", f"[SİBER GÜVENLİK UYARISI]: {text}")
        
    def _patrol_loop(self):
        while self._running:
            try:
                self._scan_and_evaluate()
            except Exception as e:
                logger.debug(f"[Cyber-Dog] Devriye hatası: {e}")
            time.sleep(self.patrol_interval_sec)
            
    def _scan_and_evaluate(self):
        now = time.time()
        suspicious_procs = []
        
        # Hızlı ön tarama (Heuristic)
        for proc in psutil.process_iter(['pid', 'name', 'cpu_percent']):
            try:
                pinfo = proc.info
                pname = str(pinfo['name'] or '').lower()
                pid = pinfo['pid']
                
                if pname in SAFE_PROCESSES or pid == 0:
                    continue
                
                # İsim bazlı şüphe
                is_sus = any(kw in pname for kw in SUSPICIOUS_KEYWORDS)
                
                # CPU bazlı şüphe (>80% CPU ve bilinmeyen)
                if not is_sus and pinfo.get('cpu_percent', 0) > 80.0:
                    is_sus = True
                    
                if is_sus:
                    if now - self._cooldowns.get(pname, 0) > self._cooldown_period:
                        suspicious_procs.append(proc)
                        self._cooldowns[pname] = now
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                pass
                
        if suspicious_procs:
            self._investigate_and_neutralize(suspicious_procs)

    def _investigate_and_neutralize(self, procs: list):
        """Şüpheli işlemleri LLM'e sorar ve gerekirse öldürür."""
        for p in procs:
            try:
                pname = p.info['name']
                pid = p.info['pid']
                
                print(f"[Cyber-Dog] 🐕 Şüpheli işlem tespit edildi: {pname} (PID: {pid}). Gemini'a soruluyor...")
                
                prompt = (
                    f"Bir siber güvenlik uzmanısın. Sistemde şu isimde şüpheli bir process çalışıyor: '{pname}'.\n"
                    f"Bu dosya adının bilinen bir zararlı yazılım (malware, miner, trojan) veya tehlikeli "
                    f"bir araç olma ihtimali nedir? SADECE VE KESİNLİKLE 'THREAT' veya 'SAFE' olarak yanıt ver."
                )
                
                response = query_gemini_reasoning(prompt, model_tier="flash", temperature=0.1)
                
                if "THREAT" in response.upper():
                    print(f"[Cyber-Dog] ⚠️ {pname} TEHDİT OLARAK ONAYLANDI. ETKİSİZ HALE GETİRİLİYOR (KILL)...")
                    try:
                        p.kill() # Terminate process
                        msg = f"Siber Güvenlik Kalkanı, '{pname}' adlı zararlı/şüpheli işlemi yakaladı ve sistemden sildi."
                        
                        # UI'a bildir
                        self._notify(msg)
                                
                    except psutil.AccessDenied:
                        print(f"[Cyber-Dog] ❌ Yetki yok: {pname} öldürülemedi.")
                else:
                    print(f"[Cyber-Dog] ✅ {pname} güvenli (SAFE) olarak işaretlendi.")
                    
            except Exception as e:
                logger.debug(f"[Cyber-Dog] Neutralize hatası: {e}")

cyber_dog = CyberDogEngine()
