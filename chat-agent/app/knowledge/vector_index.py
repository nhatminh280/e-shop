from __future__ import annotations

import re

from app.knowledge.ingestion import KnowledgeIngestionRecord


_STOPWORDS = {
    "a",
    "an",
    "and",
    "do",
    "for",
    "how",
    "i",
    "is",
    "my",
    "of",
    "on",
    "or",
    "the",
    "to",
    "what",
}


class LocalHybridKnowledgeIndex:
    def __init__(self, records: list[KnowledgeIngestionRecord]) -> None:
        self.records = records

    @classmethod
    def from_records(cls, records: list[KnowledgeIngestionRecord]) -> "LocalHybridKnowledgeIndex":
        return cls(records)

    def retrieve(self, query: str, limit: int = 2) -> list[dict]:
        query_tokens = _tokens(query)
        raw_phrases = _phrases(query)
        scored: list[tuple[float, int, int, int, int, int, KnowledgeIngestionRecord, list[str]]] = []
        for record in self.records:
            metadata_text = _metadata_text(record)
            body_text = record.text.lower()
            matched_tokens = sorted(
                token
                for token in query_tokens
                if token in metadata_text or token in body_text
            )
            if not matched_tokens:
                continue
            lexical_score = len(matched_tokens) / max(len(query_tokens), 1)
            metadata_hit_count = sum(1 for token in matched_tokens if token in metadata_text)
            metadata_boost = 0.15 * metadata_hit_count
            heading_phrase_hit_count = sum(_heading_text(record.text).count(phrase) for phrase in raw_phrases)
            phrase_hit_count = sum(body_text.count(phrase) for phrase in raw_phrases)
            body_hit_count = sum(body_text.count(token) for token in matched_tokens)
            score = min(1.0, lexical_score + metadata_boost)
            scored.append(
                (
                    score,
                    metadata_hit_count,
                    heading_phrase_hit_count,
                    phrase_hit_count,
                    -record.chunk_index,
                    body_hit_count,
                    record,
                    matched_tokens,
                )
            )

        scored.sort(key=lambda item: (item[0], item[1], item[2], item[3], item[4], item[5], len(item[7])), reverse=True)
        return [_result_for(record, score, matched_tokens) for score, _, _, _, _, _, record, matched_tokens in scored[:limit]]


def _result_for(record: KnowledgeIngestionRecord, score: float, matched_tokens: list[str]) -> dict:
    return {
        "sourceId": record.source_id,
        "sourceType": record.source_type,
        "title": record.title,
        "locale": record.locale,
        "body": record.text,
        "score": round(score, 4),
        "scoreType": "hybrid",
        "matchedTokenCount": len(matched_tokens),
        "matchedTokens": matched_tokens,
    }


def _metadata_text(record: KnowledgeIngestionRecord) -> str:
    values = [
        record.source_id,
        record.source_type,
        record.title,
        *[str(value) for value in record.metadata.values() if isinstance(value, str)],
    ]
    return " ".join(values).lower()


def _tokens(text: str) -> set[str]:
    tokens = {token for token in re.findall(r"[a-z0-9]+", text.lower()) if token}
    return {token for token in tokens if token not in _STOPWORDS}


def _heading_text(text: str) -> str:
    return " ".join(line for line in text.lower().splitlines() if line.startswith("#"))


def _phrases(text: str) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", text.lower())
    phrases: list[str] = []
    for size in range(min(4, len(tokens)), 1, -1):
        phrases.extend(" ".join(tokens[index:index + size]) for index in range(len(tokens) - size + 1))
    return phrases
