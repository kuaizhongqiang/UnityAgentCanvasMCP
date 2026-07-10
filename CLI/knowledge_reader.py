"""
AgentCanvas Knowledge Reader
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Reads markdown documents from KNOWLEDGE_PATH, parses YAML frontmatter,
and provides content for the embedding index.

Supports:
- Markdown files (.md) with optional YAML frontmatter (--- delimited)
- File-based metadata extraction (filename → id, title from first heading)
- Batch reading for index construction
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger("agentcanvas.knowledge_reader")


@dataclass
class KnowledgeDoc:
    """A single knowledge document with metadata."""

    id: str
    title: str
    description: str
    content: str
    tags: List[str]
    source_path: str
    frontmatter: Dict[str, Any] = field(default_factory=dict)

    @property
    def search_text(self) -> str:
        """Concatenated text for embedding search."""
        parts = [self.id, self.title, self.description, self.content, " ".join(self.tags)]
        return " ".join(p for p in parts if p)


class KnowledgeReader:
    """
    Reads knowledge documents from a directory.

    Each .md file can have YAML frontmatter:
    ---
    id: doc_01
    title: 显微镜使用说明
    tags: [显微镜, 实验]
    description: 显微镜的正确使用方法和注意事项
    ---
    # Markdown content starts here
    ...

    If no frontmatter, metadata is inferred from the filename and first heading.
    """

    def __init__(self, knowledge_path: str = ""):
        self._knowledge_path = Path(knowledge_path) if knowledge_path else Path.cwd() / "knowledge_docs"

    # ── Frontmatter parsing ──

    def _parse_frontmatter(self, text: str) -> tuple[Dict[str, Any], str]:
        """
        Parse YAML-like frontmatter from markdown content.

        Returns (frontmatter_dict, body_text).

        This is a lightweight parser that handles simple key: value and
        key: [list] formats. For full YAML, use the 'yaml' package.
        """
        frontmatter: Dict[str, Any] = {}
        body = text

        if text.startswith("---"):
            parts = text.split("---", 2)
            if len(parts) >= 3:
                fm_text = parts[1].strip()
                body = parts[2].strip()

                for line in fm_text.split("\n"):
                    line = line.strip()
                    if not line or line.startswith("#"):
                        continue

                    # Simple key: value
                    if ":" in line:
                        key, _, value = line.partition(":")
                        key = key.strip()
                        value = value.strip()

                        # Parse list values: [a, b, c]
                        if value.startswith("[") and value.endswith("]"):
                            items = value[1:-1].split(",")
                            frontmatter[key] = [item.strip().strip("\"'") for item in items if item.strip()]
                        # Parse quoted/plain string
                        else:
                            frontmatter[key] = value.strip("\"'")

        return frontmatter, body

    def _extract_title(self, body: str) -> str:
        """Extract the first # heading from markdown body."""
        match = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
        if match:
            return match.group(1).strip()
        return ""

    def _extract_description(self, body: str, max_len: int = 200) -> str:
        """Extract a description from the first paragraph."""
        # Skip the first heading
        text = re.sub(r"^#\s+.*$", "", body, count=1, flags=re.MULTILINE).strip()
        # Take first non-empty paragraph
        paragraphs = re.split(r"\n\s*\n", text)
        for p in paragraphs:
            p = p.strip()
            if p and not p.startswith("#") and not p.startswith("!"):
                # Clean markdown formatting
                clean = re.sub(r"[*_#\[\]\(\)]", "", p)
                return clean[:max_len]
        return ""

    def _id_from_filename(self, path: Path) -> str:
        """Convert a filename to a document ID."""
        name = path.stem  # without extension
        # Convert to snake_case: "My Document.md" → "my_document"
        name = re.sub(r"[\s\-]+", "_", name)
        name = re.sub(r"[^a-zA-Z0-9_一-鿿]", "", name)
        return name.lower()

    def _extract_tags(self, body: str, frontmatter: Dict[str, Any]) -> List[str]:
        """Extract tags from frontmatter or body content."""
        if "tags" in frontmatter and isinstance(frontmatter["tags"], list):
            return frontmatter["tags"]

        # Fallback: extract hashtags from body
        tags = re.findall(r"#(\w+)", body)
        return tags[:10]  # limit to 10 tags

    # ── Document loading ──

    def read_doc(self, path: Path) -> Optional[KnowledgeDoc]:
        """Read and parse a single knowledge document."""
        if not path.exists() or not path.is_file():
            logger.warning("Knowledge doc not found: %s", path)
            return None

        try:
            text = path.read_text(encoding="utf-8")
        except Exception as e:
            logger.error("Failed to read %s: %s", path, e)
            return None

        frontmatter, body = self._parse_frontmatter(text)

        doc = KnowledgeDoc(
            id=frontmatter.get("id", self._id_from_filename(path)),
            title=frontmatter.get("title", self._extract_title(body) or path.stem),
            description=frontmatter.get("description", self._extract_description(body)),
            content=body,
            tags=self._extract_tags(body, frontmatter),
            source_path=str(path),
            frontmatter=frontmatter,
        )
        return doc

    def read_all(self) -> List[KnowledgeDoc]:
        """Read all markdown documents from the knowledge path."""
        if not self._knowledge_path.exists():
            logger.warning("Knowledge path does not exist: %s", self._knowledge_path)
            return []

        docs: List[KnowledgeDoc] = []
        for path in sorted(self._knowledge_path.glob("**/*.md")):
            doc = self.read_doc(path)
            if doc:
                docs.append(doc)
                logger.debug("Loaded knowledge doc: %s (%s)", doc.id, path.name)

        logger.info("Loaded %d knowledge docs from %s", len(docs), self._knowledge_path)
        return docs
