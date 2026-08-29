"""
ULTRON Skill Base — Dinamik Plugin Sistemi
─────────────────────────────────────────
Her skill (yetenek), bu abstract sınıfı miras alır.
skill.yaml okunarak Gemini'a araç tanımı olarak sunulur.
handler.py execute() fonksiyonu ile araç çalıştırılır.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class SkillBase(ABC):
    """Her skill bu sınıfı implement eder."""

    # Skill meta verisi — skill.yaml'dan doldurulur
    name: str = ""
    description: str = ""
    parameters: dict = {}

    @abstractmethod
    def execute(self, args: dict) -> str:
        """
        Aracı çalıştırır.
        Args: Gemini'dan gelen parametre sözlüğü.
        Returns: Kullanıcıya/Gemini'ya dönen sonuç string'i.
        """
        ...

    def to_tool_declaration(self) -> dict:
        """Gemini Live araç tanım formatına dönüştürür."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
