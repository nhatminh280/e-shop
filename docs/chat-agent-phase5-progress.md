# Chat Agent Phase 5 Progress

Updated: 2026-06-10

This file tracks the current implementation progress for Phase 5 work from `docs/chatbot-full-pipeline.md`, focused on RAG knowledge retrieval and recommendation hardening in `chat-agent`.

## Current Status

Phase 5 is in progress. The local mock-agent now has policy/FAQ/product knowledge retrieval, grounded eval checks, a local hybrid knowledge index, recommendation metadata/fallback behavior, and evaluation checks for recommendation fallback tool chains.

Latest verified state:

```bash
chat-agent/.venv/bin/python -m pytest chat-agent/tests -q
```

Result:

```text
119 passed, 2 warnings
```

Eval baseline:

```text
19/19 cases passed
intent_accuracy = 1.0
slot_extraction_pass_rate = 1.0
tool_selection_pass_rate = 1.0
schema_validity_rate = 1.0
no_mutation_without_confirmation_rate = 1.0
response_type_accuracy = 1.0
fallback_rate = 0.1053
```

## Completed

### Step 1: Knowledge Documents

Done.

- Added local Markdown knowledge documents under `chat-agent/app/data/knowledge/`.
- Added loader and validation for required frontmatter, source ids, locale, heading, H2 sections, and word count.
- Added `KnowledgeDocument` schema.
- Added loader tests.

Covered sources:

- `return-refund`
- `shipping`
- `payment`
- `size-guide`
- `faq-account`
- `faq-order`
- `faq-product`

### Step 2: Mock Knowledge Retrieval

Done.

- Updated mock backend knowledge retrieval to read Markdown documents instead of old hard-coded mock JSON knowledge.
- Added retrieval tests for payment/account docs and no-match behavior.
- `knowledge.retrieve` now returns normalized document metadata such as `sourceId`, `sourceType`, `title`, `body`, and score metadata.

### Step 3.1: Intent Routing For Knowledge

Done.

- Expanded `policy_or_faq` routing for payment, account, invoice, product variant, restock, return/refund, shipping, and size-guide queries.
- Fixed review regressions:
  - English `latest order` now maps to latest order lookup.
  - Common order queries like `where is my order`, `tracking`, `shipment`, `giao hang` route to `order_status`.
  - Cart phrases like `add this variant to my cart` route to `cart_action`.
  - `I already signed in, check my order` does not get trapped by login FAQ routing.
  - Removed the old dead `variants` substring behavior by moving to safer term matching.
- Added intent and API regression tests.

### Step 3.2: Evaluation Coverage For Knowledge

Done.

- Expanded `evaluation/eval_cases.json` to cover all 7 knowledge sources.
- Added `answerContains` support in `evaluation/runner.py`.
- Added evaluation tests to lock Phase 5 source coverage.
- Eval dataset now checks grounded answer content for policy/FAQ cases.

### Step 3.3: Grounded Source Metadata And Low-Confidence Fallback

Done.

- `knowledge.retrieve` tool summaries now expose internal source metadata:
  - `sourceIds=...`
  - `scores=...`
  - `scoreTypes=...`
- Eval runner now checks expected `knowledgeSourceId`.
- Low-confidence knowledge retrieval returns `empty_result` instead of answering from a weak match.
- Added tests for source metadata, `knowledgeSourceId` eval checks, and low-confidence fallback.

### Step 3.4: Baseline Report And README Sync

Done.

- Updated `chat-agent/evaluation/baseline_report.md` from 10 to 16 cases.
- Documented full Phase 5 knowledge coverage.
- Documented evaluation checks for answer content and knowledge source ids.
- Updated `chat-agent/README.md` with eval runner notes.
- Eval runner disables LangSmith upload by default unless explicitly enabled from the shell.

### Step 4A: Vector-Ready RAG Interface

Done.

- Added `KnowledgeSearchResult` schema.
- Added `KnowledgeScoreType` with:
  - `keyword`
  - `vector`
  - `hybrid`
- `KnowledgeTool` now validates backend retrieval payloads through `KnowledgeSearchResult`.
- Keyword retrieval uses `matchedTokenCount >= 2`.
- Vector retrieval uses `score >= 0.7`.
- Invalid retrieval payloads return `validation_error`.
- Mock retrieval now emits vector-ready fields:
  - `score`
  - `scoreType`
  - `matchedTokenCount`
  - `matchedTokens`

This prepares the interface for future pgvector, Qdrant, or Spring vector endpoint integration without changing the graph.

### Step 4A.1: Local Hybrid Knowledge Index

Done.

- Added `LocalHybridKnowledgeIndex` for local/dev retrieval.
- Mock backend retrieval now uses the local hybrid index instead of direct ad hoc token scanning.
- Retrieval emits `scoreType="hybrid"` with matched token metadata.
- Ranking uses metadata, heading phrase, phrase, section order, and body-hit tie-breaks to keep broad policy queries stable while still selecting specific sections such as Cash on Delivery.
- Added tests for product and policy retrieval through the hybrid index.

### Step 4B.1: Recommendation Metadata Contract

Done.

- `ProductCard` now supports recommendation metadata:
  - `recommendationRank`
  - `recommendationScore`
  - `recommendationReason`
- `RecommendationTool` assigns stable rank/score/reason metadata.
- Tool summaries now include ranked recommendation debug info:
  - `rankedRecommendations=...`
  - `scores=...`
- Existing mock recommendation still works without a real ML service.

### Step 4B.2: Recommendation Fallback Hardening

Done.

- If `recommend.similar` returns `empty_result` or fails with a status such as `timeout`, the agent falls back to `catalog.search`.
- Fallback response still uses `responseType="recommendations"` when catalog fallback succeeds.
- Tool trace records both calls:
  - `recommend.similar`
  - `catalog.search`
- `fallbackCount` increments when fallback is used.
- Added API regression tests for recommendation `empty_result` and `timeout`.

### Step 4B.3: Evaluation Coverage For Recommendation Fallback

Done.

- Eval runner now supports exact `toolCallSequence` checks.
- Eval runner now supports expected per-tool `toolStatuses` checks.
- Eval runner now supports expected `fallbackCount` checks.
- Added evaluation regression coverage for recommender `empty_result`, `timeout`, and `validation_error` fallback.
- The fallback eval tests assert:
  - `recommend.similar`
  - `catalog.search`
  - `fallbackCount=1`
  - recommender failure status and catalog fallback success status

Targeted verification:

```bash
chat-agent/.venv/bin/python -m pytest chat-agent/tests/test_evaluation_baseline.py -q
```

Result:

```text
9 passed, 2 warnings
```

### Step 4B.4: Personalized Recommendation Path

Done.

- Added `recommend_personalized` to backend client abstractions.
- Added mock personalized recommendation strategy using recent product categories/tags when available and popular in-stock products otherwise.
- Added `RecommendationTool.personalized`.
- Recommendation routing now uses:
  - `recommend.similar` for explicit product/variant or similar-context requests.
  - `recommend.personalized` for generic recommendation requests.
- Evaluation now locks accented Vietnamese similar requests such as `gợi ý sản phẩm tương tự` to `recommend.similar`.
- Personalized recommender failures fall back to catalog search and increment `fallbackCount`.
- Added API, contract, and evaluation coverage for personalized recommendations.

### Step 5.1: RAG Ingestion Foundation For Policies FAQ

Done.

- Added deterministic `policies_faq` ingestion records for local policy/FAQ Markdown docs.
- Added section-aware chunking that preserves H1/H2 context.
- Preserved source metadata on every record.
- Added offline tests for source coverage, deterministic ids, metadata, section chunking, and duplicate-id protection.

Targeted verification:

```bash
chat-agent/.venv/bin/python -m pytest chat-agent/tests/test_knowledge_ingestion.py -q
```

Result:

```text
6 passed
```

### Step 5.2: Product Knowledge Records

Done.

- Added deterministic `products_knowledge` records derived from mock catalog products.
- Added `product` as a knowledge source type.
- Product records preserve product id, slug, category, gender, tags, colors, and sizes in metadata.
- Product knowledge text includes overview, material/care guidance, and best-use context derived from catalog fields.
- Added product knowledge API and evaluation coverage for the Patagonia Torrentshell jacket material/care query.

## Pending

### Future RAG Work

Not started.

- Add real vector database adapter or Spring vector endpoint integration.
- Add ingestion script for persisted product/policy/FAQ embeddings.
- Add citation metadata in a structured response field if the frontend/backend needs it beyond tool traces.

### Future Recommendation Work

Not started.

- Integrate real recommender service endpoint.
- Add fallback reason metadata in response/tool summary.

## Important Notes

- Current implementation is still mock-agent scoped. It does not implement real vector DB ingestion, real ML recommendation training, or real backend mutations.
- Mutating actions still remain draft-only and require confirmation.
- LangSmith upload is disabled by default only for eval runner; internal node/tool traces still work.
- The current warnings are dependency deprecation warnings, not test failures.
