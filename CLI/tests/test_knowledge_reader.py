"""
Tests for knowledge_reader.py — frontmatter parsing, doc loading, search text.
"""

from __future__ import annotations

from pathlib import Path


from knowledge_reader import KnowledgeReader, KnowledgeDoc


class TestFrontmatterParsing:
    def test_parse_frontmatter_basic(self):
        """Basic key: value frontmatter should be parsed."""
        text = """---
id: doc_01
title: Test Document
tags: [tag1, tag2]
---
# Content body
Some text here."""
        reader = KnowledgeReader()
        fm, body = reader._parse_frontmatter(text)
        assert fm["id"] == "doc_01"
        assert fm["title"] == "Test Document"
        assert fm["tags"] == ["tag1", "tag2"]
        assert "Content body" in body
        assert "Some text here" in body

    def test_parse_no_frontmatter(self):
        """Text without frontmatter should return empty dict."""
        text = "# Just a heading\n\nSome content."
        reader = KnowledgeReader()
        fm, body = reader._parse_frontmatter(text)
        assert fm == {}
        assert body == text

    def test_parse_empty_frontmatter(self):
        """Empty --- blocks should be handled."""
        text = """---
---
# Content"""
        reader = KnowledgeReader()
        fm, body = reader._parse_frontmatter(text)
        assert fm == {}
        assert "# Content" in body

    def test_parse_list_frontmatter(self):
        """List values in frontmatter should be parsed."""
        text = """---
tags: [显微镜, 光学, 成像]
authors: [张三]
---
# Content"""
        reader = KnowledgeReader()
        fm, body = reader._parse_frontmatter(text)
        assert fm["tags"] == ["显微镜", "光学", "成像"]
        assert fm["authors"] == ["张三"]


class TestTitleExtraction:
    def test_extract_title_from_heading(self):
        """First # heading should be extracted as title."""
        reader = KnowledgeReader()
        title = reader._extract_title("# Main Title\n\nSome text")
        assert title == "Main Title"

    def test_extract_title_no_heading(self):
        """No heading should return empty string."""
        reader = KnowledgeReader()
        title = reader._extract_title("Just plain text.")
        assert title == ""

    def test_extract_title_second_heading(self):
        """Only the first heading should be returned."""
        reader = KnowledgeReader()
        title = reader._extract_title("Some intro\n\n# First Heading\n\n## Second Heading")
        assert title == "First Heading"


class TestDescriptionExtraction:
    def test_extract_from_first_paragraph(self):
        """Description should come from the first paragraph after heading."""
        reader = KnowledgeReader()
        desc = reader._extract_description("# Title\n\nThis is the first paragraph.\n\nSecond paragraph.")
        assert "first paragraph" in desc

    def test_extract_no_paragraph(self):
        """No paragraph should return empty string."""
        reader = KnowledgeReader()
        desc = reader._extract_description("# Just a heading")
        assert desc == ""


class TestDocLoading:
    def test_read_doc_with_frontmatter(self, tmp_path: Path):
        """A .md file with frontmatter should be read correctly."""
        md_content = """---
id: custom_id
title: Custom Title
tags: [test, document]
description: A test document
---
# Heading
This is the document body."""
        path = tmp_path / "test_doc.md"
        path.write_text(md_content, encoding="utf-8")

        reader = KnowledgeReader(knowledge_path=str(tmp_path))
        doc = reader.read_doc(path)
        assert doc is not None
        assert doc.id == "custom_id"
        assert doc.title == "Custom Title"
        assert doc.tags == ["test", "document"]
        assert "document body" in doc.content
        assert doc.source_path == str(path)

    def test_read_doc_without_frontmatter(self, tmp_path: Path):
        """A .md file without frontmatter should infer metadata from content."""
        md_content = "# My Document\n\nThis is some content about microscopes."
        path = tmp_path / "my_document.md"
        path.write_text(md_content, encoding="utf-8")

        reader = KnowledgeReader(knowledge_path=str(tmp_path))
        doc = reader.read_doc(path)
        assert doc is not None
        # ID should be inferred from filename
        assert doc.id == "my_document"
        # Title should come from first heading
        assert doc.title == "My Document"

    def test_read_doc_not_found(self, tmp_path: Path):
        """Non-existent file should return None."""
        reader = KnowledgeReader()
        doc = reader.read_doc(tmp_path / "nonexistent.md")
        assert doc is None

    def test_read_all_empty_directory(self, tmp_path: Path):
        """Empty directory should return empty list."""
        reader = KnowledgeReader(knowledge_path=str(tmp_path))
        docs = reader.read_all()
        assert docs == []

    def test_read_all_multiple_docs(self, tmp_path: Path):
        """Multiple .md files should all be loaded."""
        for i in range(3):
            path = tmp_path / f"doc_{i}.md"
            path.write_text(f"# Document {i}\n\nContent {i}.", encoding="utf-8")

        reader = KnowledgeReader(knowledge_path=str(tmp_path))
        docs = reader.read_all()
        assert len(docs) == 3

    def test_id_from_filename(self):
        """Filename should be converted to a valid document ID."""
        reader = KnowledgeReader()
        # Test various filename patterns
        assert reader._id_from_filename(Path("My Document.md")) == "my_document"
        assert reader._id_from_filename(Path("显微镜使用说明.md")) == "显微镜使用说明"
        assert reader._id_from_filename(Path("part-1_intro.md")) == "part_1_intro"

    def test_search_text_property(self):
        """search_text should concatenate all searchable fields."""
        doc = KnowledgeDoc(
            id="doc_01",
            title="Test",
            description="A test document",
            content="This is the full content.",
            tags=["test", "sample"],
            source_path="/path/to/doc.md",
        )
        text = doc.search_text
        assert "doc_01" in text
        assert "Test" in text
        assert "test" in text
        assert "full content" in text
