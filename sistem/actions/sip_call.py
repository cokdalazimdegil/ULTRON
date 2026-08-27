import os
import time
import wave
import audioop
import threading
import win32com.client
from pyVoIP.VoIP import VoIPPhone, CallState

import logging
logger = logging.getLogger("ultron.actions.sip_call")

SIP_DOMAIN = "sip2sip.info"
SIP_PORT = 5060
SIP_USER_ULTRON = "ultron58"
SIP_PASS_ULTRON = "Sivas5866."
TARGET_URI = "sip:nca@sip2sip.info"

def tts_to_pcmu(text, output_filename="ultron_call.wav"):
    """Metni sese cevirir, .wav kaydeder ve PCMU byte dizisine donusturur."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
        engine = win32com.client.Dispatch("SAPI.SpVoice")
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        
        # 6 = SAFT8kHz16BitMono
        stream.Format.Type = 6
        if os.path.exists(output_filename):
            os.remove(output_filename)
            
        stream.Open(output_filename, 3, False)
        engine.AudioOutputStream = stream
        engine.Speak(text)
        stream.Close()
        
        # Oku ve PCMU'ya (ulaw) cevir
        with wave.open(output_filename, 'rb') as wf:
            frames = wf.readframes(wf.getnframes())
            pcmu_data = audioop.lin2ulaw(frames, 2)
            
        return pcmu_data
    except Exception as e:
        logger.error(f"TTS to PCMU hatası: {e}")
        return b""

def make_sip_call(text: str):
    """
    Belirtilen metni okumak uzere kullaniciyi SIP uzerinden arar.
    Arka planda calisir, arama bitince kendini kapatir.
    """
    def _call_thread():
        pcmu_data = tts_to_pcmu(text)
        if not pcmu_data:
            return
            
        phone = VoIPPhone(SIP_DOMAIN, SIP_PORT, SIP_USER_ULTRON, SIP_PASS_ULTRON, sipPort=5061)
        try:
            phone.start()
            logger.info(f"📞 [SIP] Aranıyor: {TARGET_URI}...")
            
            call = phone.call(TARGET_URI)
            
            # Bekleme döngüsü (maks 30 saniye)
            wait_time = 0
            while call.state != CallState.ANSWERED and wait_time < 30:
                time.sleep(0.5)
                wait_time += 0.5
                if call.state == CallState.CLOSED:
                    logger.info("📞 [SIP] Arama reddedildi veya düştü.")
                    break
                    
            if call.state == CallState.ANSWERED:
                logger.info("📞 [SIP] Arama cevaplandı! Ses gönderiliyor...")
                call.write_audio(pcmu_data)
                
                # Sesin uzunluğu kadar bekle (8000 Hz, 8-bit = saniyede 8000 byte)
                duration_sec = len(pcmu_data) / 8000.0
                time.sleep(duration_sec + 1.0)
                
                call.hangup()
                logger.info("📞 [SIP] Görüşme bitti, kapatıldı.")
                
        except Exception as e:
            import traceback
            logger.error(f"SIP Arama Hatası: {e}\n{traceback.format_exc()}")
        finally:
            phone.stop()

    threading.Thread(target=_call_thread, name="SIP_Caller_Thread", daemon=True).start()
    return f"Arka planda {TARGET_URI} adresi aranıyor..."
