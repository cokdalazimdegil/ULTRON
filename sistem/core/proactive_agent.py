"""
Google Workspace Proaktif İzleme Motoru
──────────────────────────────────────
• Arka planda çalışır (Daemon Thread).
• 5 dakikada bir Takvim'i ve okunmamış Gmail mesajlarını tarar.
• Yaklaşan toplantıları veya "Önemli" işaretli e-postaları 
  kullanıcıya (UI + Ses) otonom olarak bildirir.
"""

import time
import threading
import logging
from typing import Callable, Optional

from actions.workspace.gmail_service import search_emails
from actions.workspace.calendar_service import get_upcoming_events
from actions.tts import speak_text

logger = logging.getLogger("ultron.core.proactive_workspace")

class ProactiveWorkspaceAgent:
    def __init__(self, check_interval_sec: int = 300): # 5 dakika
        self.interval = check_interval_sec
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._seen_event_ids = set()
        self._seen_email_ids = set()
    def _notify(self, text: str):
        from core.event_bus import bus
        bus.publish("ui_alert", f"🔔 [WORKSPACE ASİSTANI]: {text}")
        
    def start(self):
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="WorkspaceWatcher", daemon=True)
        self._thread.start()
        logger.info("[Workspace Agent] 🕵️‍♂️ Proaktif Google Workspace izleyicisi devrede.")
        
    def stop(self):
        self._running = False
        
    def _loop(self):
        while self._running:
            try:
                self._check_calendar()
                self._check_emails()
            except Exception as e:
                logger.debug(f"[Workspace Agent] Hata: {e}")
            time.sleep(self.interval)
            
    def _check_calendar(self):
        # Sadece bugünkü etkinliklere bak
        events = get_upcoming_events(days_ahead=0)
        if isinstance(events, list) and not events and not "error" in events[0]:
            pass
            
        import datetime
        now = datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc)
        
        for e in events:
            if "error" in e: continue
            
            e_id = e.get("id")
            if e_id in self._seen_event_ids:
                continue
                
            start_str = e.get("start")
            if not start_str: continue
            
            try:
                # ISO 8601 parsing
                event_time = datetime.datetime.fromisoformat(start_str.replace("Z", "+00:00"))
                diff_minutes = (event_time - now).total_seconds() / 60.0
                
                # 15 dakikadan az kaldıysa uyar
                if 0 < diff_minutes <= 15:
                    self._seen_event_ids.add(e_id)
                    title = e.get("summary")
                    msg = f"Hatırlatma: '{title}' adlı toplantınızın başlamasına yaklaşık {int(diff_minutes)} dakika kaldı."
                    print(f"[Workspace Agent] 🗓️ {msg}")
                    self._notify(f"🗓️ {msg}")
            except Exception:
                pass
                
    def _check_emails(self):
        # Son 2 gündeki okunmamış önemli mailler (Eskileri yeni sanmaması için)
        emails = search_emails(query="is:unread is:important newer_than:2d", max_results=3)
        if isinstance(emails, list) and len(emails) > 0 and "error" not in emails[0]:
            for mail in emails:
                m_id = mail.get("id")
                if m_id in self._seen_email_ids:
                    continue
                
                self._seen_email_ids.add(m_id)
                sender = mail.get("from", "Bilinmeyen")
                subject = mail.get("subject", "Konusuz")
                
                msg = f"Yeni bir önemli e-posta aldınız. Gönderen: {sender}. Konu: {subject}."
                print(f"[Workspace Agent] 📧 {msg}")
                self._notify(f"📧 {msg}")

workspace_agent = ProactiveWorkspaceAgent()
