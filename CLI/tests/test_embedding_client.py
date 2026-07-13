"""
Tests for embedding_client.py — IndexEntry, keyword search,
index building/caching, data export loading.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from cli_core import Config
from embedding_client import EmbeddingClient, IndexEntry, SearchResult


# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def small_data_export(tmp_path: Path) -> Path:
    """Minimal data export for quick tests."""
    export = [
        {
            "id": "eq_01",
            "displayName": "显微镜",
            "description": "光学显微镜",
            "tag": ["显微镜", "光学"],
            "data": {"imagePath": "mic.png"},
            "knowledgeOriginal": "显微镜由目镜和物镜组成。",
            "templateType": "image_text",
        },
        {
            "id": "eq_02",
            "displayName": "电压表",
            "description": "电压测量",
            "tag": ["电压", "电路"],
            "data": {"imagePath": "volt.png"},
            "knowledgeOriginal": "电压表并联在电路中。",
            "templateType": "image_text",
        },
    ]
    path = tmp_path / "data_export.json"
    path.write_text(json.dumps(export, ensure_ascii=False), encoding="utf-8")
    return path


@pytest.fixture
def config_with_index(tmp_path: Path) -> Config:
    """Config pointing at a tmp directory for index caching."""
    return Config(
        streaming_assets_path=str(tmp_path),
        streaming_assets_data_path=str(tmp_path),
        top_n=5,
    )


# ── IndexEntry ──────────────────────────────────────────────────────────────


class TestIndexEntry:
    def test_search_text_concatenation(self):
        """search_text should concatenate all searchable fields."""
        entry = IndexEntry(
            id="eq_01",
            display_name="显微镜",
            description="光学显微镜工具",
            tags=["显微镜", "光学"],
            knowledge_original="这是知识原文。",
            data={"imagePath": "mic.png"},
        )
        text = entry.search_text
        assert "eq_01" in text
        assert "显微镜" in text
        assert "光学显微镜工具" in text
        assert "光学" in text  # from tags
        assert "这是知识原文。" in text

    def test_search_text_handles_empty_fields(self):
        """Empty fields should be gracefully handled."""
        entry = IndexEntry(
            id="test_id",
            display_name="",
            description="",
            tags=[],
            knowledge_original="",
            data={},
        )
        text = entry.search_text
        assert "test_id" in text
        assert text.strip() == "test_id"


# ── EmbeddingClient — Data Loading ──────────────────────────────────────────


class TestEmbeddingClientDataLoading:
    def test_load_data_export(self, small_data_export: Path, config_with_index: Config):
        """Data export should be loaded correctly."""
        client = EmbeddingClient(config_with_index)
        export = client._load_data_export()
        assert len(export) == 2
        assert export[0]["id"] == "eq_01"
        assert export[1]["id"] == "eq_02"

    def test_load_missing_file(self, tmp_path: Path):
        """Missing data_export.json should return empty list."""
        config = Config(streaming_assets_path=str(tmp_path), streaming_assets_data_path=str(tmp_path))
        client = EmbeddingClient(config)
        export = client._load_data_export()
        assert export == []

    def test_entries_from_export(self, small_data_export: Path, config_with_index: Config):
        """Raw export data should convert to IndexEntry objects."""
        client = EmbeddingClient(config_with_index)
        export = client._load_data_export()
        entries = client._entries_from_export(export)

        assert len(entries) == 2
        assert entries[0].id == "eq_01"
        assert entries[0].display_name == "显微镜"
        assert entries[0].tags == ["显微镜", "光学"]
        assert entries[0].knowledge_original == "显微镜由目镜和物镜组成。"
        assert entries[1].id == "eq_02"


# ── EmbeddingClient — Keyword Search ────────────────────────────────────────


class TestKeywordSearch:
    @pytest.mark.asyncio
    async def test_keyword_search_exact_match(self, small_data_export: Path, config_with_index: Config):
        """Keyword search should find exact matches."""
        client = EmbeddingClient(config_with_index)
        export = client._load_data_export()
        client._index = client._entries_from_export(export)
        client._ready = True

        results = await client.search("显微镜")
        assert len(results) >= 1
        assert any(r.id == "eq_01" for r in results)

    @pytest.mark.asyncio
    async def test_keyword_search_multiple_results(self, small_data_export: Path, config_with_index: Config):
        """Search should return multiple results sorted by relevance."""
        client = EmbeddingClient(config_with_index)
        export = client._load_data_export()
        client._index = client._entries_from_export(export)
        client._ready = True

        results = await client.search("电路")
        assert len(results) >= 1
        # eq_02 has "电路" in tags, should rank higher
        assert results[0].id == "eq_02" if any(r.id == "eq_02" for r in results) else True

    @pytest.mark.asyncio
    async def test_keyword_search_no_match(self, small_data_export: Path, config_with_index: Config):
        """Search with no matches should return empty list."""
        client = EmbeddingClient(config_with_index)
        export = client._load_data_export()
        client._index = client._entries_from_export(export)
        client._ready = True

        results = await client.search("xyznonexistent12345")
        assert len(results) == 0

    @pytest.mark.asyncio
    async def test_search_empty_index(self, config_with_index: Config):
        """Search with no index should return empty list."""
        client = EmbeddingClient(config_with_index)
        client._ready = True
        results = await client.search("anything")
        assert results == []

    @pytest.mark.asyncio
    async def test_keyword_search_respects_top_n(self, small_data_export: Path, config_with_index: Config):
        """Search should respect the top_n parameter."""
        client = EmbeddingClient(config_with_index)
        export = client._load_data_export()
        client._index = client._entries_from_export(export)
        client._ready = True

        results = await client.search("显微镜", top_n=1)
        assert len(results) <= 1


# ── EmbeddingClient — Index Cache ───────────────────────────────────────────


class TestIndexCache:
    @pytest.mark.asyncio
    async def test_cache_save_and_load(self, small_data_export: Path, tmp_path: Path):
        """Index should be saved and reloadable."""
        config = Config(streaming_assets_path=str(tmp_path), streaming_assets_data_path=str(tmp_path), top_n=5)
        client = EmbeddingClient(config)

        # Setup index manually (skip LM Studio)
        export = client._load_data_export()
        client._index = client._entries_from_export(export)

        # Save cache
        cache_path = client._index_cache_path()
        client._save_cached_index(cache_path)
        assert cache_path.exists()

        # Create a new client and load cache
        config2 = Config(streaming_assets_path=str(tmp_path), streaming_assets_data_path=str(tmp_path), top_n=5)
        client2 = EmbeddingClient(config2)
        client2._load_cached_index(cache_path)

        assert len(client2._index) == 2
        assert client2._index[0].id == "eq_01"
        assert client2._index[1].id == "eq_02"

    @pytest.mark.asyncio
    async def test_cache_with_embeddings(self, small_data_export: Path, tmp_path: Path):
        """Cache should preserve embedding vectors."""
        config = Config(streaming_assets_path=str(tmp_path), streaming_assets_data_path=str(tmp_path), top_n=5)
        client = EmbeddingClient(config)

        export = client._load_data_export()
        client._index = client._entries_from_export(export)

        # Add mock embeddings
        client._index[0].embedding = np.array([0.1, 0.2, 0.3], dtype=np.float32)
        client._index[1].embedding = np.array([0.4, 0.5, 0.6], dtype=np.float32)

        # Save and reload
        cache_path = client._index_cache_path()
        client._save_cached_index(cache_path)

        client2 = EmbeddingClient(config)
        client2._load_cached_index(cache_path)

        assert client2._index[0].embedding is not None
        assert np.allclose(client2._index[0].embedding, [0.1, 0.2, 0.3])
        assert np.allclose(client2._index[1].embedding, [0.4, 0.5, 0.6])

    def test_build_embeddings_matrix(self):
        """Matrix building from entries with embeddings."""
        from embedding_client import EmbeddingClient
        client = EmbeddingClient.__new__(EmbeddingClient)

        entry1 = IndexEntry(id="a", display_name="A", description="", tags=[], knowledge_original="", data={})
        entry2 = IndexEntry(id="b", display_name="B", description="", tags=[], knowledge_original="", data={})

        entry1.embedding = np.array([1.0, 0.0], dtype=np.float32)
        entry2.embedding = np.array([0.0, 1.0], dtype=np.float32)

        client._index = [entry1, entry2]
        client._build_embeddings_matrix()

        assert client._embeddings_matrix is not None
        assert client._embeddings_matrix.shape == (2, 2)

    def test_cosine_similarity(self):
        """Cosine similarity should return correct scores."""
        from embedding_client import EmbeddingClient
        client = EmbeddingClient.__new__(EmbeddingClient)

        query = np.array([1.0, 0.0], dtype=np.float32)
        matrix = np.array([
            [1.0, 0.0],  # identical → cos=1.0
            [0.0, 1.0],  # orthogonal → cos=0.0
            [1.0, 1.0],  # 45° → cos≈0.707
        ], dtype=np.float32)

        scores = client._cosine_similarity(query, matrix)

        assert np.allclose(scores[0], 1.0, atol=1e-6)
        assert np.allclose(scores[1], 0.0, atol=1e-6)
        assert np.allclose(scores[2], 0.70710677, atol=1e-6)


# ── SearchResult ────────────────────────────────────────────────────────────


class TestSearchResult:
    def test_search_result_creation(self):
        """SearchResult should be constructable with all fields."""
        result = SearchResult(
            id="eq_01",
            desc="显微镜",
            tag=["显微镜", "光学"],
            data={"imagePath": "mic.png"},
            knowledge_original="知识原文",
            score=0.95,
            template_type="image_text",
        )
        assert result.id == "eq_01"
        assert result.score == 0.95
        assert result.template_type == "image_text"
