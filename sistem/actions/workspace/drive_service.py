"""
Google Workspace — Drive Servisi
─────────────────────────────────
• Dosya arama
• Dosya metnini okuma
• Dosya yükleme
"""

import io
from typing import Any, List, Dict
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload

from .auth import get_google_credentials

def _get_drive_service():
    creds = get_google_credentials()
    if not creds:
        raise Exception("Google API kimlik doğrulaması başarısız.")
    return build('drive', 'v3', credentials=creds)

def search_drive_files(name_query: str, mime_type: str = None) -> List[Dict[str, Any]]:
    """Drive'da dosya arar."""
    try:
        service = _get_drive_service()
        q = f"name contains '{name_query}' and trashed = false"
        if mime_type:
            q += f" and mimeType='{mime_type}'"
            
        results = service.files().list(
            q=q,
            pageSize=10,
            fields="nextPageToken, files(id, name, mimeType, modifiedTime)"
        ).execute()
        
        return results.get('files', [])
    except HttpError as error:
        return [{"error": str(error)}]
    except Exception as e:
        return [{"error": str(e)}]

def read_drive_file(file_id: str) -> str:
    """Dosya metnini döner (GDocs için dışa aktarır)."""
    try:
        service = _get_drive_service()
        file_meta = service.files().get(fileId=file_id).execute()
        mime_type = file_meta.get('mimeType', '')
        
        if 'application/vnd.google-apps.document' in mime_type:
            # Google Docs -> Plain text
            request = service.files().export_media(fileId=file_id, mimeType='text/plain')
        else:
            # Diğer dosyalar
            request = service.files().get_media(fileId=file_id)
            
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
            
        return fh.getvalue().decode('utf-8', errors='ignore')
    except Exception as e:
        return f"Okuma hatası: {e}"

def upload_file_to_drive(file_path: str, folder_name: str = "ULTRON") -> str:
    """Yerel dosyayı Drive'a yükler."""
    try:
        service = _get_drive_service()
        # Basit yükleme (klasör kontrolü vs eklenebilir)
        import os
        file_name = os.path.basename(file_path)
        file_metadata = {'name': file_name}
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(body=file_metadata, media_body=media, fields='id').execute()
        return f"Dosya başarıyla yüklendi. Dosya ID: {file.get('id')}"
    except Exception as e:
        return f"Yükleme hatası: {e}"
