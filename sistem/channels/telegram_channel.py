"""
ULTRON Telegram Channel — Telegram Bot Kanal Adaptörü (OpenClaw Mimarisi)
─────────────────────────────────────────────────────────────────────────
ULTRON'u Telegram'dan kullanmayı sağlar. Bot token'ı .env veya
app_config.json'daki "telegram_bot_token" anahtarından okunur.

Kurulum:
  1. @BotFather'dan yeni bot oluştur → token'ı kopyala
  2. config/api_keys.json'a ekle: {"telegram_bot_token": "123:ABC..."}
  3. pip install python-telegram-bot

Yetenekler:
  • /start → hoş geldiniz mesajı
  • Metin mesajları → ULTRON'un cevabı
  • Heartbeat bildirimlerini Telegram'a gönderme
"""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Any

from channels import BaseChannel, channel_registry

logger = logging.getLogger("ultron.channels.telegram")


def _get_token() -> str:
    """Telegram bot token'ını config'den okur."""
    try:
        from app_config import get_app_config_value
        token = str(get_app_config_value("telegram_bot_token", "") or "")
        if token:
            return token
    except Exception:
        pass
    import os
    return os.environ.get("TELEGRAM_BOT_TOKEN", "")


class TelegramChannel(BaseChannel):
    """
    Telegram Bot kanal adaptörü.
    python-telegram-bot kütüphanesini kullanır.
    """

    name = "telegram"

    def __init__(self):
        super().__init__()
        self._app = None
        self._thread: threading.Thread | None = None
        self._chat_ids: set[int] = set()  # Mesaj gönderilecek chat ID'leri
        self._loop: asyncio.AbstractEventLoop | None = None

    def start(self) -> None:
        token = _get_token()
        if not token:
            logger.info("[TelegramChannel] Bot token bulunamadı — Telegram kanalı devre dışı.")
            return

        try:
            from telegram.ext import Application, MessageHandler, CommandHandler, filters
        except ImportError:
            logger.warning(
                "[TelegramChannel] python-telegram-bot yüklü değil — "
                "pip install python-telegram-bot"
            )
            return

        self._thread = threading.Thread(
            target=self._run_bot,
            name="TelegramChannel",
            daemon=True
        )
        self._thread.start()
        self._running = True
        logger.info("[TelegramChannel] 📱 Telegram bot kanalı başlatıldı.")

    def stop(self) -> None:
        self._running = False
        if self._app:
            try:
                asyncio.run_coroutine_threadsafe(self._app.stop(), self._loop)
            except Exception:
                pass

    def _run_bot(self) -> None:
        """Telegram bot'unu ayrı thread'de çalıştırır."""
        try:
            from telegram.ext import Application, MessageHandler, CommandHandler, filters
            import asyncio as _asyncio

            self._loop = _asyncio.new_event_loop()
            _asyncio.set_event_loop(self._loop)

            token = _get_token()
            self._app = Application.builder().token(token).build()

            async def start_cmd(update, context):
                chat_id = update.effective_chat.id
                self._chat_ids.add(chat_id)
                await update.message.reply_text(
                    "⚡ U.L.T.R.O.N bağlantısı kuruldu. Mesajını gönderebilirsin."
                )
                logger.info(f"[TelegramChannel] Yeni kullanıcı bağlandı: {chat_id}")

            async def on_message(update, context):
                chat_id = update.effective_chat.id
                self._chat_ids.add(chat_id)
                text = update.message.text or ""
                sender = str(update.effective_user.username or chat_id)

                # Gelen mesajı Gateway'e ilet
                self.on_incoming(text, sender)

                # Kullanıcıya işleniyor bildirimi
                await update.message.reply_text("⏳ İşleniyor...")

            self._app.add_handler(CommandHandler("start", start_cmd))
            self._app.add_handler(
                MessageHandler(filters.TEXT & ~filters.COMMAND, on_message)
            )

            logger.info("[TelegramChannel] Bot polling başlatıldı.")
            self._loop.run_until_complete(
                self._app.run_polling(close_loop=False)
            )
        except Exception as exc:
            logger.error(f"[TelegramChannel] Bot çalıştırma hatası: {exc}")

    async def send_message(self, text: str, metadata: dict | None = None) -> bool:
        """Kayıtlı tüm chat ID'lerine mesaj gönderir."""
        if not self._app or not self._chat_ids:
            return False

        success = False
        for chat_id in list(self._chat_ids):
            try:
                await self._app.bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="HTML"
                )
                success = True
            except Exception as exc:
                logger.warning(f"[TelegramChannel] Gönderim hatası ({chat_id}): {exc}")
        return success

    def reply_to_incoming(self, chat_id: int, text: str) -> None:
        """Gelen bir mesaja yanıt verir (ChannelRegistry'den callback olarak çağrılır)."""
        if self._app and self._loop:
            asyncio.run_coroutine_threadsafe(
                self._app.bot.send_message(chat_id=chat_id, text=text),
                self._loop
            )


# Singleton
telegram_channel = TelegramChannel()
channel_registry.register(telegram_channel)
