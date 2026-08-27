import urllib.parse
from twilio.rest import Client
import logging

logger = logging.getLogger("ultron.actions.twilio_caller")

# ==========================================
# LÜTFEN BU BİLGİLERİ TWILIO'DAN ALIP DOLDURUN
# ==========================================
TWILIO_ACCOUNT_SID = "YOUR_TWILIO_ACCOUNT_SID"
TWILIO_AUTH_TOKEN = "YOUR_TWILIO_AUTH_TOKEN"
TWILIO_PHONE_NUMBER = "YOUR_TWILIO_PHONE_NUMBER"
TARGET_PHONE_NUMBER = "YOUR_TARGET_PHONE_NUMBER"
# ==========================================

def make_phone_call(message: str):
    """
    Belirtilen metni Twilio üzerinden (Gerçek GSM aramasıyla) okur.
    """
    if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER, TARGET_PHONE_NUMBER]):
        logger.error("Twilio kimlik bilgileri eksik.")
        return "Twilio API bilgileri eksik. Lütfen twilio_caller.py dosyasına bilgileri girin."
        
    try:
        client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        
        # Amazon Polly Türkçe Ses Sentezi (Filiz)
        # Twilio, XML (TwiML) formatında talimat kabul eder.
        # Daha gerçekçi tonlamalar için "Polly.Filiz" veya "Polly.Zeynep" kullanılır.
        twiml = f'<Response><Say language="tr-TR" voice="Polly.Filiz">{message}</Say></Response>'
        
        logger.info(f"📞 [Twilio] Aranıyor: {TARGET_PHONE_NUMBER}...")
        
        call = client.calls.create(
            twiml=twiml,
            to=TARGET_PHONE_NUMBER,
            from_=TWILIO_PHONE_NUMBER
        )
        
        logger.info(f"📞 [Twilio] Arama başlatıldı. Call SID: {call.sid}")
        return f"Arka planda {TARGET_PHONE_NUMBER} numarası Twilio üzerinden başarıyla aranıyor..."
        
    except Exception as e:
        logger.error(f"Twilio Arama Hatası: {e}")
        return f"Twilio Arama Hatası: {e}"
