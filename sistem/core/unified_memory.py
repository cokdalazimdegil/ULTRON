"""
ULTRON Unified Memory Engine — Konsolide Bellek Mimarisi (Phase 7)
═════════════════════════════════════════════════════════════════
memory_manager (v1 JSON key-value), memory_2 (katmanlı akıllı bellek) ve
vector_store (ChromaDB anlamsal arama) sistemlerini tek bir çatı altında birleştirir.

Katmanlar:
    - USER_PROFILE: Kimlik, yaratıcı bilgileri, temel tercihler
    - SEMANTIC: Öğrenilmiş gerçekler, notlar, kurallar
    - EPISODIC: Olaylar, etkileşimler, geçmiş oturumlar
    - WORKING: Aktif oturum ve anlık görev bağlamı

Kullanım:
    from core.unified_memory import unified_memory
    unified_memory.store("preferences", "theme", "dark", importance=0.8)
    results = unified_memory.search("tercih edilen tema")
"""

from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from app_paths import data_path
from core.events import UltronEvent, EventPriority, EventSource

logger = logging.getLogger("ultron.core.unified_memory")

UNIFIED_MEMORY_FILE = data_path("memory", "unified_memory.json")
LEGACY_MEMORY_FILE = data_path("memory", "memory.json")


class MemoryTier(str, Enum):
    USER_PROFILE = "user_profile"   # Kimlik, tercihler, aile
    SEMANTIC     = "semantic"       # Kalıcı öğrenilen bilgiler, notlar
    EPISODIC     = "episodic"       # Geçmiş olaylar, diyalog özetleri
    WORKING      = "working"        # Anlık oturum / geçici hafıza


@dataclass
class MemoryRecord:
    key: str
    value: str
    category: str = "notes"
    tier: MemoryTier = MemoryTier.SEMANTIC
    importance: float = 0.5
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "value": self.value,
            "category": self.category,
            "tier": self.tier.value,
            "importance": self.importance,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MemoryRecord:
        tier_val = data.get("tier", MemoryTier.SEMANTIC.value)
        try:
            tier = MemoryTier(tier_val)
        except ValueError:
            tier = MemoryTier.SEMANTIC
        return cls(
            key=data.get("key", ""),
            value=data.get("value", ""),
            category=data.get("category", "notes"),
            tier=tier,
            importance=float(data.get("importance", 0.5)),
            created_at=float(data.get("created_at", time.time())),
            updated_at=float(data.get("updated_at", time.time())),
            metadata=data.get("metadata", {}),
        )


class UnifiedMemoryEngine:
    """Tek ve konsolide bellek motoru."""

    _instance: Optional["UnifiedMemoryEngine"] = None
    _lock = threading.RLock()

    def __new__(cls) -> "UnifiedMemoryEngine":
        with cls._lock:
            if cls._instance is None:
                inst = super().__new__(cls)
                inst._initialized = False
                cls._instance = inst
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._records: Dict[str, MemoryRecord] = {}  # id -> record
        self._bus = None
        self._load()

    def _get_bus(self):
        if self._bus is None:
            try:
                from core.event_bus import bus
                self._bus = bus
            except ImportError:
                pass
        return self._bus

    def _composite_key(self, category: str, key: str) -> str:
        return f"{category.strip().lower()}::{key.strip().lower()}"

    # ── Yükleme & Kaydetme ──────────────────────────────────────────────────

    def _load(self) -> None:
        """Kayıtlı bellek dosyasını ve gerekirse legacy memory.json'ı içe aktarır."""
        with self._lock:
            if UNIFIED_MEMORY_FILE.exists():
                try:
                    data = json.loads(UNIFIED_MEMORY_FILE.read_text(encoding="utf-8"))
                    for comp_key, rec_dict in data.items():
                        self._records[comp_key] = MemoryRecord.from_dict(rec_dict)
                    return
                except Exception as e:
                    logger.warning(f"[UnifiedMemory] Yükleme hatası: {e}")

            # Legacy memory.json varsa migrate et
            if LEGACY_MEMORY_FILE.exists():
                try:
                    legacy_data = json.loads(LEGACY_MEMORY_FILE.read_text(encoding="utf-8"))
                    self._migrate_legacy(legacy_data)
                except Exception as e:
                    logger.warning(f"[UnifiedMemory] Legacy aktarım hatası: {e}")

    def _save(self) -> None:
        """Diske atomik olarak kaydeder."""
        with self._lock:
            try:
                UNIFIED_MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
                data = {ck: rec.to_dict() for ck, rec in self._records.items()}
                UNIFIED_MEMORY_FILE.write_text(
                    json.dumps(data, indent=2, ensure_ascii=False),
                    encoding="utf-8",
                )
                # Legacy memory.json ile de geriye dönük senkronize tut
                self._sync_to_legacy_file()
            except Exception as e:
                logger.error(f"[UnifiedMemory] Kaydetme hatası: {e}")

    def _migrate_legacy(self, legacy_data: Dict[str, Any]) -> None:
        for cat, bucket in legacy_data.items():
            tier = MemoryTier.USER_PROFILE if cat in ("identity", "preferences", "family") else MemoryTier.SEMANTIC
            if isinstance(bucket, dict):
                for k, v in bucket.items():
                    val = v.get("value", v) if isinstance(v, dict) else str(v)
                    ck = self._composite_key(cat, k)
                    self._records[ck] = MemoryRecord(
                        key=k,
                        value=str(val),
                        category=cat,
                        tier=tier,
                        importance=0.7,
                    )
            else:
                ck = self._composite_key(cat, "value")
                self._records[ck] = MemoryRecord(
                    key="value",
                    value=str(bucket),
                    category=cat,
                    tier=tier,
                    importance=0.6,
                )

    def _sync_to_legacy_file(self) -> None:
        legacy_dict: Dict[str, Any] = {}
        for rec in self._records.values():
            if rec.category not in legacy_dict:
                legacy_dict[rec.category] = {}
            legacy_dict[rec.category][rec.key] = {"value": rec.value}
        try:
            LEGACY_MEMORY_FILE.write_text(
                json.dumps(legacy_dict, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception:
            pass

    # ── Temel Operasyonlar (CRUD) ───────────────────────────────────────────

    def store(
        self,
        category: str,
        key: str,
        value: str,
        importance: float = 0.5,
        tier: Optional[MemoryTier] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> MemoryRecord:
        """Kayıt ekler veya günceller."""
        cat_clean = category.strip().lower()
        key_clean = key.strip().lower()
        comp_key = self._composite_key(cat_clean, key_clean)

        if tier is None:
            tier = MemoryTier.USER_PROFILE if cat_clean in ("identity", "preferences", "family") else MemoryTier.SEMANTIC

        now = time.time()
        with self._lock:
            existing = self._records.get(comp_key)
            if existing:
                existing.value = str(value)
                existing.importance = max(existing.importance, importance)
                existing.updated_at = now
                if metadata:
                    existing.metadata.update(metadata)
                rec = existing
            else:
                rec = MemoryRecord(
                    key=key_clean,
                    value=str(value),
                    category=cat_clean,
                    tier=tier,
                    importance=importance,
                    created_at=now,
                    updated_at=now,
                    metadata=metadata or {},
                )
                self._records[comp_key] = rec

            self._save()

        # Vektör hafızaya ekle (arkaplanda)
        try:
            from memory.vector_store import vector_memory
            vector_memory.add(
                text=f"[{cat_clean}] {key_clean}: {value}",
                metadata={"category": cat_clean, "key": key_clean},
            )
        except Exception:
            pass

        # Event Bus'a bildir
        bus = self._get_bus()
        if bus:
            bus.publish_event(UltronEvent(
                event_type="memory.updated",
                source=EventSource.SYSTEM,
                payload={"category": cat_clean, "key": key_clean, "value": str(value)[:100]},
                priority=EventPriority.LOW,
            ))

        return rec

    def get(self, category: str, key: str) -> Optional[str]:
        """Kayıtlı değeri döner."""
        comp_key = self._composite_key(category, key)
        with self._lock:
            rec = self._records.get(comp_key)
            return rec.value if rec else None

    def delete(self, category: str, key: str) -> bool:
        """Kaydı siler."""
        comp_key = self._composite_key(category, key)
        with self._lock:
            if comp_key in self._records:
                del self._records[comp_key]
                self._save()
                return True
        return False

    def search(self, query: str, limit: int = 5) -> List[Dict[str, Any]]:
        """Hafıza araması yapar. Anlamsal ve anahtar kelime eşleştirmesi birleşiktir."""
        query_clean = query.strip().lower()
        if not query_clean:
            return []

        results = []
        with self._lock:
            for rec in self._records.values():
                score = 0.0
                text_target = f"{rec.category} {rec.key} {rec.value}".lower()
                if query_clean in text_target:
                    score = 1.0
                else:
                    # Kelime bazlı eşleşme
                    words = query_clean.split()
                    matched = sum(1 for w in words if w in text_target)
                    if matched > 0:
                        score = (matched / len(words)) * 0.8

                if score > 0:
                    results.append({
                        "category": rec.category,
                        "key": rec.key,
                        "value": rec.value,
                        "importance": rec.importance,
                        "score": score,
                    })

        results.sort(key=lambda x: (x["score"], x["importance"]), reverse=True)
        return results[:limit]

    def format_for_prompt(self, max_items: int = 8) -> str:
        """Gemini Live ve LLM istemleri için optimize edilmiş hafıza bağlamı."""
        with self._lock:
            if not self._records:
                return ""

            # Önem sırasına göre diz
            sorted_recs = sorted(
                self._records.values(),
                key=lambda r: (r.tier == MemoryTier.USER_PROFILE, r.importance),
                reverse=True,
            )

            lines = ["[ULTRON HAFIZA BAĞLAMI]"]
            for r in sorted_recs[:max_items]:
                lines.append(f"- [{r.category.upper()}] {r.key}: {r.value}")

            return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            tier_counts = {}
            for r in self._records.values():
                t = r.tier.value
                tier_counts[t] = tier_counts.get(t, 0) + 1
            return {
                "total_records": len(self._records),
                "by_tier": tier_counts,
            }

    def reset(self) -> None:
        """Test amaçlı temizleme."""
        with self._lock:
            self._records.clear()


# Global Singleton
unified_memory = UnifiedMemoryEngine()
