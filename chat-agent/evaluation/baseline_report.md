# Phase 3 Evaluation Baseline

Generated from:

```bash
.venv/bin/python -m evaluation.runner
```

Current baseline:

| Metric | Value |
| --- | ---: |
| Total cases | 19 |
| Passed cases | 19 |
| Intent accuracy | 1.0 |
| Slot extraction pass rate | 1.0 |
| Tool selection pass rate | 1.0 |
| Schema validity rate | 1.0 |
| No-mutation-without-confirmation rate | 1.0 |
| Response type accuracy | 1.0 |
| Fallback rate | 0.1053 |

Dataset coverage:

- product search
- size/color/price filtering
- recommendation with prior product context
- accented Vietnamese similar recommendation routing
- personalized recommendation without explicit product context
- authenticated order lookup
- latest order lookup
- cart add/update draft actions
- support handoff draft action
- policy/FAQ retrieval across all local knowledge sources
- product knowledge retrieval from local catalog-derived records
- grounded policy/FAQ answer content checks
- knowledge source id checks from `knowledge.retrieve` tool traces
- recommendation fallback regression coverage for `empty_result`, `timeout`, and `validation_error`
- malformed prompt guardrail

Phase 5 knowledge coverage:

- `return-refund`
- `shipping`
- `payment`
- `size-guide`
- `faq-account`
- `faq-order`
- `faq-product`
- `product-p003` product knowledge eval coverage

Evaluation checks:

- expected intent
- expected response type
- required slots
- expected tool calls
- exact tool-call sequence when `toolCallSequence` is specified
- per-tool statuses when `toolStatuses` is specified
- answer substring for grounded policy/FAQ answers
- `knowledgeSourceId` surfaced by `knowledge.retrieve`
- expected `fallbackCount` when specified
- no mutation without explicit confirmation

The fallback rate includes expected fallback-style outcomes such as empty product results and overlong malformed input.
