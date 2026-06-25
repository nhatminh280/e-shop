# Chatbot Phase 5 Closure And Phase 6 Hardening Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the repo-owned Phase 5 chatbot work and start Phase 6 with review-safe backend hardening, redaction, and review queue APIs.

**Architecture:** Keep Python chat-agent changes small and contract-oriented: Spring client adapters plus trace metadata tests. Keep Spring Boot changes at persistence boundaries: a redactor utility, service-level gateway tests, and a read-only review queue API layered through DTO/repository/service/controller.

**Tech Stack:** Python 3, FastAPI/Pydantic, pytest, httpx, Java 17, Spring Boot, JPA repositories, Mockito/JUnit, Maven.

---

## File Structure

Python Phase 5 files:

- Modify `chat-agent/app/clients/spring_client.py`: implement `recommend_personalized()` through Spring backend.
- Modify `chat-agent/app/graph/nodes.py`: add explicit `fallbackReason` to recommendation fallback trace input.
- Modify `chat-agent/tests/test_spring_client.py`: add personalized recommendation contract tests.
- Modify `chat-agent/tests/test_agent_api.py`: add fallback reason trace test.
- Modify `chat-agent/tests/test_knowledge_retrieval.py`: lock source metadata trace behavior if no existing test already covers it.
- Modify `docs/chat-agent-phase5-progress.md`: mark repo-owned Phase 5 complete and list external dependencies.

Spring Phase 6 files:

- Create `backend/e-shop/src/main/java/com/eshop/api/chatgateway/util/ChatPayloadRedactor.java`: redacts JSON and strings before persistence.
- Test `backend/e-shop/src/test/java/com/eshop/api/chatgateway/util/ChatPayloadRedactorTest.java`.
- Modify `backend/e-shop/src/main/java/com/eshop/api/chatgateway/service/ChatGatewayService.java`: apply redaction at persistence boundaries.
- Test `backend/e-shop/src/test/java/com/eshop/api/chatgateway/service/ChatGatewayServiceTest.java`: service-level send, fallback, draft confirm/cancel/expiry/unsupported behavior.
- Create `backend/e-shop/src/main/java/com/eshop/api/chatgateway/dto/ChatReviewMessageResponse.java`: review queue row DTO.
- Modify `backend/e-shop/src/main/java/com/eshop/api/chatgateway/repository/ChatMessageRepository.java`: add review query.
- Modify `backend/e-shop/src/main/java/com/eshop/api/chatgateway/repository/ChatToolCallRepository.java`: add non-success statuses query.
- Modify `backend/e-shop/src/main/java/com/eshop/api/chatgateway/service/ChatGatewayService.java`: add `getReviewMessages()`.
- Modify `backend/e-shop/src/main/java/com/eshop/api/chatgateway/controller/ChatGatewayController.java`: add `GET /api/chat/review/messages`.
- Modify `backend/e-shop/src/test/java/com/eshop/api/chatgateway/controller/ChatGatewayControllerTest.java`: add review endpoint controller test.
- Modify `docs/chatbot-full-pipeline.md`: document Phase 5 complete locally and Phase 6 minimal hardening started.

## Task 1: Spring Personalized Recommendation Adapter

**Files:**
- Modify: `chat-agent/tests/test_spring_client.py`
- Modify: `chat-agent/app/clients/spring_client.py`

- [ ] **Step 1: Write the failing personalized recommendation success test**

Append to `chat-agent/tests/test_spring_client.py`:

```python
def test_spring_client_uses_personalized_recommendation_endpoint(monkeypatch: pytest.MonkeyPatch) -> None:
    captured_url = ""
    captured_params: dict[str, Any] | None = None

    class CapturingClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def request(self, method, url, params=None, json=None, headers=None):
            nonlocal captured_url, captured_params
            captured_url = url
            captured_params = params
            return httpx.Response(
                200,
                json={
                    "recommendations": [
                        {
                            "productId": "p009",
                            "variantId": "v009",
                            "productName": "Trail Shirt",
                            "productSlug": "trail-shirt",
                            "category": "shirts",
                            "gender": "unisex",
                            "price": 250000,
                            "inStock": True,
                            "stock": 8,
                            "recommendationRank": 1,
                            "recommendationScore": 0.91,
                            "recommendationReason": "personalized by recent views",
                        }
                    ]
                },
                request=httpx.Request(method, url),
            )

    monkeypatch.setattr(httpx, "Client", CapturingClient)
    client = SpringBackendClient(base_url="http://backend", retries=0)

    [product] = client.recommend_personalized(user_id="user-1", recent_product_ids=["p001", "p002"], limit=3)

    assert captured_url == "http://backend/api/recommendations/personalized"
    assert captured_params == {"userId": "user-1", "recentProductIds": ["p001", "p002"], "limit": 3}
    assert product["productId"] == "p009"
    assert product["recommendationScore"] == 0.91
    assert product["recommendationReason"] == "personalized by recent views"
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
cd chat-agent && .venv/bin/python -m pytest tests/test_spring_client.py::test_spring_client_uses_personalized_recommendation_endpoint -q
```

Expected: FAIL because `recommend_personalized()` currently returns `[]`.

- [ ] **Step 3: Write the unavailable-backend fallback test**

Append to `chat-agent/tests/test_spring_client.py`:

```python
def test_spring_client_returns_empty_personalized_recommendations_when_backend_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnavailableClient:
        def __init__(self, timeout):
            pass

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return False

        def request(self, method, url, params=None, json=None, headers=None):
            return httpx.Response(501, json={"error": "not implemented"}, request=httpx.Request(method, url))

    monkeypatch.setattr(httpx, "Client", UnavailableClient)
    client = SpringBackendClient(base_url="http://backend", retries=0)

    assert client.recommend_personalized(user_id="user-1", recent_product_ids=["p001"], limit=4) == []
```

- [ ] **Step 4: Run fallback test to verify RED/behavior gap**

Run:

```bash
cd chat-agent && .venv/bin/python -m pytest tests/test_spring_client.py::test_spring_client_returns_empty_personalized_recommendations_when_backend_unavailable -q
```

Expected before implementation: PASS is acceptable here because the current empty implementation is already fallback-safe. The success test remains the RED test for this task.

- [ ] **Step 5: Implement minimal `recommend_personalized()`**

In `chat-agent/app/clients/spring_client.py`, replace:

```python
    def recommend_personalized(
        self,
        user_id: str | None = None,
        recent_product_ids: list[str] | None = None,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        return []
```

with:

```python
    def recommend_personalized(
        self,
        user_id: str | None = None,
        recent_product_ids: list[str] | None = None,
        limit: int = 4,
    ) -> list[dict[str, Any]]:
        params = {
            "userId": user_id,
            "recentProductIds": recent_product_ids or [],
            "limit": limit,
        }
        try:
            payload = self._get("/api/recommendations/personalized", {key: value for key, value in params.items() if value})
        except BackendClientError:
            return []
        return [_normalize_product(product) for product in _extract_list(payload, "products")]
```

- [ ] **Step 6: Run adapter tests to verify GREEN**

Run:

```bash
cd chat-agent && .venv/bin/python -m pytest tests/test_spring_client.py -q
```

Expected: all `test_spring_client.py` tests pass.

- [ ] **Step 7: Commit**

```bash
git add chat-agent/tests/test_spring_client.py chat-agent/app/clients/spring_client.py
git commit -m "Complete personalized recommendation adapter"
```

## Task 2: Recommendation Fallback Reason Metadata

**Files:**
- Modify: `chat-agent/tests/test_agent_api.py`
- Modify: `chat-agent/app/graph/nodes.py`

- [ ] **Step 1: Write the failing API trace test**

Append to `chat-agent/tests/test_agent_api.py`:

```python
def test_recommendation_fallback_trace_includes_reason() -> None:
    response = client.post(
        "/agent/chat",
        json={"sessionId": "fallback-reason-session", "message": "recommend timeout fallback"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["responseType"] == "recommendations"
    fallback_tool = next(tool for tool in body["toolCalls"] if tool["toolName"] == "catalog.search")
    assert fallback_tool["input"]["fallbackFor"] == "recommend.personalized"
    assert fallback_tool["input"]["fallbackReason"] == "recommend.personalized returned timeout"
    assert body["fallbackCount"] == 1
    assert body["needsReview"] is True
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
cd chat-agent && .venv/bin/python -m pytest tests/test_agent_api.py::test_recommendation_fallback_trace_includes_reason -q
```

Expected: FAIL because `fallbackReason` is not present in catalog fallback tool input.

- [ ] **Step 3: Implement minimal fallback reason**

In `chat-agent/app/graph/nodes.py`, inside `_handle_recommendation()`, before the `catalog.search` fallback `call_tool`, add:

```python
    fallback_reason = f"{tool_name} returned {result.status}"
```

Change the fallback `call_tool` input from:

```python
        {"query": "", "filters": {"in_stock": True}, "fallbackFor": tool_name},
```

to:

```python
        {"query": "", "filters": {"in_stock": True}, "fallbackFor": tool_name, "fallbackReason": fallback_reason},
```

- [ ] **Step 4: Run targeted test to verify GREEN**

Run:

```bash
cd chat-agent && .venv/bin/python -m pytest tests/test_agent_api.py::test_recommendation_fallback_trace_includes_reason -q
```

Expected: PASS.

- [ ] **Step 5: Run recommendation/eval regression tests**

Run:

```bash
cd chat-agent && .venv/bin/python -m pytest tests/test_agent_api.py tests/test_evaluation_baseline.py -q
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add chat-agent/tests/test_agent_api.py chat-agent/app/graph/nodes.py
git commit -m "Expose recommendation fallback reasons"
```

## Task 3: Lock Knowledge Source Metadata And Close Phase 5 Docs

**Files:**
- Modify: `chat-agent/tests/test_knowledge_retrieval.py`
- Modify: `docs/chat-agent-phase5-progress.md`

- [ ] **Step 1: Write source metadata test if not already present**

Append to `chat-agent/tests/test_knowledge_retrieval.py` unless an equivalent assertion already exists:

```python
def test_knowledge_tool_summary_includes_source_metadata() -> None:
    tool = KnowledgeTool(MockBackendClient())

    result = tool.retrieve("How long does shipping take?")

    assert result.status == "success"
    assert "sourceIds=shipping" in result.summary
    assert "scores=" in result.summary
    assert "scoreTypes=" in result.summary
```

Ensure these imports exist at the top of the file:

```python
from app.clients.mock_backend_client import MockBackendClient
from app.tools.knowledge_tool import KnowledgeTool
```

- [ ] **Step 2: Run source metadata test**

Run:

```bash
cd chat-agent && .venv/bin/python -m pytest tests/test_knowledge_retrieval.py::test_knowledge_tool_summary_includes_source_metadata -q
```

Expected: PASS if behavior is already present. If it fails, fix only the summary in `chat-agent/app/tools/knowledge_tool.py` to emit `sourceIds=...; scores=...; scoreTypes=...`.

- [ ] **Step 3: Update Phase 5 docs**

In `docs/chat-agent-phase5-progress.md`, change the current status paragraph from:

```markdown
Phase 5 is in progress. The local mock-agent now has policy/FAQ/product knowledge retrieval, grounded eval checks, a local hybrid knowledge index, recommendation metadata/fallback behavior, and evaluation checks for recommendation fallback tool chains.
```

to:

```markdown
Phase 5 is complete for the repo-owned local scope. The local mock-agent has policy/FAQ/product knowledge retrieval, grounded eval checks, a local hybrid knowledge index, recommendation metadata/fallback behavior, personalized recommendation routing, Spring personalized recommendation adapter coverage, and evaluation checks for recommendation fallback tool chains.
```

Replace the `## Pending` section with:

```markdown
## External Production Dependencies

These items are intentionally not claimed as complete in the local Phase 5 scope because they require production infrastructure or service ownership outside the chat-agent code:

- Add a real vector database adapter or Spring vector endpoint integration.
- Add persisted embedding ingestion for product, policy, and FAQ records.
- Integrate a real ML recommender service endpoint beyond graceful adapter fallback.
- Add structured citation fields in API responses if the frontend/backend needs them outside tool traces.
```

- [ ] **Step 4: Run docs-related tests**

Run:

```bash
cd chat-agent && .venv/bin/python -m pytest tests/test_knowledge_retrieval.py tests/test_evaluation_baseline.py -q
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add chat-agent/tests/test_knowledge_retrieval.py docs/chat-agent-phase5-progress.md
git commit -m "Close local chatbot phase five scope"
```

Use `git add -f docs/chat-agent-phase5-progress.md` if docs are ignored.

## Task 4: Java Chat Payload Redactor

**Files:**
- Create: `backend/e-shop/src/main/java/com/eshop/api/chatgateway/util/ChatPayloadRedactor.java`
- Create: `backend/e-shop/src/test/java/com/eshop/api/chatgateway/util/ChatPayloadRedactorTest.java`

- [ ] **Step 1: Write failing redactor tests**

Create `backend/e-shop/src/test/java/com/eshop/api/chatgateway/util/ChatPayloadRedactorTest.java`:

```java
package com.eshop.api.chatgateway.util;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class ChatPayloadRedactorTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final ChatPayloadRedactor redactor = new ChatPayloadRedactor(objectMapper);

    @Test
    void redactsSensitiveKeysAndNestedValues() {
        var node = objectMapper.valueToTree(Map.of(
            "Authorization", "Bearer abc.def.ghi",
            "message", "email me at customer@example.com or call 0901234567",
            "nested", Map.of(
                "cardNumber", "4111111111111111",
                "traceId", "trace-123"
            )
        ));

        var redacted = redactor.redact(node);

        assertThat(redacted.get("Authorization").asText()).isEqualTo("[REDACTED]");
        assertThat(redacted.get("message").asText()).doesNotContain("customer@example.com", "0901234567");
        assertThat(redacted.get("nested").get("cardNumber").asText()).isEqualTo("[REDACTED]");
        assertThat(redacted.get("nested").get("traceId").asText()).isEqualTo("trace-123");
    }

    @Test
    void redactsStringPatternsButKeepsNonSensitiveIds() {
        String redacted = redactor.redactText(
            "token=abc123 traceId=trace-1 sessionId=session-1 order ES123 card 4111 1111 1111 1111"
        );

        assertThat(redacted).contains("token=[REDACTED]");
        assertThat(redacted).contains("traceId=trace-1");
        assertThat(redacted).contains("sessionId=session-1");
        assertThat(redacted).contains("order ES123");
        assertThat(redacted).doesNotContain("4111 1111 1111 1111");
    }
}
```

- [ ] **Step 2: Run test to verify RED**

Run:

```bash
cd backend/e-shop && ./mvnw -Dtest=ChatPayloadRedactorTest test
```

Expected: compile FAIL because `ChatPayloadRedactor` does not exist.

- [ ] **Step 3: Implement redactor**

Create `backend/e-shop/src/main/java/com/eshop/api/chatgateway/util/ChatPayloadRedactor.java`:

```java
package com.eshop.api.chatgateway.util;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.fasterxml.jackson.databind.node.TextNode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.Iterator;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

@Component
@RequiredArgsConstructor
public class ChatPayloadRedactor {

    public static final String REDACTED = "[REDACTED]";

    private static final Set<String> SENSITIVE_KEY_PARTS = Set.of(
        "authorization", "token", "access_token", "refresh_token", "jwt", "password", "secret",
        "api_key", "apikey", "cookie", "email", "phone", "address", "payment", "card", "cvv", "cvc"
    );
    private static final Pattern BEARER = Pattern.compile("(?i)Bearer\\s+[A-Za-z0-9._\\-]+");
    private static final Pattern BASIC = Pattern.compile("(?i)Basic\\s+[A-Za-z0-9+/=]+");
    private static final Pattern JWT = Pattern.compile("\\beyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\b");
    private static final Pattern TOKEN_PARAM = Pattern.compile("(?i)\\b(access_token|api_key|apikey|auth|client_secret|id_token|jwt|refresh_token|secret|token)=([^&\\s]+)");
    private static final Pattern EMAIL = Pattern.compile("[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}");
    private static final Pattern VIETNAM_PHONE = Pattern.compile("\\b(?:\\+?84|0)\\d(?:[\\s.-]?\\d){7,9}\\b");
    private static final Pattern CARD_CANDIDATE = Pattern.compile("\\b(?:\\d[ -]?){13,19}\\b");

    private final ObjectMapper objectMapper;

    public JsonNode redact(JsonNode node) {
        if (node == null || node.isNull()) {
            return node;
        }
        if (node.isObject()) {
            ObjectNode copy = objectMapper.createObjectNode();
            Iterator<Map.Entry<String, JsonNode>> fields = node.fields();
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> field = fields.next();
                copy.set(field.getKey(), isSensitiveKey(field.getKey()) ? TextNode.valueOf(REDACTED) : redact(field.getValue()));
            }
            return copy;
        }
        if (node.isArray()) {
            ArrayNode copy = objectMapper.createArrayNode();
            node.forEach(item -> copy.add(redact(item)));
            return copy;
        }
        if (node.isTextual()) {
            return TextNode.valueOf(redactText(node.asText()));
        }
        return node;
    }

    public String redactText(String value) {
        if (value == null || value.isBlank()) {
            return value;
        }
        String redacted = BEARER.matcher(value).replaceAll("Bearer " + REDACTED);
        redacted = BASIC.matcher(redacted).replaceAll("Basic " + REDACTED);
        redacted = JWT.matcher(redacted).replaceAll(REDACTED);
        redacted = TOKEN_PARAM.matcher(redacted).replaceAll("$1=" + REDACTED);
        redacted = EMAIL.matcher(redacted).replaceAll(REDACTED);
        redacted = VIETNAM_PHONE.matcher(redacted).replaceAll(REDACTED);
        return redactCardNumbers(redacted);
    }

    private boolean isSensitiveKey(String key) {
        String normalized = key.toLowerCase(Locale.ROOT).replace("-", "_");
        return SENSITIVE_KEY_PARTS.stream().anyMatch(normalized::contains);
    }

    private String redactCardNumbers(String value) {
        var matcher = CARD_CANDIDATE.matcher(value);
        StringBuffer buffer = new StringBuffer();
        while (matcher.find()) {
            String candidate = matcher.group();
            String digits = candidate.replaceAll("\\D", "");
            matcher.appendReplacement(buffer, passesLuhn(digits) ? REDACTED : candidate);
        }
        matcher.appendTail(buffer);
        return buffer.toString();
    }

    private boolean passesLuhn(String digits) {
        if (digits.length() < 13 || digits.length() > 19) {
            return false;
        }
        int sum = 0;
        boolean doubleDigit = false;
        for (int index = digits.length() - 1; index >= 0; index--) {
            int value = Character.digit(digits.charAt(index), 10);
            if (doubleDigit) {
                value *= 2;
                if (value > 9) {
                    value -= 9;
                }
            }
            sum += value;
            doubleDigit = !doubleDigit;
        }
        return sum % 10 == 0;
    }
}
```

- [ ] **Step 4: Run redactor tests to verify GREEN**

Run:

```bash
cd backend/e-shop && ./mvnw -Dtest=ChatPayloadRedactorTest test
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/e-shop/src/main/java/com/eshop/api/chatgateway/util/ChatPayloadRedactor.java backend/e-shop/src/test/java/com/eshop/api/chatgateway/util/ChatPayloadRedactorTest.java
git commit -m "Add chat payload redaction"
```

## Task 5: Apply Redaction At Chat Gateway Persistence Boundaries

**Files:**
- Modify: `backend/e-shop/src/main/java/com/eshop/api/chatgateway/service/ChatGatewayService.java`
- Modify/Create: `backend/e-shop/src/test/java/com/eshop/api/chatgateway/service/ChatGatewayServiceTest.java`

- [ ] **Step 1: Write failing service persistence redaction test**

Create `backend/e-shop/src/test/java/com/eshop/api/chatgateway/service/ChatGatewayServiceTest.java` with a Mockito test class. Include constructor setup for all `ChatGatewayService` dependencies and this test:

```java
@Test
void sendMessagePersistsRedactedPayloadsAndTraceArtifacts() {
    User user = new User();
    user.setId(UUID.randomUUID());
    user.setEmail("customer@example.com");
    ChatSession session = ChatSession.builder().id(UUID.randomUUID()).user(user).status(ChatSessionStatus.OPEN).build();

    when(userRepository.findByEmailIgnoreCase("customer@example.com")).thenReturn(Optional.of(user));
    when(chatSessionRepository.save(any(ChatSession.class))).thenAnswer(invocation -> {
        ChatSession saved = invocation.getArgument(0);
        if (saved.getId() == null) {
            saved.setId(session.getId());
        }
        return saved;
    });
    when(chatMessageRepository.save(any(ChatMessage.class))).thenAnswer(invocation -> invocation.getArgument(0));
    when(chatAgentClient.chat(any(), eq("Bearer raw-token"), eq("trace-1"), eq("request-1"), eq("00-abc"), any()))
        .thenReturn(new AgentChatResponse(
            session.getId().toString(),
            "trace-1",
            "policy_or_faq",
            "answer",
            "Email customer@example.com and phone 0901234567",
            List.of(),
            null,
            false,
            List.of(new AgentToolCallTrace(
                "knowledge.retrieve",
                "success",
                12.0,
                "trace-1",
                Map.of("email", "customer@example.com"),
                "Authorization Bearer raw-token",
                "phone 0901234567",
                "phone 0901234567",
                null,
                null,
                null
            )),
            List.of(),
            Map.of(),
            0.8,
            0.8,
            false,
            22.0,
            0
        ));

    service.sendMessage(
        new ChatMessageRequest(null, "my email is customer@example.com", Map.of("phone", "0901234567")),
        () -> "customer@example.com",
        "Bearer raw-token",
        "trace-1",
        "request-1",
        "00-abc"
    );

    ArgumentCaptor<ChatMessage> messageCaptor = ArgumentCaptor.forClass(ChatMessage.class);
    verify(chatMessageRepository, atLeast(2)).save(messageCaptor.capture());
    assertThat(messageCaptor.getAllValues())
        .allSatisfy(message -> assertThat(message.getPayloadJson().toString()).doesNotContain("customer@example.com", "0901234567", "raw-token"));

    ArgumentCaptor<ChatToolCall> toolCaptor = ArgumentCaptor.forClass(ChatToolCall.class);
    verify(chatToolCallRepository).save(toolCaptor.capture());
    ChatToolCall toolCall = toolCaptor.getValue();
    assertThat(toolCall.getInputJson().toString()).doesNotContain("customer@example.com");
    assertThat(toolCall.getRequestSummary()).doesNotContain("raw-token");
    assertThat(toolCall.getResponseSummary()).doesNotContain("0901234567");
}
```

Use the actual constructor signature from `AgentToolCallTrace` in `backend/e-shop/src/main/java/com/eshop/api/chatagent/dto/AgentToolCallTrace.java`. If the record field order differs, adapt only the constructor arguments, not the assertions.

- [ ] **Step 2: Run service redaction test to verify RED**

Run:

```bash
cd backend/e-shop && ./mvnw -Dtest=ChatGatewayServiceTest#sendMessagePersistsRedactedPayloadsAndTraceArtifacts test
```

Expected: FAIL because `ChatGatewayService` persists raw payload JSON and summaries.

- [ ] **Step 3: Inject and use `ChatPayloadRedactor`**

In `ChatGatewayService`, add import:

```java
import com.eshop.api.chatgateway.util.ChatPayloadRedactor;
```

Add field to the required-args constructor:

```java
    private final ChatPayloadRedactor chatPayloadRedactor;
```

Add helper methods near the bottom:

```java
    private JsonNode redactedJson(Object value) {
        return chatPayloadRedactor.redact(objectMapper.valueToTree(value));
    }

    private JsonNode redactedJson(JsonNode value) {
        return chatPayloadRedactor.redact(value);
    }

    private String redactedText(String value) {
        return chatPayloadRedactor.redactText(value);
    }
```

Replace persistence calls:

```java
payloadJson(objectMapper.valueToTree(request))
payloadJson(objectMapper.valueToTree(response))
inputJson(toolCall.input() != null ? objectMapper.valueToTree(toolCall.input()) : null)
requestSummary(toolCall.requestSummary())
responseSummary(firstText(toolCall.responseSummary(), toolCall.outputSummary()))
errorMessage(firstText(toolCall.errorMessage(), toolCall.error()))
inputSummary(nodeTrace.inputSummary())
outputSummary(nodeTrace.outputSummary())
errorMessage(nodeTrace.errorMessage())
payloadJson(payload)
resultJson(objectMapper.valueToTree(result))
resultJson(objectMapper.valueToTree(Map.of("error", safeMessage(ex))))
payloadJson(objectMapper.valueToTree(result))
```

with the corresponding `redactedJson(...)` or `redactedText(...)` calls.

- [ ] **Step 4: Run service redaction test to verify GREEN**

Run:

```bash
cd backend/e-shop && ./mvnw -Dtest=ChatGatewayServiceTest#sendMessagePersistsRedactedPayloadsAndTraceArtifacts test
```

Expected: PASS.

- [ ] **Step 5: Run chatgateway/redactor tests**

Run:

```bash
cd backend/e-shop && ./mvnw -Dtest=ChatPayloadRedactorTest,ChatGatewayServiceTest test
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/e-shop/src/main/java/com/eshop/api/chatgateway/service/ChatGatewayService.java backend/e-shop/src/test/java/com/eshop/api/chatgateway/service/ChatGatewayServiceTest.java
git commit -m "Redact chat gateway persisted payloads"
```

## Task 6: Chat Gateway Draft And Fallback Service Hardening Tests

**Files:**
- Modify: `backend/e-shop/src/test/java/com/eshop/api/chatgateway/service/ChatGatewayServiceTest.java`
- Modify: `backend/e-shop/src/main/java/com/eshop/api/chatgateway/service/ChatGatewayService.java` only if tests reveal a behavior gap.

- [ ] **Step 1: Add fallback persistence test**

Add to `ChatGatewayServiceTest`:

```java
@Test
void sendMessagePersistsFallbackWhenAgentUnavailable() {
    User user = user("customer@example.com");
    when(userRepository.findByEmailIgnoreCase(user.getEmail())).thenReturn(Optional.of(user));
    when(chatSessionRepository.save(any(ChatSession.class))).thenAnswer(invocation -> {
        ChatSession saved = invocation.getArgument(0);
        if (saved.getId() == null) {
            saved.setId(UUID.randomUUID());
        }
        return saved;
    });
    when(chatMessageRepository.save(any(ChatMessage.class))).thenAnswer(invocation -> invocation.getArgument(0));
    when(chatAgentClient.chat(any(), any(), any(), any(), any(), any()))
        .thenThrow(new ChatAgentUnavailableException("down"));

    AgentChatResponse response = service.sendMessage(
        new ChatMessageRequest(null, "hello", Map.of()),
        () -> user.getEmail(),
        null,
        "trace-fallback",
        "request-fallback",
        null
    );

    assertThat(response.responseType()).isEqualTo("tool_error");
    assertThat(response.fallbackCount()).isEqualTo(1);
    verify(chatMessageRepository, atLeast(2)).save(any(ChatMessage.class));
}
```

Define helper `private User user(String email)` in the test:

```java
private User user(String email) {
    User user = new User();
    user.setId(UUID.randomUUID());
    user.setEmail(email);
    return user;
}
```

- [ ] **Step 2: Add expired draft test**

Add:

```java
@Test
void confirmActionMarksExpiredDraftExpired() {
    User user = user("customer@example.com");
    ChatDraftAction draft = ChatDraftAction.builder()
        .id(UUID.randomUUID())
        .user(user)
        .status(ChatDraftActionStatus.PENDING)
        .actionType("cart.add")
        .payloadJson(objectMapper.createObjectNode())
        .expiresAt(Instant.now().minusSeconds(10))
        .build();

    when(userRepository.findByEmailIgnoreCase(user.getEmail())).thenReturn(Optional.of(user));
    when(chatDraftActionRepository.findByIdAndUser_Id(draft.getId(), user.getId())).thenReturn(Optional.of(draft));

    assertThatThrownBy(() -> service.confirmAction(draft.getId(), () -> user.getEmail()))
        .hasMessageContaining("expired");
    assertThat(draft.getStatus()).isEqualTo(ChatDraftActionStatus.EXPIRED);
    verify(chatDraftActionRepository).save(draft);
}
```

- [ ] **Step 3: Add unsupported draft action test**

Add:

```java
@Test
void confirmActionFailsUnsupportedDraftWithoutCallingDomainServices() {
    User user = user("customer@example.com");
    ChatDraftAction draft = ChatDraftAction.builder()
        .id(UUID.randomUUID())
        .user(user)
        .session(ChatSession.builder().id(UUID.randomUUID()).user(user).build())
        .status(ChatDraftActionStatus.PENDING)
        .actionType("payment.capture")
        .payloadJson(objectMapper.createObjectNode())
        .expiresAt(Instant.now().plusSeconds(60))
        .build();

    when(userRepository.findByEmailIgnoreCase(user.getEmail())).thenReturn(Optional.of(user));
    when(chatDraftActionRepository.findByIdAndUser_Id(draft.getId(), user.getId())).thenReturn(Optional.of(draft));

    assertThatThrownBy(() -> service.confirmAction(draft.getId(), () -> user.getEmail()))
        .hasMessageContaining("Unsupported draft action type");
    assertThat(draft.getStatus()).isEqualTo(ChatDraftActionStatus.FAILED);
    verifyNoInteractions(cartService, supportMessagingService);
}
```

- [ ] **Step 4: Add cancel non-pending test**

Add:

```java
@Test
void cancelActionRejectsNonPendingDraft() {
    User user = user("customer@example.com");
    ChatDraftAction draft = ChatDraftAction.builder()
        .id(UUID.randomUUID())
        .user(user)
        .status(ChatDraftActionStatus.COMPLETED)
        .actionType("cart.add")
        .payloadJson(objectMapper.createObjectNode())
        .expiresAt(Instant.now().plusSeconds(60))
        .build();

    when(userRepository.findByEmailIgnoreCase(user.getEmail())).thenReturn(Optional.of(user));
    when(chatDraftActionRepository.findByIdAndUser_Id(draft.getId(), user.getId())).thenReturn(Optional.of(draft));

    assertThatThrownBy(() -> service.cancelAction(draft.getId(), () -> user.getEmail()))
        .hasMessageContaining("not pending");
}
```

- [ ] **Step 5: Run tests to verify RED/GREEN status**

Run:

```bash
cd backend/e-shop && ./mvnw -Dtest=ChatGatewayServiceTest test
```

Expected: PASS if current behavior already satisfies the tests after Task 5 setup. If any fail due to missing persistence defaults or constructor setup, fix the test setup first. If a real service behavior fails, make the minimal `ChatGatewayService` change needed and rerun.

- [ ] **Step 6: Commit**

```bash
git add backend/e-shop/src/test/java/com/eshop/api/chatgateway/service/ChatGatewayServiceTest.java backend/e-shop/src/main/java/com/eshop/api/chatgateway/service/ChatGatewayService.java
git commit -m "Harden chat gateway service behavior"
```

## Task 7: Minimal Chat Review Queue API

**Files:**
- Create: `backend/e-shop/src/main/java/com/eshop/api/chatgateway/dto/ChatReviewMessageResponse.java`
- Modify: `backend/e-shop/src/main/java/com/eshop/api/chatgateway/repository/ChatMessageRepository.java`
- Modify: `backend/e-shop/src/main/java/com/eshop/api/chatgateway/repository/ChatToolCallRepository.java`
- Modify: `backend/e-shop/src/main/java/com/eshop/api/chatgateway/service/ChatGatewayService.java`
- Modify: `backend/e-shop/src/main/java/com/eshop/api/chatgateway/controller/ChatGatewayController.java`
- Modify: `backend/e-shop/src/test/java/com/eshop/api/chatgateway/controller/ChatGatewayControllerTest.java`

- [ ] **Step 1: Write failing controller test**

Append to `ChatGatewayControllerTest`:

```java
@Test
void shouldReturnReviewMessages() throws Exception {
    UUID messageId = UUID.randomUUID();
    UUID sessionId = UUID.randomUUID();
    UUID userId = UUID.randomUUID();
    when(chatGatewayService.getReviewMessages(eq(0), eq(25), any(Principal.class)))
        .thenReturn(new org.springframework.data.domain.PageImpl<>(List.of(
            new ChatReviewMessageResponse(
                messageId,
                sessionId,
                userId,
                "Needs review",
                "recommendation",
                "fallback",
                "trace-review",
                1,
                java.time.Instant.parse("2026-06-22T00:00:00Z"),
                List.of("fallback_count", "response_type")
            )
        )));

    mockMvc.perform(get("/api/chat/review/messages")
            .principal(() -> "admin@example.com")
            .param("page", "0")
            .param("size", "25"))
        .andExpect(status().isOk())
        .andExpect(jsonPath("$.content[0].messageId").value(messageId.toString()))
        .andExpect(jsonPath("$.content[0].sessionId").value(sessionId.toString()))
        .andExpect(jsonPath("$.content[0].reviewReasons[0]").value("fallback_count"));
}
```

Add import:

```java
import com.eshop.api.chatgateway.dto.ChatReviewMessageResponse;
```

- [ ] **Step 2: Run controller test to verify RED**

Run:

```bash
cd backend/e-shop && ./mvnw -Dtest=ChatGatewayControllerTest#shouldReturnReviewMessages test
```

Expected: compile FAIL because DTO/service/controller method do not exist.

- [ ] **Step 3: Create DTO**

Create `backend/e-shop/src/main/java/com/eshop/api/chatgateway/dto/ChatReviewMessageResponse.java`:

```java
package com.eshop.api.chatgateway.dto;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record ChatReviewMessageResponse(
    UUID messageId,
    UUID sessionId,
    UUID userId,
    String body,
    String intent,
    String responseType,
    String traceId,
    Integer fallbackCount,
    Instant createdAt,
    List<String> reviewReasons
) {
}
```

- [ ] **Step 4: Add repository methods**

In `ChatMessageRepository`, add:

```java
import com.eshop.api.chatgateway.enums.ChatMessageRole;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

Page<ChatMessage> findByRoleAndFallbackCountGreaterThanOrderByCreatedAtDesc(
    ChatMessageRole role,
    Integer fallbackCount,
    Pageable pageable
);

@Query("""
    select message
    from ChatMessage message
    where message.role = com.eshop.api.chatgateway.enums.ChatMessageRole.ASSISTANT
      and (
        message.fallbackCount > 0
        or message.responseType in ('tool_error', 'fallback')
      )
    order by message.createdAt desc
    """)
Page<ChatMessage> findReviewCandidates(Pageable pageable);
```

In `ChatToolCallRepository`, add:

```java
import java.util.Collection;
import java.util.List;

List<ChatToolCall> findByMessage_IdAndStatusIn(UUID messageId, Collection<String> statuses);
```

- [ ] **Step 5: Add service method**

In `ChatGatewayService`, add:

```java
@Transactional(readOnly = true)
public Page<ChatReviewMessageResponse> getReviewMessages(int page, int size, Principal principal) {
    requireUser(principal);
    int resolvedPage = Math.max(page, 0);
    int resolvedSize = Math.max(1, Math.min(size, 100));
    return chatMessageRepository.findReviewCandidates(PageRequest.of(resolvedPage, resolvedSize))
        .map(this::toReviewMessage);
}

private ChatReviewMessageResponse toReviewMessage(ChatMessage message) {
    List<String> reasons = reviewReasons(message);
    UUID userId = message.getUser() != null ? message.getUser().getId() : null;
    return new ChatReviewMessageResponse(
        message.getId(),
        message.getSession().getId(),
        userId,
        message.getBody(),
        message.getIntent(),
        message.getResponseType(),
        message.getTraceId(),
        message.getFallbackCount(),
        message.getCreatedAt(),
        reasons
    );
}

private List<String> reviewReasons(ChatMessage message) {
    List<String> reasons = new java.util.ArrayList<>();
    if (message.getFallbackCount() != null && message.getFallbackCount() > 0) {
        reasons.add("fallback_count");
    }
    if ("tool_error".equals(message.getResponseType()) || "fallback".equals(message.getResponseType())) {
        reasons.add("response_type");
    }
    List<ChatToolCall> failedTools = chatToolCallRepository.findByMessage_IdAndStatusIn(
        message.getId(),
        List.of("timeout", "backend_error", "validation_error")
    );
    if (!failedTools.isEmpty()) {
        reasons.add("tool_status");
    }
    return List.copyOf(reasons);
}
```

Add imports:

```java
import com.eshop.api.chatgateway.dto.ChatReviewMessageResponse;
import org.springframework.data.domain.Page;
```

- [ ] **Step 6: Add controller route**

In `ChatGatewayController`, add:

```java
import com.eshop.api.chatgateway.dto.ChatReviewMessageResponse;
import org.springframework.data.domain.Page;
```

Add method:

```java
@GetMapping("/review/messages")
public ResponseEntity<Page<ChatReviewMessageResponse>> getReviewMessages(
    @RequestParam(defaultValue = "0") int page,
    @RequestParam(defaultValue = "50") int size,
    Principal principal
) {
    return ResponseEntity.ok(chatGatewayService.getReviewMessages(page, size, principal));
}
```

- [ ] **Step 7: Run controller test to verify GREEN**

Run:

```bash
cd backend/e-shop && ./mvnw -Dtest=ChatGatewayControllerTest#shouldReturnReviewMessages test
```

Expected: PASS.

- [ ] **Step 8: Add service unit test for reasons**

Add to `ChatGatewayServiceTest`:

```java
@Test
void getReviewMessagesReturnsReasonsForFallbackAndToolFailures() {
    User user = user("admin@example.com");
    ChatMessage message = ChatMessage.builder()
        .id(UUID.randomUUID())
        .session(ChatSession.builder().id(UUID.randomUUID()).user(user).build())
        .user(user)
        .role(ChatMessageRole.ASSISTANT)
        .body("fallback")
        .intent("recommendation")
        .responseType("fallback")
        .traceId("trace-review")
        .fallbackCount(1)
        .createdAt(Instant.parse("2026-06-22T00:00:00Z"))
        .build();

    when(userRepository.findByEmailIgnoreCase(user.getEmail())).thenReturn(Optional.of(user));
    when(chatMessageRepository.findReviewCandidates(any(PageRequest.class)))
        .thenReturn(new PageImpl<>(List.of(message)));
    when(chatToolCallRepository.findByMessage_IdAndStatusIn(eq(message.getId()), any()))
        .thenReturn(List.of(ChatToolCall.builder().status("timeout").build()));

    Page<ChatReviewMessageResponse> result = service.getReviewMessages(0, 50, () -> user.getEmail());

    ChatReviewMessageResponse row = result.getContent().get(0);
    assertThat(row.reviewReasons()).containsExactly("fallback_count", "response_type", "tool_status");
}
```

- [ ] **Step 9: Run review queue tests**

Run:

```bash
cd backend/e-shop && ./mvnw -Dtest=ChatGatewayControllerTest,ChatGatewayServiceTest test
```

Expected: PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/e-shop/src/main/java/com/eshop/api/chatgateway/dto/ChatReviewMessageResponse.java backend/e-shop/src/main/java/com/eshop/api/chatgateway/repository/ChatMessageRepository.java backend/e-shop/src/main/java/com/eshop/api/chatgateway/repository/ChatToolCallRepository.java backend/e-shop/src/main/java/com/eshop/api/chatgateway/service/ChatGatewayService.java backend/e-shop/src/main/java/com/eshop/api/chatgateway/controller/ChatGatewayController.java backend/e-shop/src/test/java/com/eshop/api/chatgateway/controller/ChatGatewayControllerTest.java backend/e-shop/src/test/java/com/eshop/api/chatgateway/service/ChatGatewayServiceTest.java
git commit -m "Add chat review queue API"
```

## Task 8: Pipeline Docs And Final Verification

**Files:**
- Modify: `docs/chatbot-full-pipeline.md`
- Optionally modify: `chat-agent/README.md` if the personalized Spring adapter should be documented there.

- [ ] **Step 1: Update pipeline docs**

In `docs/chatbot-full-pipeline.md`, under `### Phase 5: RAG And Recommendations`, add:

```markdown
Status: complete for repo-owned local scope. Local RAG, local hybrid indexing, knowledge source metadata, recommendation ranking metadata, personalized recommendation routing, Spring personalized recommendation adapter coverage, and fallback behavior are implemented and covered by tests. Production vector DB, persisted embedding ingestion, and real ML recommender training remain external production dependencies.
```

Under `### Phase 6: Backend Integration And Production Hardening`, add:

```markdown
Status: started with minimal backend hardening. The Spring chat gateway persists chat sessions/messages/tool traces/draft actions, redacts sensitive payloads before persistence, supports draft confirmation/cancel flows, and exposes a read-only review queue API for fallback/tool-error messages. Full production completion still requires load tests, operational dashboard wiring, and production infrastructure validation.
```

- [ ] **Step 2: Run Python full tests**

Run:

```bash
cd chat-agent && .venv/bin/python -m pytest tests -q
```

Expected: PASS. Record the exact pass count and warnings in the final implementation summary.

- [ ] **Step 3: Run backend targeted tests**

Run:

```bash
cd backend/e-shop && ./mvnw -Dtest=ChatPayloadRedactorTest,ChatGatewayControllerTest,ChatGatewayServiceTest test
```

Expected: PASS.

- [ ] **Step 4: Run backend full test suite**

Run:

```bash
cd backend/e-shop && ./mvnw test
```

Expected: PASS. If it fails due to unrelated environment or pre-existing failures, capture the failing test names and error summary.

- [ ] **Step 5: Check git status**

Run:

```bash
git status --short --branch
```

Expected: only ignored/local `.codegraph` directories remain untracked, or a clean working tree if those are ignored before final handoff.

- [ ] **Step 6: Commit docs and final verification updates**

```bash
git add docs/chatbot-full-pipeline.md
git commit -m "Document chatbot phase hardening status"
```

Use `git add -f docs/chatbot-full-pipeline.md` if docs are ignored.

## Final Verification Checklist

- [ ] Python tests passed with exact command: `cd chat-agent && .venv/bin/python -m pytest tests -q`.
- [ ] Backend targeted tests passed with exact command: `cd backend/e-shop && ./mvnw -Dtest=ChatPayloadRedactorTest,ChatGatewayControllerTest,ChatGatewayServiceTest test`.
- [ ] Backend full tests either passed with `cd backend/e-shop && ./mvnw test` or failures are documented with exact failing tests.
- [ ] `docs/chat-agent-phase5-progress.md` says Phase 5 local scope is complete and external dependencies are explicit.
- [ ] `docs/chatbot-full-pipeline.md` says Phase 6 minimal hardening has started, not full production completed.
- [ ] Sensitive values are redacted in persisted chat payloads and traces.
- [ ] `origin/main` is pushed only after all intended commits are created and verified.
