"""
ULTRON Local RAG Engine — Yerel Bilgi Tabanı ve Semantik Erişim Motoru (Phase 8)
══════════════════════════════════════════════════════════════════════════════
Dokümanları (metin, markdown, kod, notlar) parçalara (chunk) ayırır,
ChromaDB ve yerel vektör/BM25 hibrit arama ile hızlı ve güvenilir RAG sağlar.

Kullanım:
    from core.local_rag_engine import local_rag
    local_rag.index_document("notlar", "Ultron mimarisinde Event Bus...", doc_id="doc_1")
    results = local_rag.search("Event Bus nasıl çalışır?", limit=3)
"""

from __future__ import annotations

import hashlib
import json
import logging
import math
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from app_paths import data_path
from core.events import UltronEvent, EventPriority, EventSource

logger = logging.getLogger("ultron.core.local_rag")

RAG_DB_DIR = data_path("memory", "rag_chroma")
RAG_FALLBACK_FILE = data_path("memory", "rag_fallback.json")


@dataclass
class RagChunk:
    chunk_id: str
    doc_id: str
    text: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


class LocalRagEngine:
    """Yerel doküman indeksleme ve anlamsal arama motoru."""

    _instance: Optional["LocalRagEngine"] = None
    _lock = threading.RLock()

    def __new__(cls) -> "LocalRagEngine":
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

        self._bus = None
        self._chroma_client = None
        self._collection = None
        self._fallback_docs: Dict[str, RagChunk] = {}
        self._init_storage()

    def _get_bus(self):
        if self._bus is None:
            try:
                from core.event_bus import bus
                self._bus = bus
            except ImportError:
                pass
        return self._bus

    def _init_storage(self) -> None:
        """ChromaDB veya fallback JSON deposunu başlatır."""
        try:
            import chromadb
            RAG_DB_DIR.mkdir(parents=True, exist_ok=True)
            self._chroma_client = chromadb.PersistentClient(path=str(RAG_DB_DIR))
            self._collection = self._chroma_client.get_or_create_collection("ultron_rag_docs")
            logger.info("[LocalRAG] ChromaDB başarıyla bağlandı.")
        except Exception as e:
            logger.warning(f"[LocalRAG] ChromaDB başlatılamadı, fallback aktif: {e}")
            self._load_fallback()

    def _load_fallback(self) -> None:
        if RAG_FALLBACK_FILE.exists():
            try:
                data = json.loads(RAG_FALLBACK_FILE.read_text(encoding="utf-8"))
                for cid, d in data.items():
                    self._fallback_docs[cid] = RagChunk(
                        chunk_id=cid,
                        doc_id=d.get("doc_id", ""),
                        text=d.get("text", ""),
                        metadata=d.get("metadata", {}),
                    )
            except Exception:
                pass

    def _save_fallback(self) -> None:
        try:
            RAG_FALLBACK_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {
                c.chunk_id: {
                    "doc_id": c.doc_id,
                    "text": c.text,
                    "metadata": c.metadata,
                }
                for c in self._fallback_docs.values()
            }
            RAG_FALLBACK_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    # ── Metin Parçalama (Chunking) ──────────────────────────────────────────

    def chunk_text(self, text: str, chunk_size: int = 400, overlap: int = 50) -> List[str]:
        """Metni örtüşen parçalara (sliding window chunk) ayırır."""
        text = text.strip()
        if not text:
            return []
        if len(text) <= chunk_size:
            return [text]

        chunks = []
        step = max(chunk_size - overlap, 50)
        for i in range(0, len(text), step):
            c = text[i : i + chunk_size].strip()
            if c:
                chunks.append(c)
        return chunks

    # ── İndeksleme (Ingestion) ──────────────────────────────────────────────

    def index_document(
        self,
        title: str,
        content: str,
        doc_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        chunk_size: int = 400,
    ) -> List[str]:
        """Bir dokümanı indeksler."""
        if not doc_id:
            doc_id = hashlib.md5(f"{title}_{content[:50]}".encode()).hexdigest()[:12]

        chunks = self.chunk_text(content, chunk_size=chunk_size)
        meta_base = metadata or {}
        meta_base["title"] = title
        meta_base["doc_id"] = doc_id
        meta_base["indexed_at"] = time.time()

        chunk_ids = []
        with self._lock:
            if self._collection is not None:
                try:
                    c_ids = [f"{doc_id}_{i}" for i in range(len(chunks))]
                    c_metas = [{**meta_base, "chunk_index": i} for i in range(len(chunks))]
                    self._collection.upsert(
                        ids=c_ids,
                        documents=chunks,
                        metadatas=c_metas,
                    )
                    chunk_ids = c_ids
                except Exception as e:
                    logger.warning(f"[LocalRAG] ChromaDB upsert hatası, fallback'e yazılıyor: {e}")
                    for i, ch in enumerate(chunks):
                        cid = f"{doc_id}_{i}"
                        self._fallback_docs[cid] = RagChunk(
                            chunk_id=cid,
                            doc_id=doc_id,
                            text=ch,
                            metadata={**meta_base, "chunk_index": i},
                        )
                        chunk_ids.append(cid)
                    self._save_fallback()
            else:
                for i, ch in enumerate(chunks):
                    cid = f"{doc_id}_{i}"
                    self._fallback_docs[cid] = RagChunk(
                        chunk_id=cid,
                        doc_id=doc_id,
                        text=ch,
                        metadata={**meta_base, "chunk_index": i},
                    )
                    chunk_ids.append(cid)
                self._save_fallback()

        logger.info(f"[LocalRAG] '{title}' indekslendi ({len(chunks)} parça).")

        # Event Bus
        bus = self._get_bus()
        if bus:
            bus.publish_event(UltronEvent(
                event_type="rag.indexed",
                source=EventSource.SYSTEM,
                payload={"doc_id": doc_id, "title": title, "chunks_count": len(chunks)},
                priority=EventPriority.LOW,
            ))

        return chunk_ids

    # ── Arama (Retrieval) ───────────────────────────────────────────────────

    def search(self, query: str, limit: int = 5) -> List[RagChunk]:
        """Semantik ve anahtar kelime eşleştirmesi ile en alakalı parçaları döner."""
        query = query.strip()
        if not query:
            return []

        results: List[RagChunk] = []

        with self._lock:
            # 1. ChromaDB üzerinden dene
            if self._collection is not None:
                try:
                    res = self._collection.query(
                        query_texts=[query],
                        n_results=min(limit, self._collection.count() or 1),
                    )
                    if res and res.get("documents") and res["documents"][0]:
                        docs = res["documents"][0]
                        metas = res["metadatas"][0] if res.get("metadatas") else [{}] * len(docs)
                        ids = res["ids"][0] if res.get("ids") else [""] * len(docs)
                        distances = res["distances"][0] if res.get("distances") else [0.0] * len(docs)

                        for doc, meta, cid, dist in zip(docs, metas, ids, distances):
                            # Distance'ı benzerlik skoruna çevir
                            score = max(0.0, 1.0 - (dist / 2.0))
                            results.append(RagChunk(
                                chunk_id=cid,
                                doc_id=meta.get("doc_id", ""),
                                text=doc,
                                metadata=meta,
                                score=score,
                            ))
                        # ChromaDB araması tamamlandı
                        pass
                except Exception as e:
                    logger.debug(f"[LocalRAG] ChromaDB arama hatası, fallback'e geçiliyor: {e}")

            # 2. Fallback Anahtar Kelime / BM25 Arama (ChromaDB sonuç bulamadıysa)
            if not results:
                words = [w.lower() for w in re.findall(r"\w+", query) if len(w) > 2]
                scored = []
                for chunk in self._fallback_docs.values():
                    c_text = chunk.text.lower()
                    matches = sum(1 for w in words if w in c_text)
                    if matches > 0:
                        score = matches / max(len(words), 1)
                        scored.append((score, chunk))

                scored.sort(key=lambda x: x[0], reverse=True)
                for score, chunk in scored[:limit]:
                    chunk.score = score
                    results.append(chunk)

        # Event Bus
        bus = self._get_bus()
        if bus:
            bus.publish_event(UltronEvent(
                event_type="rag.query",
                source=EventSource.SYSTEM,
                payload={"query": query, "results_count": len(results)},
                priority=EventPriority.LOW,
            ))

        return results

    def format_context_for_llm(self, query: str, limit: int = 4) -> str:
        """Sorgu ile ilgili RAG bağlamını LLM prompt'una eklenmek üzere metin olarak biçimlendirir."""
        chunks = self.search(query, limit=limit)
        if not chunks:
            return ""

        lines = ["[YEREL BİLGİ TABANI (RAG) BAĞLAMI]"]
        for i, c in enumerate(chunks, 1):
            title = c.metadata.get("title", "Doküman")
            lines.append(f"--- Kaynak {i}: {title} (Eşleşme: {c.score:.2f}) ---")
            lines.append(c.text.strip())

        return "\n".join(lines)

    def reset(self) -> None:
        """Test amaçlı sıfırlama."""
        with self._lock:
            self._fallback_docs.clear()
            if self._collection is not None:
                try:
                    self._chroma_client.delete_collection("ultron_rag_docs")
                    self._collection = self._chroma_client.create_collection("ultron_rag_docs")
                except Exception:
                    pass


# Global Singleton
local_rag = LocalRagEngine()
