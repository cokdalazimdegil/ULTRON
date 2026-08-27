"""
Google Workspace — Gmail Servisi
─────────────────────────────────
• E-postaları ara (Gmail Search Syntax destekler)
• E-posta detayını oku
• Taslak oluştur
"""

import base64
from email.message import EmailMessage
from typing import Any, List, Dict
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

from .auth import get_google_credentials

def _get_gmail_service():
    creds = get_google_credentials()
    if not creds:
        raise Exception("Google API kimlik doğrulaması başarısız.")
    return build('gmail', 'v1', credentials=creds)

def search_emails(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """Verilen sorguya (örn: 'is:unread', 'from:boss@company.com') göre mailleri arar."""
    try:
        service = _get_gmail_service()
        results = service.users().messages().list(userId='me', q=query, maxResults=max_results).execute()
        messages = results.get('messages', [])
        
        parsed_emails = []
        for msg in messages:
            msg_id = msg['id']
            txt = service.users().messages().get(userId='me', id=msg_id, format='metadata', metadataHeaders=['Subject', 'From', 'Date']).execute()
            headers = txt.get('payload', {}).get('headers', [])
            
            subject = next((h['value'] for h in headers if h['name'] == 'Subject'), "Konusuz")
            sender = next((h['value'] for h in headers if h['name'] == 'From'), "Bilinmeyen Gönderici")
            date = next((h['value'] for h in headers if h['name'] == 'Date'), "Bilinmeyen Tarih")
            
            parsed_emails.append({
                "id": msg_id,
                "subject": subject,
                "from": sender,
                "date": date
            })
            
        return parsed_emails
    except HttpError as error:
        return [{"error": str(error)}]
    except Exception as e:
        return [{"error": str(e)}]

def read_email_content(message_id: str) -> str:
    """Belirli bir e-postanın metin gövdesini (snippet veya snippet+body) okur."""
    try:
        service = _get_gmail_service()
        txt = service.users().messages().get(userId='me', id=message_id, format='full').execute()
        snippet = txt.get('snippet', '')
        
        # Gövdeyi okumak için payload'ı çözebiliriz ama snippet çoğu zaman asistan için yeterlidir
        # Çok derin okuma için parça birleştirilebilir.
        return f"Snippet: {snippet}"
    except HttpError as error:
        return f"E-posta okuma hatası: {error}"
    except Exception as e:
        return f"Bilinmeyen hata: {e}"

def send_or_draft_email(to: str, subject: str, body: str, is_draft: bool = True) -> str:
    """E-posta taslağı oluşturur veya gönderir."""
    try:
        service = _get_gmail_service()
        message = EmailMessage()
        message.set_content(body)
        message['To'] = to
        message['From'] = "me"
        message['Subject'] = subject

        encoded_message = base64.urlsafe_b64encode(message.as_bytes()).decode()
        create_message = {'raw': encoded_message}

        if is_draft:
            draft = service.users().drafts().create(userId="me", body={'message': create_message}).execute()
            return f"Taslak başarıyla oluşturuldu! Taslak ID: {draft['id']}"
        else:
            send_message = service.users().messages().send(userId="me", body=create_message).execute()
            return f"E-posta başarıyla gönderildi! Mesaj ID: {send_message['id']}"
            
    except HttpError as error:
        return f"Gönderim/Taslak hatası: {error}"
    except Exception as e:
        return f"Bilinmeyen hata: {e}"
