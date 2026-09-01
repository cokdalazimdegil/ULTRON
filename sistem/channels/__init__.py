"""
ULTRON Channel Adaptörleri — Temel Kanal Sınıfı (OpenClaw Mimarisi)
────────────────────────────────────────────────────────────────────
Her iletişim kanalı (Web UI, Telegram, WhatsApp vb.) bu soyut sınıfı
implemente eder. Gateway (server.py) hangi kanalların bağlı olduğunu
bilmek zorunda değildir — sadece ChannelRegistry üzerinden mesaj yayar.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger("ultron.channels")


class BaseChannel(ABC):
    """Tüm iletişim kanallarının temel sınıfı."""

    name: str = "base"
    enabled: bool = True

    def __init__(self):
        self._running = False

    @abstractmethod
    def start(self) -> None:
        """Kanalı başlatır (bağlantı kur, dinlemeye başla)."""
        ...

    @abstractmethod
    def stop(self) -> None:
        """Kanalı durdurur."""
        ...

    @abstractmethod
    async def send_message(self, text: str, metadata: dict | None = None) -> bool:
        """
        Kanala mesaj gönderir.

        Args:
            text:     Gönderilecek metin
            metadata: Kanal'a özel ek parametreler

        Returns:
            True → başarılı, False → başarısız
        """
        ...

    def on_incoming(self, text: str, sender: str = "unknown"):
        """
        Kanaldan gelen mesajı Gateway'e iletmek için çağrılır.
        Alt sınıflar bu metodu override etmez — Registry üzerinden çalışır.
        """
        from channels import channel_registry
        channel_registry.dispatch_incoming(text, sender, channel=self.name)

    def is_running(self) -> bool:
        return self._running


class ChannelRegistry:
    """
    Tüm aktif kanalları merkezi olarak yönetir.
    server.py (Gateway) bu registry üzerinden mesaj yayar.
    """

    def __init__(self):
        self._channels: dict[str, BaseChannel] = {}
        self._incoming_handlers: list[Any] = []

    def register(self, channel: BaseChannel) -> None:
        """Yeni bir kanal kaydeder."""
        self._channels[channel.name] = channel
        logger.info(f"[ChannelRegistry] Kanal kayıtlı: {channel.name}")

    def unregister(self, name: str) -> None:
        self._channels.pop(name, None)

    def get(self, name: str) -> BaseChannel | None:
        return self._channels.get(name)

    def all_channels(self) -> list[BaseChannel]:
        return list(self._channels.values())

    def on_incoming(self, handler) -> None:
        """
        Herhangi bir kanaldan gelen mesajı alacak callback kaydeder.
        handler(text: str, sender: str, channel: str) şeklinde çağrılır.
        """
        self._incoming_handlers.append(handler)

    def dispatch_incoming(self, text: str, sender: str, channel: str) -> None:
        """Gelen mesajı tüm handler'lara dağıtır."""
        for handler in self._incoming_handlers:
            try:
                handler(text, sender, channel)
            except Exception as exc:
                logger.error(f"[ChannelRegistry] Incoming handler hatası: {exc}")

    async def broadcast(self, text: str, exclude: list[str] | None = None) -> None:
        """Tüm aktif kanallara mesaj gönderir."""
        exclude = exclude or []
        for name, channel in self._channels.items():
            if name in exclude:
                continue
            if not channel.is_running():
                continue
            try:
                await channel.send_message(text)
            except Exception as exc:
                logger.error(f"[ChannelRegistry] {name} kanal gönderim hatası: {exc}")

    def start_all(self) -> None:
        """Tüm kayıtlı kanalları başlatır."""
        for channel in self._channels.values():
            if channel.enabled:
                try:
                    channel.start()
                    logger.info(f"[ChannelRegistry] {channel.name} başlatıldı.")
                except Exception as exc:
                    logger.error(f"[ChannelRegistry] {channel.name} başlatılamadı: {exc}")

    def stop_all(self) -> None:
        """Tüm kanalları durdurur."""
        for channel in self._channels.values():
            try:
                channel.stop()
            except Exception:
                pass


# Singleton
channel_registry = ChannelRegistry()
