"""
ULTRON Vector Memory Store — Semantik Hafiza Veritabani (v1.0)
ChromaDB tabanli yerel vektor veritabani. Semantik arama destekler.
Fallback: ChromaDB yuklenemezse keyword aramasina duser.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app_paths import data_path

logger = logging.getLogger("ultron.memory.vector_store")

try:
    import chromadb
    from chromadb.config import Settings
    CHROMADB_OK = True
except ImportError:
    CHROMADB_OK = False
    logger.warning("[VectorStore] chromadb yuklu degil — keyword fallback aktif.")

try:
    from google import genai as _genai_mod
    GENAI_OK = True
except ImportError:
    GENAI_OK = False

CHROMA_PATH = data_path("memory", "chroma_db")
COLLECTION_NAME = "ultron_memory"
EMBED_MODEL = "text-embedding-004"


@dataclass
class SearchResult:
    doc_id: str
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0


class _KeywordFallbackStore:
    def __init__(self):
        self._data: dict[str, dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._path = data_path("memory", "vector_fallback.json")
        self._load()

    def _load(self):
        with self._lock:
            try:
                if self._path.exists():
                    self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except Exception:
                self._data = {}

    def _save(self):
        with self._lock:
            try:
                self._path.parent.mkdir(parents=True, exist_ok=True)
                self._path.write_text(json.dumps(self._data, indent=2, ensure_ascii=False), encoding="utf-8")
            except Exception as e:
                logger.error(f"Fallback kaydetme hatasi: {e}")

    def add(self, doc_id: str, text: str, metadata: dict[str, Any]) -> None:
        with self._lock:
            self._data[doc_id] = {"text": text, "metadata": metadata, "ts": time.time()}
            self._save()

    def search(self, query: str, n: int = 5) -> list[SearchResult]:
        with self._lock:
            terms = [t.lower() for t in re.findall(r"\w+", query) if len(t) > 2]
            if not terms:
                items = sorted(self._data.items(), key=lambda x: x[1].get("ts", 0), reverse=True)
                return [SearchResult(doc_id=k, text=v["text"], metadata=v.get("metadata", {}), score=0.5)
                        for k, v in items[:n]]
            scored = []
            for doc_id, item in self._data.items():
                content = (item.get("text", "") + " " + json.dumps(item.get("metadata", {}))).lower()
                matches = sum(1 for t in terms if t in content)
                if matches:
                    scored.append((matches / len(terms), doc_id, item))
            scored.sort(reverse=True, key=lambda x: x[0])
            return [SearchResult(doc_id=doc_id, text=item["text"], metadata=item.get("metadata", {}), score=score)
                    for score, doc_id, item in scored[:n]]

    def delete(self, doc_id: str) -> bool:
        with self._lock:
            if doc_id in self._data:
                del self._data[doc_id]
                self._save()
                return True
            return False

    def get_all(self) -> list[SearchResult]:
        with self._lock:
            return [SearchResult(doc_id=k, text=v["text"], metadata=v.get("metadata", {}), score=1.0)
                    for k, v in self._data.items()]


class VectorMemoryStore:
    """Yerel ChromaDB tabanli semantik vektor hafiza deposu."""

    def __init__(self):
        self._lock = threading.RLock()
        self._fallback: _KeywordFallbackStore | None = None
        self._client = None
        self._collection = None
        self._api_key: str = ""
        self._init_store()

    def _init_store(self) -> None:
        if not CHROMADB_OK:
            self._fallback = _KeywordFallbackStore()
            return
        try:
            CHROMA_PATH.mkdir(parents=True, exist_ok=True)
            self._client = chromadb.PersistentClient(
                path=str(CHROMA_PATH),
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"[VectorStore] ChromaDB: {CHROMA_PATH} | {self._collection.count()} kayit")
        except Exception as e:
            logger.error(f"[VectorStore] ChromaDB hatasi: {e} — fallback aktif.")
            self._fallback = _KeywordFallbackStore()

    def _embed(self, text: str) -> list[float] | None:
        if not GENAI_OK or not self._api_key:
            return None
        try:
            from google import genai
            client = genai.Client(api_key=self._api_key)
            result = client.models.embed_content(model=EMBED_MODEL, contents=text)
            return result.embeddings[0].values
        except Exception as e:
            logger.debug(f"[VectorStore] Embedding hatasi: {e}")
            return None

    def set_api_key(self, key: str) -> None:
        self._api_key = key.strip()

    def _make_id(self, text: str, metadata: dict) -> str:
        raw = text[:120] + json.dumps(metadata, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def add(self, text: str, metadata: dict[str, Any] | None = None, doc_id: str | None = None) -> str:
        meta = metadata or {}
        meta["timestamp"] = time.time()
        doc_id = doc_id or self._make_id(text, meta)

        if self._fallback:
            self._fallback.add(doc_id, text, meta)
            return doc_id

        with self._lock:
            try:
                embedding = self._embed(text)
                kwargs: dict[str, Any] = {
                    "documents": [text],
                    "ids": [doc_id],
                    "metadatas": [meta],
                }
                if embedding:
                    kwargs["embeddings"] = [embedding]
                self._collection.upsert(**kwargs)
            except Exception as e:
                logger.error(f"[VectorStore] Ekle hatasi: {e}")
        return doc_id

    def search(self, query: str, n: int = 5) -> list[SearchResult]:
        if self._fallback:
            return self._fallback.search(query, n)

        with self._lock:
            try:
                count = self._collection.count()
                if count == 0:
                    return []
                embedding = self._embed(query)
                kwargs: dict[str, Any] = {
                    "n_results": min(n, count),
                    "include": ["documents", "metadatas", "distances"],
                }
                if embedding:
                    kwargs["query_embeddings"] = [embedding]
                else:
                    kwargs["query_texts"] = [query]

                results = self._collection.query(**kwargs)
                out = []
                docs = (results.get("documents") or [[]])[0]
                metas = (results.get("metadatas") or [[]])[0]
                dists = (results.get("distances") or [[]])[0]
                ids = (results.get("ids") or [[]])[0]

                for doc_id, text, meta, dist in zip(ids, docs, metas, dists):
                    score = max(0.0, 1.0 - float(dist))
                    out.append(SearchResult(
                        doc_id=doc_id, text=text or "", metadata=meta or {}, score=round(score, 3)
                    ))
                return out
            except Exception as e:
                logger.error(f"[VectorStore] Arama hatasi: {e}")
                return []

    def delete(self, doc_id: str) -> bool:
        if self._fallback:
            return self._fallback.delete(doc_id)
        with self._lock:
            try:
                self._collection.delete(ids=[doc_id])
                return True
            except Exception as e:
                logger.error(f"[VectorStore] Sil hatasi: {e}")
                return False

    def get_all(self) -> list[SearchResult]:
        if self._fallback:
            return self._fallback.get_all()
        with self._lock:
            try:
                results = self._collection.get(include=["documents", "metadatas"])
                docs = results.get("documents") or []
                metas = results.get("metadatas") or []
                ids = results.get("ids") or []
                return [SearchResult(doc_id=d_id, text=text or "", metadata=meta or {}, score=1.0)
                        for d_id, text, meta in zip(ids, docs, metas)]
            except Exception as e:
                logger.error(f"[VectorStore] get_all hatasi: {e}")
                return []

    def count(self) -> int:
        if self._fallback:
            return len(self._fallback._data)
        with self._lock:
            try:
                return self._collection.count()
            except Exception:
                return 0

    def format_for_prompt(self, query: str = "", max_results: int = 6) -> str:
        if query:
            results = self.search(query, n=max_results)
        else:
            results = self.get_all()[:max_results]
        if not results:
            return ""
        lines = ["[SEMANTIK HAFIZA — ILGILI KAYITLAR]"]
        for r in results:
            cat = r.metadata.get("category", "")
            key = r.metadata.get("key", "")
            prefix = f"{cat}/{key}: " if cat else ""
            lines.append(f"• {prefix}{r.text}")
        return "\n".join(lines)


vector_memory = VectorMemoryStore()
