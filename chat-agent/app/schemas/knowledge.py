from __future__ import annotations

from pathlib import Path
from typing import Literal

from pydantic import Field, field_validator, model_validator

from .chat import CamelModel


KnowledgeSourceType = Literal[
    "return_refund",
    "shipping",
    "payment",
    "size_guide",
    "faq_account",
    "faq_order",
    "faq_product",
    "product",
]
KnowledgeScoreType = Literal["keyword", "vector", "hybrid"]


class KnowledgeDocument(CamelModel):
    source_id: str = Field(alias="sourceId")
    source_type: KnowledgeSourceType = Field(alias="sourceType")
    title: str
    locale: str
    heading: str
    body: str
    source_path: Path = Field(alias="sourcePath")
    word_count: int = Field(alias="wordCount")

    @field_validator("source_id")
    @classmethod
    def source_id_must_be_kebab_case(cls, value: str) -> str:
        if not value or value != value.lower() or "_" in value or " " in value:
            raise ValueError("sourceId must be kebab-case")
        return value

    @field_validator("locale")
    @classmethod
    def locale_must_be_en_us(cls, value: str) -> str:
        if value != "en-US":
            raise ValueError("locale must be en-US")
        return value


class KnowledgeSearchResult(CamelModel):
    source_id: str = Field(alias="sourceId")
    source_type: KnowledgeSourceType = Field(alias="sourceType")
    title: str
    locale: str = "en-US"
    body: str
    score: float = 0
    score_type: KnowledgeScoreType = Field(default="keyword", alias="scoreType")
    matched_token_count: int = Field(default=0, alias="matchedTokenCount")
    matched_tokens: list[str] = Field(default_factory=list, alias="matchedTokens")

    @field_validator("source_id")
    @classmethod
    def source_id_must_be_kebab_case(cls, value: str) -> str:
        if not value or value != value.lower() or "_" in value or " " in value:
            raise ValueError("sourceId must be kebab-case")
        return value

    @field_validator("locale")
    @classmethod
    def locale_must_be_en_us(cls, value: str) -> str:
        if value != "en-US":
            raise ValueError("locale must be en-US")
        return value

    @model_validator(mode="after")
    def matched_token_count_matches_tokens(self) -> "KnowledgeSearchResult":
        if self.matched_tokens and self.matched_token_count == 0:
            self.matched_token_count = len(self.matched_tokens)
        return self
