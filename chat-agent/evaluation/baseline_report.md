# Phase 3 Evaluation Baseline

Generated from:

```bash
.venv/bin/python -m evaluation.runner
```

Current baseline:

| Metric | Value |
| --- | ---: |
| Total cases | 10 |
| Passed cases | 10 |
| Intent accuracy | 1.0 |
| Slot extraction pass rate | 1.0 |
| Tool selection pass rate | 1.0 |
| Schema validity rate | 1.0 |
| No-mutation-without-confirmation rate | 1.0 |
| Response type accuracy | 1.0 |
| Fallback rate | 0.2 |

Dataset coverage:

- product search
- size/color/price filtering
- recommendation with prior product context
- authenticated order lookup
- latest order lookup
- cart add/update draft actions
- support handoff draft action
- policy/FAQ retrieval
- malformed prompt guardrail

The fallback rate includes expected fallback-style outcomes such as empty product results and overlong malformed input.
