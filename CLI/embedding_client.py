"""
AgentCanvas Embedding Client
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LM Studio client for semantic search via Qwen3-Embedding-0.6B.

Architecture:
    Agent → MCP Server → Embedding Engine (LM Studio)
                  |
             search.data returns Top-N IDs + knowledgeOriginal
                  |
             get.data fetches full content from Unity

Search and data retrieval are decoupled: Embedding returns only IDs
and anchor text; Unity returns ground-truth content.
"""

from __future__ import annotations

import json
import logging
import pickle
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import httpx
import numpy as np

from cli_core import Config
from knowledge_reader import KnowledgeDoc, KnowledgeReader

logger = logging.getLogger("agentcanvas.embedding")

# ── Data Structures ─────────────────────────────────────────────────────────


@dataclass
class SearchResult:
    """A single search result from the embedding engine."""

    id: str
    desc: str
    tag: List[str]
    data: Dict[str, Any]
    knowledge_original: str
    score: float
    template_type: str


@dataclass
class IndexEntry:
    """An entry in the embedding index."""

    id: str
    display_name: str
    description: str
    tags: List[str]
    knowledge_original: str
    data: Dict[str, Any]
    template_type: str = ""
    embedding: Optional[np.ndarray] = None

    @property
    def search_text(self) -> str:
        """Concatenate all searchable text for embedding."""
        parts = [
            self.id,
            self.display_name,
            self.description,
            " ".join(self.tags),
            self.knowledge_original,
        ]
        return " ".join(p for p in parts if p)


# ── Embedding Client ────────────────────────────────────────────────────────


class EmbeddingClient:
    """
    Client for LM Studio embedding API.

    Handles:
    - Calling LM Studio's /v1/embeddings endpoint
    - Building and caching search indices
    - Cosine similarity search with Top-N results
    - Graceful fallback to keyword matching when LM Studio is unavailable
    """

    def __init__(self, config: Config, knowledge_reader: Optional[KnowledgeReader] = None):
        self.config = config
        self._http_client: Optional[httpx.AsyncClient] = None
        self._index: List[IndexEntry] = []
        self._embeddings_matrix: Optional[np.ndarray] = None
        self._embedding_map: List[int] = []  # matrix index → _index index
        self._ready = False
        self._knowledge_reader = knowledge_reader or (
            KnowledgeReader(config.knowledge_path) if config.knowledge_path else None
        )

    # ── HTTP ──

    async def _ensure_http(self) -> httpx.AsyncClient:
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(
                timeout=httpx.Timeout(30.0),
            )
        return self._http_client

    async def _check_lm_studio(self) -> bool:
        """Check if LM Studio is reachable."""
        try:
            client = await self._ensure_http()
            url = f"{self.config.lm_studio_base_url}/v1/models"
            resp = await client.get(url, timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    async def get_embedding(self, text: str) -> Optional[np.ndarray]:
        """
        Get embedding vector for a single text string from LM Studio.

        Returns None if LM Studio is unavailable.
        """
        client = await self._ensure_http()
        url = f"{self.config.lm_studio_base_url}/v1/embeddings"
        payload = {
            "model": self.config.embedding_model,
            "input": text,
        }

        try:
            resp = await client.post(url, json=payload, timeout=30.0)
            resp.raise_for_status()
            data = resp.json()
            vector = data["data"][0]["embedding"]
            return np.array(vector, dtype=np.float32)
        except Exception as e:
            logger.warning("LM Studio embedding failed: %s", e)
            return None

    async def get_embeddings_batch(
        self, texts: List[str]
    ) -> List[Optional[np.ndarray]]:
        """
        Get embeddings for a batch of texts.

        Currently sends one at a time (LM Studio handles this fine for <1000 items).
        Could be optimized with true batching in the future.
        """
        results = []
        for i, text in enumerate(texts):
            logger.debug("Embedding %d/%d: %d chars", i + 1, len(texts), len(text))
            vec = await self.get_embedding(text)
            results.append(vec)
        return results

    # ── Index Management ──

    def _index_cache_path(self) -> Path:
        """Path to the cached embedding index."""
        return Path(self.config.streaming_assets_path) / "index" / "embeddings.pkl"

    def _data_export_path(self) -> Path:
        """Path to the Unity data export file."""
        return Path(self.config.streaming_assets_path) / "data_export.json"

    def _load_data_export(self) -> List[Dict[str, Any]]:
        """Load exported data from Unity's data_export.json."""
        path = self._data_export_path()
        if not path.exists():
            logger.warning("Data export not found at %s", path)
            return []
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
            return data
        # May be wrapped in an object with "items" or "data" key
        return data.get("items", data.get("data", []))

    def _entries_from_export(self, export: List[Dict[str, Any]]) -> List[IndexEntry]:
        """Convert raw export data into IndexEntry objects."""
        entries = []
        for item in export:
            entry = IndexEntry(
                id=item.get("id", ""),
                display_name=item.get("displayName", item.get("name", "")),
                description=item.get("description", ""),
                tags=item.get("tag", item.get("tags", [])),
                knowledge_original=item.get("knowledgeOriginal", ""),
                data=item.get("data", {}),
                template_type=item.get("templateType", ""),
            )
            entries.append(entry)
        return entries

    def _knowledge_to_entry(self, doc: KnowledgeDoc) -> IndexEntry:
        """Convert a KnowledgeDoc to an IndexEntry for the embedding index."""
        return IndexEntry(
            id=doc.id,
            display_name=doc.title,
            description=doc.description,
            tags=doc.tags,
            knowledge_original=doc.content,
            data={"source": doc.source_path},
            template_type="knowledge",
        )

    async def build_index(self, force: bool = False) -> bool:
        """
        Build or load the embedding index.

        1. Check for cached index → load if fresh
        2. Otherwise, read data_export.json → compute embeddings → cache

        Returns True if index is ready, False if only keyword fallback available.
        """
        cache_path = self._index_cache_path()

        # Try loading cached index
        if not force and cache_path.exists():
            try:
                self._load_cached_index(cache_path)
                logger.info(
                    "Loaded cached index: %d entries",
                    len(self._index),
                )
                return True
            except Exception as e:
                logger.warning("Failed to load cached index: %s", e)

        # Load data export (Unity)
        export = self._load_data_export()
        self._index = self._entries_from_export(export) if export else []
        if export:
            logger.info("Loaded %d entries from Unity data export", len(export))
        else:
            logger.warning("No Unity data export found at %s", self._data_export_path())

        # Load knowledge docs (markdown files)
        if self._knowledge_reader:
            try:
                knowledge_docs = self._knowledge_reader.read_all()
                for doc in knowledge_docs:
                    # Avoid duplicate IDs — knowledge docs take precedence
                    self._index = [e for e in self._index if e.id != doc.id]
                    self._index.append(self._knowledge_to_entry(doc))
                logger.info("Loaded %d entries from knowledge docs", len(knowledge_docs))
            except Exception as e:
                logger.warning("Failed to load knowledge docs: %s", e)

        if not self._index:
            logger.warning("No index entries loaded — keyword fallback only")
            self._ready = False
            return False

        # Try LM Studio for embeddings
        lm_available = await self._check_lm_studio()
        if lm_available:
            logger.info("LM Studio available — computing embeddings...")
            texts = [e.search_text for e in self._index]
            embeddings = await self.get_embeddings_batch(texts)

            # Assign embeddings where successful
            valid_count = 0
            for entry, emb in zip(self._index, embeddings):
                if emb is not None:
                    entry.embedding = emb
                    valid_count += 1

            logger.info("Computed %d/%d embeddings", valid_count, len(self._index))

            if valid_count > 0:
                self._build_embeddings_matrix()
                self._save_cached_index(cache_path)
        else:
            logger.warning(
                "LM Studio not available at %s — keyword fallback only",
                self.config.lm_studio_base_url,
            )

        self._ready = True
        return lm_available

    def _build_embeddings_matrix(self) -> None:
        """Build numpy matrix + index map from entry embeddings."""
        vectors: List[np.ndarray] = []
        self._embedding_map = []
        for i, entry in enumerate(self._index):
            if entry.embedding is not None:
                vectors.append(entry.embedding)
                self._embedding_map.append(i)
        if vectors:
            self._embeddings_matrix = np.stack(vectors)
        else:
            self._embeddings_matrix = None

    def _save_cached_index(self, path: Path) -> None:
        """Persist the computed index to disk."""
        path.parent.mkdir(parents=True, exist_ok=True)

        # Convert numpy arrays to lists for serialization
        serializable = []
        for entry in self._index:
            e = entry.__dict__.copy()
            if e["embedding"] is not None:
                e["embedding"] = e["embedding"].tolist()
            serializable.append(e)

        cache_data = {
            "version": 1,
            "entries": serializable,
        }

        with open(path, "wb") as f:
            pickle.dump(cache_data, f)

        logger.info("Index cached to %s (%d entries)", path, len(self._index))

    def _load_cached_index(self, path: Path) -> None:
        """Load a previously cached index from disk."""
        with open(path, "rb") as f:
            cache_data = pickle.load(f)

        entries_data = cache_data.get("entries", [])
        self._index = []
        for e in entries_data:
            entry = IndexEntry(
                id=e["id"],
                display_name=e["display_name"],
                description=e["description"],
                tags=e["tags"],
                knowledge_original=e["knowledge_original"],
                data=e["data"],
                template_type=e["template_type"],
            )
            if e.get("embedding") is not None:
                entry.embedding = np.array(e["embedding"], dtype=np.float32)
            self._index.append(entry)

        self._build_embeddings_matrix()
        self._ready = True

    # ── Search ──

    def _cosine_similarity(
        self, query_vec: np.ndarray, matrix: np.ndarray
    ) -> np.ndarray:
        """Compute cosine similarity between query and all index vectors."""
        query_norm = query_vec / (np.linalg.norm(query_vec) + 1e-10)
        matrix_norm = matrix / (np.linalg.norm(matrix, axis=1, keepdims=True) + 1e-10)
        scores = np.dot(matrix_norm, query_norm)
        return scores

    def _keyword_search(self, query: str) -> List[Tuple[int, float]]:
        """
        Simple keyword-based fallback search.

        Scores based on term frequency in id, display_name, description, and tags.
        Used when LM Studio is unavailable.
        """
        query_lower = query.lower()
        terms = re.findall(r"\w+", query_lower)

        scored: List[Tuple[int, float]] = []
        for idx, entry in enumerate(self._index):
            score = 0.0
            search_text = f"{entry.id} {entry.display_name} {entry.description} {' '.join(entry.tags)}".lower()

            for term in terms:
                count = search_text.count(term)
                if count > 0:
                    # Boost for matches in id (exact) and display_name
                    if term == entry.id.lower():
                        score += 3.0
                    elif term in entry.display_name.lower():
                        score += 2.0
                    elif term in entry.tags:
                        score += 1.5
                    else:
                        score += count * 0.5

            if score > 0:
                scored.append((idx, score))

        scored.sort(key=lambda x: x[1], reverse=True)
        return scored

    async def search(self, query: str, top_n: Optional[int] = None) -> List[SearchResult]:
        """
        Search the index using semantic embedding (or keyword fallback).

        Returns up to top_n SearchResult objects, sorted by relevance.
        """
        if not self._index:
            logger.warning("No index loaded — returning empty results")
            return []

        if top_n is None:
            top_n = self.config.top_n

        # Try semantic search first
        if self._embeddings_matrix is not None:
            query_vec = await self.get_embedding(query)
            if query_vec is not None:
                scores = self._cosine_similarity(query_vec, self._embeddings_matrix)
                top_indices = np.argsort(scores)[::-1][:top_n]

                results = []
                for matrix_idx in top_indices:
                    real_idx = self._embedding_map[matrix_idx]
                    entry = self._index[real_idx]
                    results.append(
                        SearchResult(
                            id=entry.id,
                            desc=entry.description or entry.display_name,
                            tag=entry.tags,
                            data=entry.data,
                            knowledge_original=entry.knowledge_original,
                            score=float(scores[matrix_idx]),
                            template_type=entry.template_type,
                        )
                    )
                logger.debug(
                    "Semantic search | query=%s | top=%d | best=%.4f",
                    query[:50],
                    len(results),
                    results[0].score if results else 0,
                )
                return results

        # Fallback: keyword search
        logger.info("Semantic search unavailable — using keyword fallback")
        scored = self._keyword_search(query)

        results = []
        for idx, score in scored[:top_n]:
            entry = self._index[idx]
            results.append(
                SearchResult(
                    id=entry.id,
                    desc=entry.description or entry.display_name,
                    tag=entry.tags,
                    data=entry.data,
                    knowledge_original=entry.knowledge_original,
                    score=score,
                    template_type=entry.template_type,
                )
            )

        return results

    # ── Lifecycle ──

    async def close(self) -> None:
        if self._http_client and not self._http_client.is_closed:
            await self._http_client.aclose()
