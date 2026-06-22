package com.eshop.api.chatgateway.service;

import com.eshop.api.cart.dto.AddCartItemRequest;
import com.eshop.api.cart.dto.CartResponse;
import com.eshop.api.cart.dto.UpdateCartItemRequest;
import com.eshop.api.cart.repository.CartItemRepository;
import com.eshop.api.cart.repository.CartRepository;
import com.eshop.api.cart.service.CartService;
import com.eshop.api.catalog.model.ProductVariant;
import com.eshop.api.catalog.repository.ProductVariantRepository;
import com.eshop.api.chatagent.client.ChatAgentClient;
import com.eshop.api.chatagent.dto.AgentChatRequest;
import com.eshop.api.chatagent.dto.AgentChatResponse;
import com.eshop.api.chatagent.dto.AgentDraftAction;
import com.eshop.api.chatagent.dto.AgentNodeTrace;
import com.eshop.api.chatagent.dto.AgentProductCard;
import com.eshop.api.chatagent.dto.AgentToolCallTrace;
import com.eshop.api.chatgateway.dto.ChatActionResultResponse;
import com.eshop.api.chatgateway.dto.ChatContextResponse;
import com.eshop.api.chatgateway.dto.ChatHistoryMessageResponse;
import com.eshop.api.chatgateway.dto.ChatHistoryResponse;
import com.eshop.api.chatgateway.dto.ChatMessageRequest;
import com.eshop.api.chatgateway.enums.ChatDraftActionStatus;
import com.eshop.api.chatgateway.enums.ChatMessageRole;
import com.eshop.api.chatgateway.enums.ChatSessionStatus;
import com.eshop.api.chatgateway.model.ChatDraftAction;
import com.eshop.api.chatgateway.model.ChatMessage;
import com.eshop.api.chatgateway.model.ChatNodeTrace;
import com.eshop.api.chatgateway.model.ChatSession;
import com.eshop.api.chatgateway.model.ChatToolCall;
import com.eshop.api.chatgateway.repository.ChatDraftActionRepository;
import com.eshop.api.chatgateway.repository.ChatMessageRepository;
import com.eshop.api.chatgateway.repository.ChatNodeTraceRepository;
import com.eshop.api.chatgateway.repository.ChatSessionRepository;
import com.eshop.api.chatgateway.repository.ChatToolCallRepository;
import com.eshop.api.chatgateway.util.ChatPayloadRedactor;
import com.eshop.api.exception.ApiException;
import com.eshop.api.exception.ChatAgentUnavailableException;
import com.eshop.api.exception.InvalidJwtException;
import com.eshop.api.exception.ProductVariantNotFoundException;
import com.eshop.api.order.repository.OrderRepository;
import com.eshop.api.support.dto.CreateSupportConversationRequest;
import com.eshop.api.support.dto.SupportConversationSummaryResponse;
import com.eshop.api.support.service.SupportMessagingService;
import com.eshop.api.user.User;
import com.eshop.api.user.UserRepository;
import com.fasterxml.jackson.core.JsonProcessingException;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.JsonNodeFactory;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.data.domain.PageRequest;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.util.StringUtils;

import java.math.BigDecimal;
import java.security.Principal;
import java.time.Instant;
import java.time.temporal.ChronoUnit;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

@Slf4j
@Service
@RequiredArgsConstructor
public class ChatGatewayService {

    private static final int DEFAULT_DRAFT_EXPIRY_MINUTES = 15;
    private static final TypeReference<Map<String, Object>> MAP_TYPE = new TypeReference<>() {
    };

    private final ChatSessionRepository chatSessionRepository;
    private final ChatMessageRepository chatMessageRepository;
    private final ChatToolCallRepository chatToolCallRepository;
    private final ChatNodeTraceRepository chatNodeTraceRepository;
    private final ChatDraftActionRepository chatDraftActionRepository;
    private final ChatAgentClient chatAgentClient;
    private final UserRepository userRepository;
    private final CartService cartService;
    private final CartRepository cartRepository;
    private final CartItemRepository cartItemRepository;
    private final ProductVariantRepository productVariantRepository;
    private final SupportMessagingService supportMessagingService;
    private final OrderRepository orderRepository;
    private final ChatPayloadRedactor chatPayloadRedactor;
    private final ObjectMapper objectMapper;

    @Transactional
    public AgentChatResponse sendMessage(
        ChatMessageRequest request,
        Principal principal,
        String authorization,
        String traceIdHeader,
        String requestIdHeader,
        String traceparent
    ) {
        User user = resolveOptionalUser(principal);
        ChatSession session = loadOrCreateSession(request.sessionId(), user);
        Instant now = Instant.now();
        session.setLastMessageAt(now);
        chatSessionRepository.save(session);

        String traceId = firstText(traceIdHeader, UUID.randomUUID().toString());
        String requestId = firstText(requestIdHeader, UUID.randomUUID().toString());
        Map<String, Object> clientContext = request.clientContext() != null ? request.clientContext() : Map.of();

        ChatMessage userMessage = chatMessageRepository.save(ChatMessage.builder()
            .session(session)
            .user(user)
            .role(ChatMessageRole.USER)
            .body(request.message())
            .traceId(traceId)
            .payloadJson(redactedJson(request))
            .build());

        AgentChatResponse response;
        try {
            response = chatAgentClient.chat(
                new AgentChatRequest(
                    request.message(),
                    session.getId().toString(),
                    traceId,
                    requestId,
                    traceparent,
                    user != null ? user.getId().toString() : null,
                    user != null,
                    clientContext
                ),
                authorization,
                traceId,
                requestId,
                traceparent,
                session.getId().toString()
            );
        } catch (ChatAgentUnavailableException ex) {
            log.warn("Chat agent unavailable for traceId={} sessionId={}: {}", traceId, session.getId(), ex.getMessage());
            response = fallbackResponse(session.getId().toString(), traceId);
        }

        response = ensureResponseIds(response, session.getId().toString(), traceId);
        ChatMessage assistantMessage = persistAssistantResponse(session, user, response);
        persistToolCalls(session, assistantMessage, response);
        persistNodeTraces(session, assistantMessage, response);
        persistDraftAction(session, user, assistantMessage, response.draftAction());

        return response;
    }

    @Transactional
    public ChatActionResultResponse confirmAction(UUID draftActionId, Principal principal) {
        User user = requireUser(principal);
        ChatDraftAction draft = loadOwnedDraft(draftActionId, user);
        ensurePendingAndFresh(draft);

        Instant now = Instant.now();
        draft.setConfirmedAt(now);
        try {
            Map<String, Object> result = executeDraftAction(user, draft);
            draft.setStatus(ChatDraftActionStatus.COMPLETED);
            draft.setCompletedAt(now);
            draft.setResultJson(redactedJson(result));
            chatDraftActionRepository.save(draft);
            persistActionEvent(draft, "Completed " + draft.getActionType(), result);
            return new ChatActionResultResponse(draft.getId(), "completed", draft.getActionType(), result);
        } catch (RuntimeException ex) {
            draft.setStatus(ChatDraftActionStatus.FAILED);
            draft.setErrorMessage(redactedText(ex.getMessage()));
            draft.setResultJson(redactedJson(Map.of("error", safeMessage(ex))));
            chatDraftActionRepository.save(draft);
            throw ex;
        }
    }

    @Transactional
    public ChatActionResultResponse cancelAction(UUID draftActionId, Principal principal) {
        User user = requireUser(principal);
        ChatDraftAction draft = loadOwnedDraft(draftActionId, user);
        if (draft.getStatus() != ChatDraftActionStatus.PENDING) {
            throw new ApiException("Draft action is not pending", 409);
        }
        draft.setStatus(ChatDraftActionStatus.CANCELLED);
        draft.setCancelledAt(Instant.now());
        chatDraftActionRepository.save(draft);
        persistActionEvent(draft, "Cancelled " + draft.getActionType(), Map.of());
        return new ChatActionResultResponse(draft.getId(), "cancelled", draft.getActionType(), Map.of());
    }

    @Transactional(readOnly = true)
    public ChatHistoryResponse getHistory(UUID sessionId, int page, int size, Principal principal) {
        User user = requireUser(principal);
        chatSessionRepository.findByIdAndUser_Id(sessionId, user.getId())
            .orElseThrow(() -> new ApiException("Chat session not found", 404));

        var resolvedPage = Math.max(page, 0);
        var resolvedSize = Math.max(1, Math.min(size, 100));
        var messages = chatMessageRepository.findBySession_IdOrderByCreatedAtAsc(
            sessionId,
            PageRequest.of(resolvedPage, resolvedSize)
        );
        return new ChatHistoryResponse(
            sessionId,
            messages.stream().map(this::toHistoryMessage).toList(),
            messages.getNumber(),
            messages.getSize(),
            messages.hasNext()
        );
    }

    @Transactional(readOnly = true)
    public ChatContextResponse getContext(Principal principal, String locale) {
        User user = requireUser(principal);
        var cart = cartRepository.findByUser_Id(user.getId()).orElse(null);
        var cartSummary = cart == null
            ? new ChatContextResponse.CartSummary(0, BigDecimal.ZERO, "VND")
            : new ChatContextResponse.CartSummary(
                cart.getItems() != null ? cart.getItems().size() : 0,
                cart.getItems() == null ? BigDecimal.ZERO : cart.getItems().stream()
                    .map(item -> {
                        BigDecimal price = item.getVariant() != null && item.getVariant().getPrice() != null
                            ? item.getVariant().getPrice()
                            : BigDecimal.ZERO;
                        int quantity = item.getQuantity() != null ? item.getQuantity() : 0;
                        return price.multiply(BigDecimal.valueOf(quantity));
                    })
                    .reduce(BigDecimal.ZERO, BigDecimal::add),
                "VND"
            );

        var recentOrders = orderRepository.findByUser_IdOrderByPlacedAtDesc(user.getId(), PageRequest.of(0, 3))
            .stream()
            .map(order -> new ChatContextResponse.RecentOrderSummary(
                order.getId(),
                order.getOrderNumber(),
                order.getStatus() != null ? order.getStatus().name() : null
            ))
            .toList();

        return new ChatContextResponse(
            new ChatContextResponse.UserSummary(user.getId(), null),
            cartSummary,
            recentOrders,
            List.of(),
            StringUtils.hasText(locale) ? locale : "vi-VN",
            Instant.now()
        );
    }

    private ChatSession loadOrCreateSession(UUID requestedSessionId, User user) {
        if (requestedSessionId == null) {
            return chatSessionRepository.save(ChatSession.builder()
                .user(user)
                .status(ChatSessionStatus.OPEN)
                .lastMessageAt(Instant.now())
                .build());
        }
        if (user != null) {
            return chatSessionRepository.findByIdAndUser_Id(requestedSessionId, user.getId())
                .orElseThrow(() -> new ApiException("Chat session not found", 404));
        }
        return chatSessionRepository.findById(requestedSessionId)
            .orElseThrow(() -> new ApiException("Chat session not found", 404));
    }

    private AgentChatResponse fallbackResponse(String sessionId, String traceId) {
        return new AgentChatResponse(
            sessionId,
            traceId,
            "fallback",
            "tool_error",
            "Chat assistant is temporarily unavailable. Please try again later or contact support.",
            List.of(),
            null,
            false,
            List.of(),
            List.of(),
            Map.of(),
            null,
            null,
            true,
            null,
            1
        );
    }

    private AgentChatResponse ensureResponseIds(AgentChatResponse response, String sessionId, String traceId) {
        AgentDraftAction draftAction = response.draftAction();
        if (draftAction != null) {
            UUID draftId = parseUuid(draftAction.draftActionId());
            if (draftId == null) {
                draftId = UUID.randomUUID();
            }
            draftAction = new AgentDraftAction(
                draftId.toString(),
                draftAction.actionType(),
                draftAction.payload(),
                firstText(draftAction.status(), "pending"),
                draftAction.expiresAt() != null ? draftAction.expiresAt() : Instant.now().plus(DEFAULT_DRAFT_EXPIRY_MINUTES, ChronoUnit.MINUTES),
                draftAction.needsConfirmation()
            );
        }

        return new AgentChatResponse(
            firstText(response.sessionId(), sessionId),
            firstText(response.traceId(), traceId),
            response.intent(),
            response.responseType(),
            response.answer(),
            response.productCards() != null ? response.productCards() : List.of(),
            draftAction,
            response.needsConfirmation(),
            response.toolCalls() != null ? response.toolCalls() : List.of(),
            response.nodeTraces() != null ? response.nodeTraces() : List.of(),
            response.slots() != null ? response.slots() : Map.of(),
            response.intentConfidence(),
            response.routingConfidence(),
            response.needsReview(),
            response.latencyMs(),
            response.fallbackCount() != null ? response.fallbackCount() : 0
        );
    }

    private ChatMessage persistAssistantResponse(ChatSession session, User user, AgentChatResponse response) {
        return chatMessageRepository.save(ChatMessage.builder()
            .session(session)
            .user(user)
            .role(ChatMessageRole.ASSISTANT)
            .body(response.answer() != null ? response.answer() : "")
            .intent(response.intent())
            .responseType(response.responseType())
            .traceId(response.traceId())
            .latencyMs(toBigDecimal(response.latencyMs()))
            .fallbackCount(response.fallbackCount() != null ? response.fallbackCount() : 0)
            .payloadJson(redactedJson(response))
            .build());
    }

    private void persistToolCalls(ChatSession session, ChatMessage message, AgentChatResponse response) {
        List<AgentToolCallTrace> toolCalls = response.toolCalls() != null ? response.toolCalls() : List.of();
        toolCalls.stream()
            .filter(toolCall -> StringUtils.hasText(toolCall.toolName()))
            .map(toolCall -> ChatToolCall.builder()
                .session(session)
                .message(message)
                .traceId(firstText(toolCall.traceId(), response.traceId()))
                .toolName(toolCall.toolName())
                .status(firstText(toolCall.status(), "unknown"))
                .latencyMs(toBigDecimal(toolCall.latencyMs()))
                .requestSummary(redactedText(toolCall.requestSummary()))
                .responseSummary(redactedText(firstText(toolCall.responseSummary(), toolCall.outputSummary())))
                .inputJson(toolCall.input() != null ? redactedJson(toolCall.input()) : null)
                .errorMessage(redactedText(firstText(toolCall.errorMessage(), toolCall.error())))
                .build())
            .forEach(chatToolCallRepository::save);
    }

    private void persistNodeTraces(ChatSession session, ChatMessage message, AgentChatResponse response) {
        List<AgentNodeTrace> nodeTraces = response.nodeTraces() != null ? response.nodeTraces() : List.of();
        nodeTraces.stream()
            .filter(nodeTrace -> StringUtils.hasText(nodeTrace.nodeName()))
            .map(nodeTrace -> ChatNodeTrace.builder()
                .session(session)
                .message(message)
                .traceId(response.traceId())
                .nodeName(nodeTrace.nodeName())
                .intent(nodeTrace.intent())
                .status(firstText(nodeTrace.status(), "unknown"))
                .latencyMs(toBigDecimal(nodeTrace.latencyMs()))
                .intentConfidence(toBigDecimal(nodeTrace.intentConfidence()))
                .routingConfidence(toBigDecimal(nodeTrace.routingConfidence()))
                .inputSummary(redactedText(nodeTrace.inputSummary()))
                .outputSummary(redactedText(nodeTrace.outputSummary()))
                .errorMessage(redactedText(nodeTrace.errorMessage()))
                .build())
            .forEach(chatNodeTraceRepository::save);
    }

    private void persistDraftAction(ChatSession session, User user, ChatMessage message, AgentDraftAction draftAction) {
        if (draftAction == null || !StringUtils.hasText(draftAction.actionType())) {
            return;
        }
        UUID id = parseUuid(draftAction.draftActionId());
        if (id == null) {
            id = UUID.randomUUID();
        }
        // This payload is executable domain input for delayed confirmation. Do not redact it
        // without adding separate storage for executable payloads and display/audit payloads.
        JsonNode payload = draftAction.payload() != null
            ? objectMapper.valueToTree(draftAction.payload())
            : JsonNodeFactory.instance.objectNode();
        chatDraftActionRepository.save(ChatDraftAction.builder()
            .id(id)
            .session(session)
            .user(user)
            .message(message)
            .actionType(draftAction.actionType())
            .status(ChatDraftActionStatus.PENDING)
            .payloadJson(payload)
            .expiresAt(draftAction.expiresAt() != null ? draftAction.expiresAt() : Instant.now().plus(DEFAULT_DRAFT_EXPIRY_MINUTES, ChronoUnit.MINUTES))
            .build());
    }

    private Map<String, Object> executeDraftAction(User user, ChatDraftAction draft) {
        return switch (draft.getActionType()) {
            case "cart.add" -> executeCartAdd(user, draft.getPayloadJson());
            case "cart.update_quantity" -> executeCartUpdate(user, draft.getPayloadJson());
            case "cart.remove_item" -> executeCartRemove(user, draft.getPayloadJson());
            case "support.handoff" -> executeSupportHandoff(user, draft.getPayloadJson());
            default -> throw new ApiException("Unsupported draft action type", 400);
        };
    }

    private Map<String, Object> executeCartAdd(User user, JsonNode payload) {
        UUID variantId = requiredUuid(payload, "variantId");
        validateProductVariant(payload, variantId);
        AddCartItemRequest request = new AddCartItemRequest();
        request.setVariantId(variantId);
        request.setQuantity(optionalInt(payload, "quantity", 1));
        return cartResult(cartService.addItem(user.getEmail(), request));
    }

    private Map<String, Object> executeCartUpdate(User user, JsonNode payload) {
        UUID itemId = optionalUuid(payload, "cartItemId");
        if (itemId == null) {
            itemId = resolveCartItemId(user, requiredUuid(payload, "variantId"));
        }
        UpdateCartItemRequest request = new UpdateCartItemRequest();
        request.setQuantity(optionalInt(payload, "quantity", 1));
        return cartResult(cartService.updateItem(user.getEmail(), itemId, request));
    }

    private Map<String, Object> executeCartRemove(User user, JsonNode payload) {
        UUID itemId = optionalUuid(payload, "cartItemId");
        if (itemId == null) {
            itemId = resolveCartItemId(user, requiredUuid(payload, "variantId"));
        }
        return cartResult(cartService.removeItem(user.getEmail(), itemId));
    }

    private Map<String, Object> executeSupportHandoff(User user, JsonNode payload) {
        String summary = text(payload, "summary");
        String message = firstText(transcriptText(payload), summary, "Customer requested support handoff.");
        SupportConversationSummaryResponse response = supportMessagingService.startConversation(
            user.getEmail(),
            new CreateSupportConversationRequest(firstText(summary, "Chat support handoff"), message, List.of())
        );
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("conversationId", response.id());
        result.put("status", response.status());
        return result;
    }

    private void validateProductVariant(JsonNode payload, UUID variantId) {
        UUID productId = optionalUuid(payload, "productId");
        if (productId == null) {
            return;
        }
        ProductVariant variant = productVariantRepository.findById(variantId)
            .orElseThrow(() -> new ProductVariantNotFoundException(variantId));
        if (variant.getProduct() == null || !productId.equals(variant.getProduct().getId())) {
            throw new ApiException("Variant does not belong to product", 400);
        }
    }

    private UUID resolveCartItemId(User user, UUID variantId) {
        var cart = cartRepository.findByUser_Id(user.getId())
            .orElseThrow(() -> new ApiException("Cart item not found", 404));
        return cartItemRepository.findByCart_IdAndVariant_Id(cart.getId(), variantId)
            .orElseThrow(() -> new ApiException("Cart item not found", 404))
            .getId();
    }

    private Map<String, Object> cartResult(CartResponse response) {
        Map<String, Object> result = new LinkedHashMap<>();
        result.put("cartId", response.getId());
        result.put("cartItemCount", response.getTotalItems() != null ? response.getTotalItems() : 0);
        result.put("totalQuantity", response.getTotalQuantity() != null ? response.getTotalQuantity() : 0);
        result.put("subtotal", response.getSubtotal() != null ? response.getSubtotal() : BigDecimal.ZERO);
        return result;
    }

    private void persistActionEvent(ChatDraftAction draft, String body, Map<String, Object> result) {
        chatMessageRepository.save(ChatMessage.builder()
            .session(draft.getSession())
            .user(draft.getUser())
            .role(ChatMessageRole.ASSISTANT)
            .body(body)
            .responseType("action_result")
            .payloadJson(redactedJson(result))
            .build());
    }

    private void ensurePendingAndFresh(ChatDraftAction draft) {
        if (draft.getStatus() != ChatDraftActionStatus.PENDING) {
            throw new ApiException("Draft action is not pending", 409);
        }
        if (draft.getExpiresAt() != null && draft.getExpiresAt().isBefore(Instant.now())) {
            draft.setStatus(ChatDraftActionStatus.EXPIRED);
            chatDraftActionRepository.save(draft);
            throw new ApiException("Draft action has expired", 410);
        }
    }

    private ChatDraftAction loadOwnedDraft(UUID draftActionId, User user) {
        return chatDraftActionRepository.findByIdAndUser_Id(draftActionId, user.getId())
            .orElseThrow(() -> new ApiException("Draft action not found", 404));
    }

    private ChatHistoryMessageResponse toHistoryMessage(ChatMessage message) {
        AgentChatResponse response = null;
        if (message.getPayloadJson() != null && message.getRole() == ChatMessageRole.ASSISTANT) {
            try {
                response = objectMapper.treeToValue(message.getPayloadJson(), AgentChatResponse.class);
            } catch (JsonProcessingException ex) {
                log.debug("Unable to deserialize assistant chat payload {}", message.getId(), ex);
            }
        }
        return new ChatHistoryMessageResponse(
            message.getId(),
            message.getRole(),
            message.getBody(),
            message.getResponseType(),
            response != null && response.productCards() != null ? response.productCards() : List.of(),
            response != null ? response.draftAction() : null,
            message.getTraceId(),
            message.getIntent(),
            response != null && response.slots() != null ? response.slots() : Map.of(),
            message.getCreatedAt()
        );
    }

    private User requireUser(Principal principal) {
        if (principal == null || !StringUtils.hasText(principal.getName())) {
            throw new InvalidJwtException("Authentication is required for chat operations");
        }
        return userRepository.findByEmailIgnoreCase(principal.getName())
            .orElseThrow(() -> new InvalidJwtException("Authenticated user was not found"));
    }

    private User resolveOptionalUser(Principal principal) {
        if (principal == null || !StringUtils.hasText(principal.getName())) {
            return null;
        }
        return userRepository.findByEmailIgnoreCase(principal.getName()).orElse(null);
    }

    private UUID requiredUuid(JsonNode payload, String fieldName) {
        UUID value = optionalUuid(payload, fieldName);
        if (value == null) {
            throw new ApiException(fieldName + " is required", 400);
        }
        return value;
    }

    private UUID optionalUuid(JsonNode payload, String fieldName) {
        String value = text(payload, fieldName);
        return parseUuid(value);
    }

    private UUID parseUuid(String value) {
        if (!StringUtils.hasText(value)) {
            return null;
        }
        try {
            return UUID.fromString(value);
        } catch (IllegalArgumentException ex) {
            return null;
        }
    }

    private int optionalInt(JsonNode payload, String fieldName, int fallback) {
        if (payload != null && payload.hasNonNull(fieldName) && payload.get(fieldName).canConvertToInt()) {
            return payload.get(fieldName).asInt();
        }
        return fallback;
    }

    private String text(JsonNode payload, String fieldName) {
        if (payload == null || !payload.hasNonNull(fieldName)) {
            return null;
        }
        return payload.get(fieldName).asText();
    }

    private String transcriptText(JsonNode payload) {
        if (payload == null || !payload.has("transcript") || !payload.get("transcript").isArray()) {
            return null;
        }
        StringBuilder builder = new StringBuilder();
        payload.get("transcript").forEach(item -> {
            String role = item.hasNonNull("role") ? item.get("role").asText() : "user";
            String content = item.hasNonNull("content") ? item.get("content").asText() : "";
            if (!content.isBlank()) {
                if (builder.length() > 0) {
                    builder.append('\n');
                }
                builder.append(role).append(": ").append(content);
            }
        });
        return builder.length() == 0 ? null : builder.toString();
    }

    private BigDecimal toBigDecimal(Double value) {
        return value == null ? null : BigDecimal.valueOf(value);
    }

    private String firstText(String... values) {
        for (String value : values) {
            if (StringUtils.hasText(value)) {
                return value;
            }
        }
        return null;
    }

    private String safeMessage(RuntimeException ex) {
        return StringUtils.hasText(ex.getMessage()) ? ex.getMessage() : ex.getClass().getSimpleName();
    }

    private JsonNode redactedJson(Object value) {
        if (value == null) {
            return null;
        }
        return redactedJson(objectMapper.valueToTree(value));
    }

    private JsonNode redactedJson(JsonNode value) {
        return chatPayloadRedactor.redact(value);
    }

    private String redactedText(String value) {
        return chatPayloadRedactor.redactText(value);
    }

    @SuppressWarnings("unused")
    private Map<String, Object> toMap(JsonNode jsonNode) {
        return objectMapper.convertValue(jsonNode, MAP_TYPE);
    }
}
