"""
Google Workspace OAuth 2.0 Doğrulama Modülü
───────────────────────────────────────────
Bu modül Google API'leri (Gmail, Drive, Calendar) için OAuth 2.0 flow'unu yönetir.
İlk çalıştırıldığında tarayıcı açar, yetki alır ve token.json kaydeder.
Sonraki çalışmalarda token'ı kullanır ve gerekirse (refresh_token ile) yeniler.
"""

import os
from pathlib import Path
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

# Kapsamlar (Scopes): E-posta okuma/değiştirme, Drive arama, Takvim okuma/yazma
SCOPES = [
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/drive.readonly",
    "https://www.googleapis.com/auth/calendar"
]

# Paths
WORKSPACE_DIR = Path(__file__).parent
CREDENTIALS_PATH = WORKSPACE_DIR / "credentials.json"
TOKEN_PATH = WORKSPACE_DIR / "token.json"

def get_google_credentials() -> Credentials | None:
    """OAuth 2.0 Credentials nesnesini döndürür. Gerekirse tarayıcıdan yetki alır."""
    creds = None

    # Varsa mevcut token'ı yükle
    if TOKEN_PATH.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)
        except Exception:
            pass

    # Token geçerli değilse veya yoksa
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            try:
                creds.refresh(Request())
            except Exception as e:
                print(f"[Workspace Auth] Token yenilenemedi: {e}")
                creds = None

        if not creds:
            if not CREDENTIALS_PATH.exists():
                print("[Workspace Auth] HATA: credentials.json dosyası bulunamadı!")
                print(f"Lütfen Google Cloud Console'dan indirdiğiniz credentials.json dosyasını şuraya koyun:\n{CREDENTIALS_PATH}")
                return None
                
            try:
                flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
                creds = flow.run_local_server(port=0)
            except Exception as e:
                print(f"[Workspace Auth] OAuth Onay hatası: {e}")
                return None

        # Yeni token'ı kaydet
        if creds:
            with open(TOKEN_PATH, "w") as token:
                token.write(creds.to_json())

    return creds
