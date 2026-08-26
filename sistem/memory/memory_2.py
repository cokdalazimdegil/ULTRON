"""
ULTRON Intelligent Memory 2.0 Subsystem (RAG & Semantic Tiered Storage)
"""

from __future__ import annotations

import json
import logging
import re
import threading
import time
import unicodedata
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from app_paths import data_path

logger = logging.getLogger("ultron.memory.memory_2")

MEMORY_V2_FILE = data_path("memory", "memory_v2.json")


class MemoryTier(str, Enum):
    USER_MEMORY     = "USER_MEMORY"       # Kimlik, aile, tercihler
    WORKING_MEMORY  = "WORKING_MEMORY"    # Aktif oturum ve görev bağlamı
    SEMANTIC_MEMORY = "SEMANTIC_MEMORY"   # Kalıcı öğrenilmiş gerçekler ve bilgiler
    EPISODIC_MEMORY = "EPISODIC_MEMORY"   # Olay günlükleri ve geçmiş etkileşimler


@dataclass
class MemoryEntry:
    key: str
    content: str
    tier: MemoryTier = MemoryTier.SEMANTIC_MEMORY
    importance: float = 0.5
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "content": self.content,
            "tier": self.tier.value,
            "importance": self.importance,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        tier_val = data.get("tier", MemoryTier.SEMANTIC_MEMORY.value)
        try:
            tier = MemoryTier(tier_val)
        except ValueError:
            tier = MemoryTier.SEMANTIC_MEMORY
        return cls(
            key=data.get("key", ""),
            content=data.get("content", ""),
            tier=tier,
            importance=float(data.get("importance", 0.5)),
            timestamp=float(data.get("timestamp", time.time())),
            metadata=data.get("metadata", {}),
        )


class IntelligentMemoryManager:
    """Çok katmanlı, akıllı bellek yöneticisi."""

    def __init__(self):
        self._lock = threading.RLock()
        self._entries: dict[str, MemoryEntry] = {}
        self._load()

    def _load(self) -> None:
        with self._lock:
            try:
                if MEMORY_V2_FILE.exists():
                    raw = json.loads(MEMORY_V2_FILE.read_text(encoding="utf-8"))
                    if isinstance(raw, list):
                        for item in raw:
                            entry = MemoryEntry.from_dict(item)
                            self._entries[entry.key] = entry
                    elif isinstance(raw, dict):
                        for k, v in raw.items():
                            if isinstance(v, dict):
                                entry = MemoryEntry.from_dict(v)
                                self._entries[k] = entry
            except Exception as e:
                logger.warning(f"Memory v2 yükleme hatası: {e}")

    def _save(self) -> None:
        with self._lock:
            try:
                MEMORY_V2_FILE.parent.mkdir(parents=True, exist_ok=True)
                data = [e.to_dict() for e in self._entries.values()]
                MEMORY_V2_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.error(f"Memory v2 kaydetme hatası: {e}")

    def store(self, key: str, content: str, tier: MemoryTier = MemoryTier.SEMANTIC_MEMORY, importance: float = 0.5, metadata: dict[str, Any] | None = None) -> None:
        with self._lock:
            entry = MemoryEntry(
                key=key.strip(),
                content=content.strip(),
                tier=tier,
                importance=importance,
                timestamp=time.time(),
                metadata=metadata or {},
            )
            self._entries[entry.key] = entry
            self._save()

    def retrieve(self, key: str) -> Optional[MemoryEntry]:
        with self._lock:
            return self._entries.get(key.strip())

    def delete(self, key: str) -> bool:
        with self._lock:
            if key.strip() in self._entries:
                del self._entries[key.strip()]
                self._save()
                return True
            return False

    def search(self, query: str, limit: int = 5, min_score: float = 0.2) -> list[MemoryEntry]:
        with self._lock:
            q_terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 1]
            if not q_terms:
                return list(self._entries.values())[:limit]

            scored: list[tuple[float, MemoryEntry]] = []
            for entry in self._entries.values():
                content_lower = f"{entry.key} {entry.content}".lower()
                matches = sum(1 for t in q_terms if t in content_lower)
                score = matches / max(1, len(q_terms))
                score += entry.importance * 0.2
                if score >= min_score:
                    scored.append((score, entry))

            scored.sort(key=lambda x: x[0], reverse=True)
            return [e for _, e in scored[:limit]]

    def get_tier(self, tier: MemoryTier) -> list[MemoryEntry]:
        with self._lock:
            return [e for e in self._entries.values() if e.tier == tier]

    def format_for_prompt(self, max_entries: int = 8) -> str:
        with self._lock:
            if not self._entries:
                return ""
            sorted_entries = sorted(self._entries.values(), key=lambda e: (e.importance, e.timestamp), reverse=True)[:max_entries]
            lines = ["[ÖĞRENİLMİŞ HAFIZA & BİLGİLER]"]
            for e in sorted_entries:
                lines.append(f"• {e.key}: {e.content}")
            return "\n".join(lines)


# Global Singleton
intelligent_memory = IntelligentMemoryManager()
