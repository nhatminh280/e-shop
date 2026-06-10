from __future__ import annotations

import pytest

from app.knowledge.loader import KnowledgeDocumentError, load_knowledge_documents


def test_loads_seed_knowledge_documents() -> None:
    documents = load_knowledge_documents()

    assert len(documents) == 7
    assert {document.source_id for document in documents} == {
        "faq-account",
        "faq-order",
        "faq-product",
        "payment",
        "return-refund",
        "shipping",
        "size-guide",
    }

    shipping = next(document for document in documents if document.source_id == "shipping")
    assert shipping.source_type == "shipping"
    assert shipping.title == "Shipping Policy"
    assert shipping.locale == "en-US"
    assert shipping.heading == "Shipping Policy"
    assert "**Standard.** 3 to 5 business days" in shipping.body
    assert shipping.word_count >= 800


def test_rejects_frontmatter_source_id_that_does_not_match_filename(tmp_path) -> None:
    path = tmp_path / "shipping.md"
    path.write_text(
        """---
sourceId: wrong-id
sourceType: shipping
title: Shipping Policy
locale: en-US
---

# Shipping Policy

Intro text.

## Delivery

Standard delivery takes 3 to 5 business days.
""",
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeDocumentError, match="sourceId must match filename"):
        load_knowledge_documents(tmp_path)


def test_rejects_unknown_or_extra_frontmatter_fields(tmp_path) -> None:
    path = tmp_path / "payment.md"
    path.write_text(
        """---
sourceId: payment
sourceType: payment
title: Payment Methods and Policy
locale: en-US
tags: payment
---

# Payment Methods and Policy

Intro text.

## Methods

We accept card payments and cash on delivery.
""",
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeDocumentError, match="frontmatter fields must be exactly"):
        load_knowledge_documents(tmp_path)


def test_rejects_missing_h2_section(tmp_path) -> None:
    path = tmp_path / "size-guide.md"
    path.write_text(
        """---
sourceId: size-guide
sourceType: size_guide
title: Size Guide
locale: en-US
---

# Size Guide

Only an intro paragraph.
""",
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeDocumentError, match="at least one H2"):
        load_knowledge_documents(tmp_path)


def test_rejects_heading_that_does_not_match_title(tmp_path) -> None:
    path = tmp_path / "faq-account.md"
    path.write_text(
        """---
sourceId: faq-account
sourceType: faq_account
title: Account FAQ
locale: en-US
---

# Wrong Heading

## Sign In

""" + "Account help. " * 850,
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeDocumentError, match="H1 heading must match title"):
        load_knowledge_documents(tmp_path)


def test_rejects_body_outside_mvp_word_count_range(tmp_path) -> None:
    path = tmp_path / "faq-product.md"
    path.write_text(
        """---
sourceId: faq-product
sourceType: faq_product
title: Product FAQ
locale: en-US
---

# Product FAQ

## Stock

Short body.
""",
        encoding="utf-8",
    )

    with pytest.raises(KnowledgeDocumentError, match="body word count must be between 800 and 1200"):
        load_knowledge_documents(tmp_path)
