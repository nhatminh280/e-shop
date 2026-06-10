from __future__ import annotations

import re
from pathlib import Path

from pydantic import ValidationError

from app.schemas.knowledge import KnowledgeDocument, KnowledgeSourceType


DEFAULT_KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "data" / "knowledge"
REQUIRED_FRONTMATTER_FIELDS = {"sourceId", "sourceType", "title", "locale"}
ALLOWED_SOURCE_TYPES = set(KnowledgeSourceType.__args__)
MIN_BODY_WORDS = 800
MAX_BODY_WORDS = 1200


class KnowledgeDocumentError(ValueError):
    pass


def load_knowledge_documents(directory: Path | str = DEFAULT_KNOWLEDGE_DIR) -> list[KnowledgeDocument]:
    base_path = Path(directory)
    documents = [_load_document(path) for path in sorted(base_path.glob("*.md"))]
    return documents


def _load_document(path: Path) -> KnowledgeDocument:
    text = path.read_text(encoding="utf-8")
    frontmatter, body = _split_frontmatter(text, path)
    metadata = _parse_frontmatter(frontmatter, path)
    _validate_metadata(metadata, path)
    heading = _extract_heading(body, path)
    _validate_heading(heading, metadata["title"], path)
    _validate_body(body, path)

    try:
        return KnowledgeDocument(
            sourceId=metadata["sourceId"],
            sourceType=metadata["sourceType"],
            title=metadata["title"],
            locale=metadata["locale"],
            heading=heading,
            body=body.strip(),
            sourcePath=path,
            wordCount=len(body.split()),
        )
    except ValidationError as exc:
        raise KnowledgeDocumentError(f"{path.name}: invalid knowledge document metadata") from exc


def _split_frontmatter(text: str, path: Path) -> tuple[str, str]:
    match = re.match(r"^---\n(.*?)\n---\n(.*)$", text, flags=re.DOTALL)
    if not match:
        raise KnowledgeDocumentError(f"{path.name}: missing YAML frontmatter")
    return match.group(1), match.group(2)


def _parse_frontmatter(frontmatter: str, path: Path) -> dict[str, str]:
    metadata: dict[str, str] = {}
    for line in frontmatter.splitlines():
        if not line.strip():
            continue
        if ": " not in line:
            raise KnowledgeDocumentError(f"{path.name}: invalid frontmatter line")
        key, value = line.split(": ", 1)
        metadata[key] = value
    return metadata


def _validate_metadata(metadata: dict[str, str], path: Path) -> None:
    if set(metadata) != REQUIRED_FRONTMATTER_FIELDS:
        raise KnowledgeDocumentError(f"{path.name}: frontmatter fields must be exactly {sorted(REQUIRED_FRONTMATTER_FIELDS)}")
    if metadata["sourceId"] != path.stem:
        raise KnowledgeDocumentError(f"{path.name}: sourceId must match filename")
    if metadata["sourceType"] not in ALLOWED_SOURCE_TYPES:
        raise KnowledgeDocumentError(f"{path.name}: invalid sourceType")
    if metadata["locale"] != "en-US":
        raise KnowledgeDocumentError(f"{path.name}: locale must be en-US")


def _extract_heading(body: str, path: Path) -> str:
    stripped = body.lstrip()
    first_line = stripped.splitlines()[0] if stripped else ""
    if not first_line.startswith("# "):
        raise KnowledgeDocumentError(f"{path.name}: H1 heading must immediately follow frontmatter")
    return first_line[2:].strip()


def _validate_heading(heading: str, title: str, path: Path) -> None:
    if heading != title:
        raise KnowledgeDocumentError(f"{path.name}: H1 heading must match title")


def _validate_body(body: str, path: Path) -> None:
    heading_count = len(re.findall(r"^# ", body, flags=re.MULTILINE))
    if heading_count != 1:
        raise KnowledgeDocumentError(f"{path.name}: exactly one H1 heading is required")
    if not re.search(r"^## .+", body, flags=re.MULTILINE):
        raise KnowledgeDocumentError(f"{path.name}: at least one H2 section is required")
    word_count = len(body.split())
    if word_count < MIN_BODY_WORDS or word_count > MAX_BODY_WORDS:
        raise KnowledgeDocumentError(f"{path.name}: body word count must be between 800 and 1200")
