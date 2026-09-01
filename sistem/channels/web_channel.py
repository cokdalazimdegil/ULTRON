"""
ULTRON Web Channel — WebSocket Kanal Adaptörü (OpenClaw Mimarisi)
──────────────────────────────────────────────────────────────────
Mevcut server.py'nin web_clients setini Channel mimarisine adapte eder.
server.py hâlâ WebSocket bağlantılarını yönetir; bu adaptör sadece
ChannelRegistry ile köprü kurar.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from channels import BaseChannel, channel_registry

logger = logging.getLogger("ultron.channels.web")


class WebChannel(BaseChannel):
    """
    Web UI kanalı.
    server.py'nin web_clients set'inden beslenecek şekilde tasarlanmıştır.
    Gerçek WebSocket gönderimi server.py'de kalır — bu sınıf sadece
    ChannelRegistry köprüsü sağlar.
    """

    name = "web"

    def __init__(self):
        super().__init__()
        self._web_clients_ref = None  # server.py'nin web_clients set'ine referans

    def attach_web_clients(self, web_clients_set) -> None:
        """server.py'nin web_clients set'ine referans bağlar."""
        self._web_clients_ref = web_clients_set

    def start(self) -> None:
        self._running = True
        logger.info("[WebChannel] Web kanalı aktif.")

    def stop(self) -> None:
        self._running = False

    async def send_message(self, text: str, metadata: dict | None = None) -> bool:
        """Bağlı tüm web istemcilerine mesaj gönderir."""
        if not self._web_clients_ref:
            return False

        sent = False
        msg_type = (metadata or {}).get("type", "heartbeat_task")
        payload = {"type": msg_type, "message": text}

        for client in list(self._web_clients_ref):
            try:
                import json as _json
                await client.ws.send_text(_json.dumps(payload))
                sent = True
            except Exception:
                pass
        return sent

    def notify_incoming(self, text: str, sender: str = "web_user") -> None:
        """Web'den gelen mesajı registry'ye iletir."""
        self.on_incoming(text, sender)


# Singleton
web_channel = WebChannel()
channel_registry.register(web_channel)
