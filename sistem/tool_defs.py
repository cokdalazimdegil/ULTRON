"""
ULTRON — Gemini Live Araç (Tool) Tanımları Mimarisi (Facade)
Masaüstü (main.py), web sunucusu (jarvis_web/server.py) ve otonom ajan ağı ortak kullanır.
Tüm araçlar sistem/tools/ altındaki modüllerde kategorize edilmiştir.
"""

from tools import (
    ALL_TOOLS,
    CALENDAR_TOOLS,
    COMMUNICATION_TOOLS,
    SYSTEM_TOOLS,
    MEDIA_TOOLS,
    SMART_HOME_TOOLS,
    MEMORY_TOOLS,
    AGENT_TOOLS,
)

TOOL_DECLARATIONS = ALL_TOOLS

__all__ = [
    "TOOL_DECLARATIONS",
    "ALL_TOOLS",
    "CALENDAR_TOOLS",
    "COMMUNICATION_TOOLS",
    "SYSTEM_TOOLS",
    "MEDIA_TOOLS",
    "SMART_HOME_TOOLS",
    "MEMORY_TOOLS",
    "AGENT_TOOLS",
]
