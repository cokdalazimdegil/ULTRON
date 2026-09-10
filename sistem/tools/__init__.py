"""
ULTRON Araç Tanımları Paketi
Tüm alt modüllerdeki Gemini Live araçlarını derleyip ALL_TOOLS olarak sunar.
"""

from tools.calendar_tools import CALENDAR_TOOLS
from tools.communication_tools import COMMUNICATION_TOOLS
from tools.system_tools import SYSTEM_TOOLS
from tools.media_tools import MEDIA_TOOLS
from tools.smart_home_tools import SMART_HOME_TOOLS
from tools.memory_tools import MEMORY_TOOLS
from tools.agent_tools import AGENT_TOOLS

ALL_TOOLS = (
    CALENDAR_TOOLS
    + COMMUNICATION_TOOLS
    + SYSTEM_TOOLS
    + MEDIA_TOOLS
    + SMART_HOME_TOOLS
    + MEMORY_TOOLS
    + AGENT_TOOLS
)

__all__ = [
    "ALL_TOOLS",
    "CALENDAR_TOOLS",
    "COMMUNICATION_TOOLS",
    "SYSTEM_TOOLS",
    "MEDIA_TOOLS",
    "SMART_HOME_TOOLS",
    "MEMORY_TOOLS",
    "AGENT_TOOLS",
]
