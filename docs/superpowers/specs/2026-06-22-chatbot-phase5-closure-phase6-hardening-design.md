# Chatbot Phase 5 Closure And Phase 6 Hardening Design

## Context

`docs/chatbot-full-pipeline.md` defines Phase 5 as RAG and recommendations, and Phase 6 as backend integration and production hardening. Current repo state already includes local RAG retrieval, local hybrid knowledge indexing, recommendation fallback behavior, personalized recommendation routing, Python observability/redaction, and a Spring chat gateway with persistence and draft action endpoints.

This design closes the reviewable Phase 5 work that can be completed inside this repo, then starts Phase 6 with minimal backend hardening. It does not claim full production readiness for infrastructure that is not present in the repo, such as a real vector database, real ML recommendation service training, a finished admin dashboard, or external load-test infrastructure.

## Goals

- Mark Phase 5 complete for local/repo-owned behavior with test evidence.
- Keep Phase 5 external dependencies explicit instead of pretending they are implemented.
- Add missing Spring client behavior for personalized recommendations.
- Preserve source and fallback metadata so low-confidence RAG/recommendation paths can be reviewed.
- Harden the Spring chat gateway with service-level tests for persistence, draft confirmation, cancellation, expiry, and unsupported actions.
- Redact sensitive data before chatbot payloads, tool traces, node traces, draft payloads, and action errors are persisted.
- Add a minimal backend review queue API for messages that need staff review, without building a dashboard UI.

## Non-Goals

- No new frontend/admin dashboard.
- No Qdrant, pgvector, or embedding provider integration.
- No real ML recommender training pipeline.
- No websocket chat transport.
- No payment or checkout execution through the chatbot.
- No broad refactor of chat graph, catalog, cart, order, or support domains.

## Phase 5 Closure Design

### Personalized Recommendation Adapter

`chat-agent/app/clients/spring_client.py` currently has `recommend_personalized()` returning an empty list. It will call a Spring backend endpoint using the same normalization and resilience style as `recommend_similar()`.

Preferred path:

- `GET /api/recommendations/personalized`

Query parameters:

- `userId`, when available
- `recentProductIds`, passed as a list
- `limit`

Behavior:

- On success, normalize the returned `products`, `recommendations`, `items`, `content`, or `data` list into agent product payloads.
- On backend error, timeout, 404, or 501, return `[]` so the graph keeps its existing catalog fallback path.
- Preserve `recommendationScore`, `recommendationRank`, and `recommendationReason` if returned.

### Fallback Reason Metadata

Recommendation fallback already routes from `recommend.similar` or `recommend.personalized` to `catalog.search`. The implementation will make the reason explicit in traceable output:

- Add `fallbackReason` to the catalog fallback tool input.
- Include the upstream recommendation tool status in the fallback reason.
- Keep `fallbackCount` incremented exactly once when fallback succeeds.
- Preserve `needsReview=true` for fallback/tool-error paths through existing review logic.

This remains trace metadata, not a new user-facing sentence unless the existing answer already explains fallback.

### Knowledge Source Metadata

Knowledge retrieval already includes `sourceIds`, `scores`, and `scoreTypes` in the tool summary. The closure work will lock this behavior with tests and documentation:

- Validate that successful policy/product knowledge responses include source metadata in `knowledge.retrieve` traces.
- Validate that low-confidence retrieval returns `empty_result`, increments fallback behavior through the graph, and marks review when appropriate.

### Documentation

`docs/chat-agent-phase5-progress.md` will move from "in progress" to "completed for local/repo-owned scope" and list the remaining external production dependencies:

- real vector database or Spring vector endpoint
- persisted embedding ingestion job
- real recommender service endpoint coverage beyond graceful adapter fallback
- optional structured citation fields if the frontend/backend needs them outside tool traces

## Phase 6 Minimal Hardening Design

### Chat Gateway Service Tests

The backend already has controller tests for `ChatGatewayController`. Phase 6 hardening will add service-level tests around `ChatGatewayService` because the highest-risk behavior is in persistence and draft execution.

Tests will cover:

- `sendMessage()` creates or loads a session, persists the user message, calls `ChatAgentClient`, persists assistant message, tool calls, node traces, and draft action.
- If `ChatAgentClient` throws `ChatAgentUnavailableException`, the service persists a fallback assistant response instead of failing the whole request.
- `confirmAction()` completes supported draft actions and writes an action-result message.
- `confirmAction()` marks expired drafts as expired and returns the expected conflict/gone behavior.
- `confirmAction()` rejects unsupported action types without executing domain services.
- `cancelAction()` only cancels pending owned drafts.

The first implementation pass will use Mockito tests against repositories and domain services. It will not require a real database unless existing backend test infrastructure already provides one cheaply.

### Persistence Redaction

The Python agent already redacts logs and traces before returning tool/node trace fields. The Spring gateway still persists request/response payload JSON and errors, so it needs its own final persistence boundary redaction.

Add a small backend utility, for example `ChatPayloadRedactor`, under `com.eshop.api.chatgateway.service` or `com.eshop.api.chatgateway.util`.

It will recursively redact:

- sensitive keys: `authorization`, `token`, `accessToken`, `refreshToken`, `jwt`, `password`, `secret`, `apiKey`, `cookie`, `email`, `phone`, `address`, `payment`, `card`, `cardNumber`, `cvv`, `cvc`
- sensitive string patterns: bearer/basic credentials, JWT-like strings, token query parameters, email addresses, Vietnam phone numbers, and Luhn-valid card numbers

Apply it before persisting:

- user request payload JSON
- assistant response payload JSON
- tool call `inputJson`
- tool call `requestSummary`, `responseSummary`, `errorMessage`
- node trace summaries and errors
- draft payload/result JSON
- action failure errors

Trace IDs, request IDs, session IDs, UUIDs, counts, product IDs, order numbers, and non-sensitive numeric values must remain unchanged.

### Minimal Review Queue API

Phase 6 docs mention dashboard/admin review inputs for low-confidence conversations. This scope will implement only backend API foundations.

Add read-only service/query support for reviewable chat messages:

- Messages where assistant payload has `needsReview=true`
- OR `fallbackCount > 0`
- OR `responseType` is `tool_error` or `fallback`
- OR persisted tool calls for the message contain non-success statuses such as `timeout`, `backend_error`, or `validation_error`

Endpoint:

- `GET /api/chat/review/messages?page=0&size=50`

Response shape:

- message id
- session id
- user id, if present
- body
- intent
- response type
- trace id
- fallback count
- created at
- review reasons

This endpoint should be authenticated like other backend APIs. Role-specific authorization can be added later if the existing security setup has an established admin annotation/pattern that can be applied safely during implementation.

### Documentation

Update `docs/chatbot-full-pipeline.md` or a companion progress note to state:

- Phase 5 local scope is complete.
- Phase 6 backend hardening has started with persistence tests, redaction, and review queue APIs.
- Full Phase 6 production completion still requires load tests, operational dashboard wiring, and production infrastructure validation.

## Data Flow

1. React or API client calls Spring `POST /api/chat/messages`.
2. Spring creates/loads a chat session and persists the redacted user message payload.
3. Spring calls Python `POST /agent/chat` through `ChatAgentClient`, forwarding auth and trace headers.
4. Python agent calls mock or Spring backend tools, emits structured answer, traces, draft actions, fallback counts, and review flags.
5. Spring redacts and persists assistant response, tool calls, node traces, and draft action.
6. If the user confirms a draft, Spring validates ownership/status/expiry and executes the mapped domain service.
7. Review API lists assistant messages that are low-confidence, fallback-heavy, or tool-error affected.

## Error Handling

- Python agent unavailable: Spring persists fallback response with `fallbackCount=1` and `responseType=tool_error`.
- Backend recommendation unavailable: Python Spring client returns `[]`; graph falls back to catalog search.
- Low-confidence knowledge: `knowledge.retrieve` returns `empty_result`; graph returns fallback/review behavior.
- Expired draft: status changes to `EXPIRED`; confirmation returns the existing API error behavior.
- Unsupported draft action: status becomes `FAILED` only if the current service behavior reaches execution; no domain service is called.
- Redaction failures: redactor must be defensive and preserve valid JSON shape. If a value cannot be parsed as a known structure, it is treated as a scalar string/value.

## Testing Strategy

### Python Chat Agent

- Add failing tests first for `SpringBackendClient.recommend_personalized()`.
- Add tests for fallback reason metadata in recommendation fallback traces.
- Add tests that knowledge retrieval source metadata remains present.
- Run `chat-agent/.venv/bin/python -m pytest chat-agent/tests -q`.

### Spring Backend

- Add unit tests for redaction utility covering nested maps/lists, text patterns, and non-sensitive trace IDs.
- Add service tests for `ChatGatewayService` persistence and draft action behavior.
- Add controller/service tests for review queue endpoint.
- Run targeted backend chatgateway tests first.
- Run full backend tests with `cd backend/e-shop && ./mvnw test` when environment allows.

## Review Notes

This scope intentionally favors contract tests and persistence boundary tests over new UI surface area. The goal is to make review by a stronger model straightforward: each behavior has a narrow test, each production claim is backed by code, and external infrastructure gaps remain documented instead of hidden.
