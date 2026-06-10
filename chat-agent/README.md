# E-Shop AI Chat Agent

Standalone FastAPI service for the e-commerce chatbot. Phase 2 is scoped to the Python agent only: mock/Spring client abstractions, tool routing, draft actions, memory, structured errors, and contract tests. It does not implement real backend mutations, database access, checkout, ML recommender training, or RAG ingestion.

## Run

```bash
cd chat-agent
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --reload --port 8010
```

Health check:

```bash
curl http://127.0.0.1:8010/agent/health
```

Chat:

```bash
curl -X POST http://127.0.0.1:8010/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"demo","message":"ao khoac den size M"}'
```

Follow-up cart draft using memory:

```bash
curl -X POST http://127.0.0.1:8010/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"sessionId":"demo","message":"them cai dau tien vao gio"}'
```

## Backend Mode

Mock mode is the default:

```bash
USE_MOCK_BACKEND=true python -m uvicorn app.main:app --reload --port 8010
```

HTTP backend mode is enabled only by env var:

```bash
USE_MOCK_BACKEND=false \
BACKEND_BASE_URL=http://localhost:8080 \
BACKEND_TIMEOUT_SECONDS=2 \
BACKEND_RETRIES=1 \
BACKEND_CIRCUIT_FAILURE_THRESHOLD=3 \
BACKEND_CIRCUIT_COOLDOWN_SECONDS=10 \
python -m uvicorn app.main:app --reload --port 8010
```

The Spring client is an HTTPX adapter only. It does not implement backend business logic and does not write to a database.
The circuit breaker stops short-lived retry storms when the backend is unavailable; after the cooldown it allows a probe request and resets on success.

## Phase 2 Status

Phase 2 is complete for the Python chat agent:

- mock backend mode works without Spring Boot
- Spring backend mode uses the same client interface
- catalog, recommendation, cart, order, support, and knowledge tools return normalized `ToolResult` values
- cart add/update/remove and support handoff always return draft actions
- tool failures map to structured response types instead of crashing the graph
- backend payload contract tests cover valid, empty, malformed, unauthorized, timeout, and server-error cases

## Architecture

```text
app/main.py
app/clients/
  base_client.py
  mock_backend_client.py
  spring_client.py
app/tools/
  base.py
  catalog_tool.py
  recommendation_tool.py
  cart_tool.py
  order_tool.py
  support_tool.py
  knowledge_tool.py
app/graph/
  state.py
  nodes.py
  workflow.py
app/services/
  draft_service.py
  memory_service.py
  trace_service.py
app/utils/
  intent_rules.py
  language.py
  slot_parser.py
```

## Draft Actions

Mutating requests never execute immediately. Cart add/update/remove and support handoff return:

- `responseType="draft_action"` or `responseType="handoff"`
- `needsConfirmation=true`
- `draftAction.status="pending"`
- `draftAction.expiresAt`

Supported draft action types:

- `cart.add`
- `cart.update_quantity`
- `cart.remove_item`
- `support.handoff`

The draft service provides `create_draft_action()`, `validate_draft_action()`, `expire_draft_action()`, `complete_draft_action()`, `cancel_draft_action()`, and `fail_draft_action()`.

Draft statuses:

- `pending`
- `completed`
- `cancelled`
- `expired`
- `failed`

## Conversation Memory

The in-memory session store tracks:

- previous products shown
- previous tool results
- last intent
- last assistant response
- last selected product/order when available

This allows follow-ups such as `them cai dau tien vao gio`, `san pham do`, `xoa no di`, or `tang so luong len 2` after a product search.

## Tool Routing And Errors

The graph classifies intent, extracts slots, resolves context, routes to a domain tool, and formats a structured response. Tool statuses are standardized:

- `success`
- `empty_result`
- `timeout`
- `unauthorized`
- `backend_error`
- `validation_error`

The graph converts tool failures into response types such as `empty_result`, `auth_required`, or `tool_error` instead of crashing.

## Trace IDs

Every request has a `traceId`. If `POST /agent/chat` receives `traceId`, the service reuses it; otherwise it generates one.

Every chat response includes:

- `traceId`
- `sessionId`
- `intent`
- `toolCalls`
- `nodeTraces`
- `latencyMs`
- `fallbackCount`

Each tool call trace includes `toolName`, `traceId`, `status`, `latencyMs`, request/response summaries, and an error message when present. Each node trace includes `nodeName`, `status`, `latencyMs`, input/output summaries, and error fields.

## Observability

The service auto-loads `chat-agent/.env` on startup. Runtime environment variables still win over `.env` values.

LangSmith tracing is enabled with:

```bash
LANGSMITH_TRACING=true
LANGSMITH_API_KEY=...
LANGSMITH_PROJECT=e-shop-chat-agent
```

Local verification:

```bash
cd chat-agent
.venv/bin/python -m uvicorn app.main:app --reload --port 8010
curl -X POST http://127.0.0.1:8010/agent/chat \
  -H "Content-Type: application/json" \
  -H "x-trace-id: trace-local-check" \
  -H "x-request-id: req-local-check" \
  -H "x-session-id: session-local-check" \
  -d '{"message":"ao khoac den size M"}'
```

Check LangSmith project `e-shop-chat-agent` for metadata `traceId=trace-local-check`.

OpenTelemetry spans/exporters are not implemented in the current scope. The agent still accepts and forwards trace-compatible headers:

- `traceparent`
- `x-trace-id`
- `x-request-id`
- `x-session-id`

Structured JSON logs are enabled by default. Each request, node, and tool log includes available fields such as `traceId`, `trace_id`, `sessionId`, `session_id`, `userId`, `user_id`, `node`, `intent`, `toolName`, `tool_name`, `status`, `latencyMs`, `latency_ms`, `errorClass`, `error_class`, `errorMessage`, and `error_message`.

Disable JSON logs or change level with:

```bash
CHAT_AGENT_JSON_LOGS=false
CHAT_AGENT_LOG_LEVEL=DEBUG
```

Logs and traces are redacted for sensitive fields such as `Authorization`, tokens, passwords, phone, address, payment/card data, and email.

Prometheus-compatible metrics are available at:

```bash
curl http://127.0.0.1:8010/agent/metrics
```

Metrics include:

- `agent_request_total`
- `agent_request_by_path_total`
- `agent_latency_ms`
- `agent_node_latency_ms`
- `agent_tool_latency_ms`
- `agent_tool_error_total`
- `agent_fallback_total`
- `agent_intent_total`
- `agent_response_type_total`
- `agent_draft_action_total`

Example checks:

```bash
curl http://127.0.0.1:8010/agent/metrics | grep agent_request_total
curl http://127.0.0.1:8010/agent/metrics | grep agent_tool_error_total
```

## Test

```bash
cd chat-agent
.venv/bin/python -m pytest -v
```

Coverage includes product search, recommendations, add/update/remove cart drafts, support handoff drafts, draft expiration/cancel/complete/fail, contextual references, unauthorized order lookup, empty result handling, timeout fallback, malformed backend payload handling, memory behavior, and backend payload contract checks.

## Phase 3 Evaluation

Phase 3 adds observability and a lightweight evaluation baseline without adding RAG ingestion, ML training, or real backend writes.

Files:

- `evaluation/eval_cases.json` stores regression cases.
- `evaluation/runner.py` runs the dataset and computes metrics.
- `evaluation/baseline_report.md` records the current baseline.
- `tests/test_evaluation_baseline.py` locks the evaluation in pytest.

Run the evaluation report:

```bash
cd chat-agent
.venv/bin/python -m evaluation.runner
```

The evaluation runner is offline by default: it disables LangSmith upload unless tracing is explicitly enabled in the shell. To upload eval traces intentionally, run with:

```bash
LANGSMITH_TRACING=true .venv/bin/python -m evaluation.runner
```

The prompt-compatible runner path also works:

```bash
.venv/bin/python -m app.evaluation.run_eval
```

The baseline tracks:

- intent accuracy
- slot extraction pass rate
- tool selection pass rate
- schema validity rate
- no-mutation-without-confirmation rate
- fallback rate
- grounded answer substring checks for policy/FAQ cases
- knowledge source id checks for `knowledge.retrieve`

Recommendation coverage includes `recommend.similar` for contextual product requests and `recommend.personalized` for generic recommendation requests. Both paths return ranked product cards and use catalog fallback when the recommender returns no usable result.

## Local RAG Knowledge

The mock agent uses local retrieval for Phase 5 development:

- policy, FAQ, shipping, payment, return/refund, and size-guide docs are loaded from `app/data/knowledge/*.md`
- product knowledge records are derived from the mock catalog
- `app.knowledge.ingestion` builds deterministic `policies_faq` and `products_knowledge` records
- `app.knowledge.vector_index.LocalHybridKnowledgeIndex` ranks records locally and returns `scoreType="hybrid"`
- `knowledge.retrieve` validates every payload through `KnowledgeSearchResult` and returns source ids in tool traces

Targeted RAG tests:

```bash
cd chat-agent
.venv/bin/python -m pytest tests/test_knowledge_loader.py tests/test_knowledge_ingestion.py tests/test_knowledge_vector_index.py tests/test_knowledge_retrieval.py -q
```

## Out Of Scope

The current Phase 2/3/5 mock-agent scope does not implement payment, checkout, real database access, real websocket support, production auth, Qdrant/pgvector persistence, or ML recommender training.
