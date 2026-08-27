"""
Google Workspace — Takvim Servisi
─────────────────────────────────
• Yaklaşan etkinlikleri okuma
• Yeni etkinlik oluşturma
"""

import datetime
from typing import Any, List, Dict
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import get_google_credentials

def _get_calendar_service():
    creds = get_google_credentials()
    if not creds:
        raise Exception("Google API kimlik doğrulaması başarısız.")
    return build('calendar', 'v3', credentials=creds)

def get_upcoming_events(days_ahead: int = 1) -> List[Dict[str, Any]]:
    """Belirtilen gün sayısı kadar ileriye dönük etkinlikleri getirir."""
    try:
        service = _get_calendar_service()
        now = datetime.datetime.utcnow().isoformat() + 'Z'
        future = (datetime.datetime.utcnow() + datetime.timedelta(days=days_ahead)).isoformat() + 'Z'
        
        events_result = service.events().list(
            calendarId='primary', timeMin=now, timeMax=future,
            maxResults=15, singleEvents=True,
            orderBy='startTime'
        ).execute()
        
        events = events_result.get('items', [])
        parsed_events = []
        
        for event in events:
            start = event['start'].get('dateTime', event['start'].get('date'))
            parsed_events.append({
                "id": event['id'],
                "summary": event.get('summary', 'İsimsiz Etkinlik'),
                "start": start,
                "link": event.get('htmlLink', '')
            })
            
        return parsed_events
    except HttpError as error:
        return [{"error": str(error)}]
    except Exception as e:
        return [{"error": str(e)}]

def create_calendar_event(title: str, start_time: str, end_time: str, description: str = "") -> str:
    """Yeni etkinlik oluşturur. ISO 8601 formatı beklenir."""
    try:
        service = _get_calendar_service()
        event = {
            'summary': title,
            'description': description,
            'start': {
                'dateTime': start_time,
                'timeZone': 'Europe/Istanbul',
            },
            'end': {
                'dateTime': end_time,
                'timeZone': 'Europe/Istanbul',
            },
        }
        
        event = service.events().insert(calendarId='primary', body=event).execute()
        return f"Etkinlik oluşturuldu: {event.get('htmlLink')}"
    except HttpError as error:
        return f"Takvim oluşturma hatası: {error}"
    except Exception as e:
        return f"Bilinmeyen hata: {e}"
