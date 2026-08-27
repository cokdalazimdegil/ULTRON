import os
import sys
import time
import asyncio
import random
import logging
from pydub import AudioSegment

import win32com.client

from telethon import TelegramClient
from telethon.tl.functions.phone import CreateGroupCallRequest, DiscardGroupCallRequest
from telethon.tl.functions.channels import GetFullChannelRequest
from telethon.tl.functions.messages import GetFullChatRequest
from telethon.tl.types import InputPeerChannel, InputPeerChat

# FFmpeg için sistem PATH'ine venv Scripts klasörünü ekle
venv_scripts = os.path.join(os.path.dirname(__file__), "..", ".venv", "Scripts")
os.environ["PATH"] += os.pathsep + venv_scripts

from pytgcalls import PyTgCalls
from pytgcalls.types import MediaStream

logger = logging.getLogger("ultron.actions.telegram_caller")

API_ID = "YOUR_TELEGRAM_API_ID" # Int olarak güncelleyin
API_HASH = "YOUR_TELEGRAM_API_HASH"
SESSION_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "ultron_telegram.session")

def tts_to_mp3(text, output_filename="ultron_telegram.wav"):
    """Metni seslendirir ve wav olarak kaydeder."""
    try:
        import pythoncom
        pythoncom.CoInitialize()
        engine = win32com.client.Dispatch("SAPI.SpVoice")
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        
        # 4 = SAFT11kHz16BitMono
        stream.Format.Type = 4 
        if os.path.exists(output_filename):
            os.remove(output_filename)
            
        stream.Open(output_filename, 3, False)
        engine.AudioOutputStream = stream
        engine.Speak(text)
        stream.Close()
        
        return output_filename
    except Exception as e:
        logger.error(f"TTS hatası: {e}")
        return None

async def _async_make_call(chat_name: str, message: str):
    if not os.path.exists(SESSION_PATH):
        logger.error("Telegram oturumu bulunamadı! Lütfen önce giriş yapın.")
        return False

    client = TelegramClient(SESSION_PATH, API_ID, API_HASH)
    call = PyTgCalls(client)
    
    try:
        await client.start()
        
        # Hedef grubu bul
        target_entity = None
        # Önce Süper Grup/Kanal ara
        async for dialog in client.iter_dialogs():
            if dialog.name == chat_name and hasattr(dialog.entity, 'broadcast'):
                target_entity = dialog.entity
                break
        
        # Eğer bulunamazsa normal grup ara
        if not target_entity:
            async for dialog in client.iter_dialogs():
                if dialog.name == chat_name:
                    target_entity = dialog.entity
                    break
                
        if not target_entity:
            logger.error(f"'{chat_name}' isimli grup bulunamadı!")
            return False

        # Ses dosyasını hazırla
        audio_file = tts_to_mp3(message)
        if not audio_file:
            return False
            
        # Eğer aktif sesli sohbet yoksa başlatmaya çalış (Telethon)
        full_chat = None
        try:
            if hasattr(target_entity, 'title'): # Channel/Supergroup
                full_chat = await client(GetFullChannelRequest(channel=target_entity))
                call_obj = full_chat.full_chat.call
            else: # Normal Chat
                full_chat = await client(GetFullChatRequest(chat_id=target_entity.id))
                call_obj = full_chat.full_chat.call
                
            if not call_obj:
                logger.info(f"'{chat_name}' grubunda sesli sohbet başlatılıyor...")
                res = await client(CreateGroupCallRequest(
                    peer=target_entity,
                    random_id=random.randint(0, 0x7fffffff)
                ))
                # Call started
                
        except Exception as e:
            logger.warning(f"Sesli sohbet kontrol/başlatma hatası (Önemsiz olabilir): {e}")

        # PyTgCalls başlat ve sese katıl
        await call.start()
        logger.info("PyTgCalls başlatıldı. Sese katılınıyor...")
        
        # Telegram API kuralları: Normal gruplar negatif, Süper grup/Kanallar -100 ile başlar
        from telethon.utils import get_peer_id
        real_chat_id = get_peer_id(target_entity)
        
        logger.info("Ses çalınıyor...")
        
        # Pydub ile başa 5 saniye boşluk (sessizlik) ekleyelim ki WebRTC bağlanana kadar ses kaybolmasın
        audio = AudioSegment.from_file(audio_file)
        silence = AudioSegment.silent(duration=5000)
        padded_audio = silence + audio
        padded_audio.export(audio_file, format="wav")
        
        duration_sec = len(padded_audio) / 1000.0
        
        await call.play(
            real_chat_id,
            MediaStream(media_path=audio_file)
        )
        
        # Sesin toplam süresi (5 sn boşluk + kendi süresi) + 3 saniye ekstra bekleme
        await asyncio.sleep(duration_sec + 3.0)
        
        # Çağrıyı bitir
        await call.leave_call(real_chat_id)
        logger.info("Arama sonlandırıldı.")
        
    except Exception as e:
        import traceback
        logger.error(f"Telegram arama hatası: {e}\n{traceback.format_exc()}")
    finally:
        await client.disconnect()

def make_telegram_call(message: str, chat_name: str = "ULTRON CORE"):
    """
    Ultron'un Telegram üzerinden belirttiğiniz gruba girip sesli sohbete sesi basması için senkron fonksiyon.
    Arka planda thread içerisinde asenkron loop oluşturarak çalışır.
    """
    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(_async_make_call(chat_name, message))
        loop.close()
        
    import threading
    t = threading.Thread(target=_run, daemon=True, name="TelegramCallThread")
    t.start()
    return f"'{chat_name}' grubuna Telegram sesli araması başlatılıyor..."

