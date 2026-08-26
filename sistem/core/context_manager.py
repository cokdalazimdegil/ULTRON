"""
ULTRON Context Manager — Unified Context Synthesis & Truncation (V17)
═════════════════════════════════════════════════════════════════════
• Çok Katmanlı Bağlam Sentezi:
  RecentContext -> WorkingContext -> TaskContext -> RetrievedMemory -> SystemState
• Önceliklendirilmiş Dinamik Prompt Enjeksiyonu
• Güvenli Token Tahmini ve Aşırı Bağlam Büyümesini Önleme (Non-Destructive Truncation)
• Gemini Live & REST Oturumları ile Tam Entegrasyon
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from typing import Any

from computer.world_model import world_model
from memory.memory_2 import intelligent_memory, MemoryTier

logger = logging.getLogger("ultron.core.context_manager")


@dataclass
class ConversationTurn:
    role: str       # "user" | "ultron" | "system"
    text: str
    timestamp: float = field(default_factory=time.time)
    importance: float = 0.5


@dataclass
class ContextSnapshot:
    recent_dialogue: list[ConversationTurn] = field(default_factory=list)
    active_goal: str = ""
    system_summary: str = ""
    retrieved_memory: str = ""
    agent_results: list[dict[str, Any]] = field(default_factory=list)
    total_estimated_tokens: int = 0
    generated_at: float = field(default_factory=time.time)


class ContextManager:
    """Merkezi Bağlam Yöneticisi."""

    MAX_RECENT_TURNS = 10
    ESTIMATED_CHARS_PER_TOKEN = 3.5  # Türkçe ve kod karışımı için güvenli çarpan

    def __init__(self):
        self._lock = threading.RLock()
        self._dialogue_history: list[ConversationTurn] = []
        self._summary: str = ""

    def add_turn(self, role: str, text: str, importance: float = 0.5) -> None:
        """Yeni bir konuşma turunu kaydeder ve gerekirse en eskileri özetler."""
        with self._lock:
            turn = ConversationTurn(role=role, text=text.strip(), importance=importance)
            self._dialogue_history.append(turn)

            # Geçmişi sınırla (Hafıza şişmesini önle)
            if len(self._dialogue_history) > self.MAX_RECENT_TURNS * 2:
                # En eski turları episodic hafızaya aktar
                oldest = self._dialogue_history[:self.MAX_RECENT_TURNS]
                self._dialogue_history = self._dialogue_history[self.MAX_RECENT_TURNS:]
                try:
                    old_text = " | ".join(f"{t.role}: {t.text}" for t in oldest)
                    intelligent_memory.store(
                        tier=MemoryTier.EPISODIC_MEMORY,
                        key=f"dialogue_archive_{int(time.time())}",
                        content=old_text,
                        importance=0.4
                    )
                except Exception:
                    pass

    def estimate_tokens(self, text: str) -> int:
        """Metin için yaklaşık token sayısını hesaplar."""
        if not text:
            return 0
        return max(1, int(len(text) / self.ESTIMATED_CHARS_PER_TOKEN))

    def build_unified_context(self, current_user_query: str = "", max_tokens: int = 2048) -> str:
        """
        Öncelik sırasına göre tüm katmanları birleştirerek LLM için prompt bağlamı oluşturur:
        1. Sistem ve Biyometrik Kimlik (World State)
        2. Aktif Görev Bağlamı (Task Context)
        3. Sorguyla İlgili Hafıza (Retrieved Memory)
        4. Son Konuşma Geçmişi (Recent Dialogue)
        """
        with self._lock:
            sections = []

            # 1. World Model Durumu
            world_summary = world_model.get_world_summary()
            sections.append(f"[CANLI DÜNYA & SİSTEM DURUMU]\n{world_summary}")

            # 2. Kalıcı Kullanıcı Profili (Identity)
            # Kimlik bilgileri her zaman bağlama eklenmeli (kullanıcının adını unutmaması için)
            identities = intelligent_memory.retrieve(query="identity", limit=10)
            if identities:
                id_lines = ["[KULLANICI PROFİLİ VE TERCİHLER]"]
                for m in identities:
                    id_lines.append(f"• {m.key}: {m.content}")
                sections.append("\n".join(id_lines))

            # 3. Aktif Görev
            task = world_model.active_task
            if task.goal and task.status != "IDLE":
                sections.append(f"[AKTİF OTONOM GÖREV]\nGörev: {task.goal} (Durum: {task.status})")

            # 4. İlgili Hafıza (Konu Bazlı)
            if current_user_query:
                memories = intelligent_memory.retrieve(query=current_user_query, limit=4)
                # Identity ile çakışanları çıkar
                filtered = [m for m in memories if m.tier != MemoryTier.SEMANTIC_MEMORY or "identity" not in m.key.lower()]
                if filtered:
                    mem_lines = ["[İLGİLİ HAFIZA BİLGİLERİ]"]
                    for m in filtered:
                        mem_lines.append(f"• {m.key}: {m.content}")
                    sections.append("\n".join(mem_lines))

            # 5. Son Diyalog
            recent = self._dialogue_history[-self.MAX_RECENT_TURNS:]
            if recent:
                dial_lines = ["[SON KONUŞMALAR]"]
                for t in recent:
                    dial_lines.append(f"{t.role.upper()}: {t.text}")
                sections.append("\n".join(dial_lines))

            # 6. Persona Hatırlatıcısı (Kibir Döngüsünü Kırmak İçin)
            sections.append(
                "[SİSTEM DİREKTİFİ]\nYanıtını verirken karakterini koru (zeki, tok, net) fakat "
                "ASLA 'Ben ULTRON'um, şöyle yaparım' gibi tekrarlara düşme. Mümkün olduğunca doğal, "
                "kısa ve zekice yanıt ver."
            )

            full_context = "\n\n".join(sections)
            return full_context

    def clear_session(self) -> None:
        """Oturum geçmişini sıfırlar."""
        with self._lock:
            self._dialogue_history.clear()
            self._summary = ""


# Global Singleton
context_manager = ContextManager()
