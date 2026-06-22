package com.eshop.api.chatgateway.service;

import com.eshop.api.cart.repository.CartItemRepository;
import com.eshop.api.cart.repository.CartRepository;
import com.eshop.api.cart.service.CartService;
import com.eshop.api.catalog.repository.ProductVariantRepository;
import com.eshop.api.chatagent.client.ChatAgentClient;
import com.eshop.api.chatagent.dto.AgentChatResponse;
import com.eshop.api.chatagent.dto.AgentDraftAction;
import com.eshop.api.chatagent.dto.AgentNodeTrace;
import com.eshop.api.chatagent.dto.AgentToolCallTrace;
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
import com.eshop.api.order.repository.OrderRepository;
import com.eshop.api.support.dto.CreateSupportConversationRequest;
import com.eshop.api.support.dto.SupportConversationSummaryResponse;
import com.eshop.api.support.enums.SupportConversationStatus;
import com.eshop.api.support.service.SupportMessagingService;
import com.eshop.api.user.User;
import com.eshop.api.user.UserRepository;
import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.mockito.ArgumentCaptor;

import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class ChatGatewayServiceTest {

    private final ChatSessionRepository chatSessionRepository = mock(ChatSessionRepository.class);
    private final ChatMessageRepository chatMessageRepository = mock(ChatMessageRepository.class);
    private final ChatToolCallRepository chatToolCallRepository = mock(ChatToolCallRepository.class);
    private final ChatNodeTraceRepository chatNodeTraceRepository = mock(ChatNodeTraceRepository.class);
    private final ChatDraftActionRepository chatDraftActionRepository = mock(ChatDraftActionRepository.class);
    private final ChatAgentClient chatAgentClient = mock(ChatAgentClient.class);
    private final UserRepository userRepository = mock(UserRepository.class);
    private final CartService cartService = mock(CartService.class);
    private final CartRepository cartRepository = mock(CartRepository.class);
    private final CartItemRepository cartItemRepository = mock(CartItemRepository.class);
    private final ProductVariantRepository productVariantRepository = mock(ProductVariantRepository.class);
    private final SupportMessagingService supportMessagingService = mock(SupportMessagingService.class);
    private final OrderRepository orderRepository = mock(OrderRepository.class);
    private final ObjectMapper objectMapper = new ObjectMapper();
    private final ChatPayloadRedactor chatPayloadRedactor = new ChatPayloadRedactor(objectMapper);

    private final ChatGatewayService service = new ChatGatewayService(
        chatSessionRepository,
        chatMessageRepository,
        chatToolCallRepository,
        chatNodeTraceRepository,
        chatDraftActionRepository,
        chatAgentClient,
        userRepository,
        cartService,
        cartRepository,
        cartItemRepository,
        productVariantRepository,
        supportMessagingService,
        orderRepository,
        chatPayloadRedactor,
        objectMapper
    );

    @Test
    void sendMessagePersistsRedactedPayloadsAndTraceArtifacts() {
        List<ChatMessage> savedMessages = new ArrayList<>();
        List<ChatToolCall> savedToolCalls = new ArrayList<>();
        List<ChatNodeTrace> savedNodeTraces = new ArrayList<>();
        UUID sessionId = UUID.randomUUID();

        when(chatSessionRepository.save(any(ChatSession.class))).thenAnswer(invocation -> {
            ChatSession session = invocation.getArgument(0);
            session.setId(sessionId);
            session.setStatus(ChatSessionStatus.OPEN);
            return session;
        });
        when(chatMessageRepository.save(any(ChatMessage.class))).thenAnswer(invocation -> {
            ChatMessage message = invocation.getArgument(0);
            savedMessages.add(message);
            return message;
        });
        when(chatToolCallRepository.save(any(ChatToolCall.class))).thenAnswer(invocation -> {
            ChatToolCall toolCall = invocation.getArgument(0);
            savedToolCalls.add(toolCall);
            return toolCall;
        });
        when(chatNodeTraceRepository.save(any(ChatNodeTrace.class))).thenAnswer(invocation -> {
            ChatNodeTrace nodeTrace = invocation.getArgument(0);
            savedNodeTraces.add(nodeTrace);
            return nodeTrace;
        });
        when(chatAgentClient.chat(any(), any(), any(), any(), any(), any())).thenReturn(agentResponse());

        service.sendMessage(
            new ChatMessageRequest(
                null,
                "Please help customer@example.com at 0901234567",
                Map.of(
                    "email", "customer@example.com",
                    "phone", "0901234567",
                    "accessToken", "raw-token"
                )
            ),
            null,
            "Bearer raw-token",
            "trace-1",
            "request-1",
            "00-abcdef"
        );

        assertThat(savedMessages).hasSize(2);
        ChatMessage userMessage = savedMessages.stream()
            .filter(message -> message.getRole() == ChatMessageRole.USER)
            .findFirst()
            .orElseThrow();
        ChatMessage assistantMessage = savedMessages.stream()
            .filter(message -> message.getRole() == ChatMessageRole.ASSISTANT)
            .findFirst()
            .orElseThrow();

        assertRedacted(userMessage.getPayloadJson());
        assertRedacted(assistantMessage.getPayloadJson());
        assertThat(savedToolCalls).hasSize(1);
        assertThat(savedNodeTraces).hasSize(1);

        ChatToolCall toolCall = savedToolCalls.getFirst();
        assertRedacted(toolCall.getInputJson());
        assertRedacted(toolCall.getRequestSummary());
        assertRedacted(toolCall.getResponseSummary());
        assertRedacted(toolCall.getErrorMessage());

        ChatNodeTrace nodeTrace = savedNodeTraces.getFirst();
        assertRedacted(nodeTrace.getInputSummary());
        assertRedacted(nodeTrace.getOutputSummary());
        assertRedacted(nodeTrace.getErrorMessage());
    }

    @Test
    void confirmSupportHandoffPreservesExecutableDraftPayloadAndRedactsPersistedResultArtifacts() {
        UUID userId = UUID.randomUUID();
        UUID draftActionId = UUID.randomUUID();
        UUID conversationId = UUID.randomUUID();
        UUID sessionId = UUID.randomUUID();
        User user = User.builder()
            .id(userId)
            .email("shopper@example.com")
            .build();
        List<ChatMessage> savedMessages = new ArrayList<>();
        List<ChatDraftAction> savedDraftActions = new ArrayList<>();

        when(chatSessionRepository.save(any(ChatSession.class))).thenAnswer(invocation -> {
            ChatSession session = invocation.getArgument(0);
            session.setId(sessionId);
            session.setStatus(ChatSessionStatus.OPEN);
            return session;
        });
        when(userRepository.findByEmailIgnoreCase("shopper@example.com")).thenReturn(Optional.of(user));
        when(chatDraftActionRepository.save(any(ChatDraftAction.class))).thenAnswer(invocation -> {
            ChatDraftAction draft = invocation.getArgument(0);
            savedDraftActions.add(draft);
            return draft;
        });
        when(chatMessageRepository.save(any(ChatMessage.class))).thenAnswer(invocation -> {
            ChatMessage message = invocation.getArgument(0);
            savedMessages.add(message);
            return message;
        });
        when(chatAgentClient.chat(any(), any(), any(), any(), any(), any())).thenReturn(draftSupportHandoffResponse(draftActionId));
        when(supportMessagingService.startConversation(eq("shopper@example.com"), any(CreateSupportConversationRequest.class)))
            .thenReturn(new SupportConversationSummaryResponse(
                conversationId,
                SupportConversationStatus.OPEN,
                "Support",
                Instant.now(),
                null,
                null,
                null,
                0
            ));

        service.sendMessage(
            new ChatMessageRequest(null, "handoff", Map.of()),
            () -> "shopper@example.com",
            "Bearer raw-token",
            "trace-1",
            "request-1",
            "00-abcdef"
        );
        ChatDraftAction persistedDraft = savedDraftActions.getFirst();
        assertThat(persistedDraft.getPayloadJson().toString())
            .contains("customer@example.com", "0901234567", "raw-token");

        when(chatDraftActionRepository.findByIdAndUser_Id(draftActionId, userId)).thenReturn(Optional.of(persistedDraft));
        savedMessages.clear();
        service.confirmAction(draftActionId, () -> "shopper@example.com");

        ArgumentCaptor<CreateSupportConversationRequest> requestCaptor =
            ArgumentCaptor.forClass(CreateSupportConversationRequest.class);
        verify(supportMessagingService).startConversation(eq("shopper@example.com"), requestCaptor.capture());
        CreateSupportConversationRequest supportRequest = requestCaptor.getValue();
        assertThat(supportRequest.subject()).contains("customer@example.com", "0901234567");
        assertThat(supportRequest.message()).contains("customer@example.com", "0901234567", "raw-token");

        assertRedacted(persistedDraft.getResultJson());
        assertThat(savedMessages).hasSize(1);
        assertThat(savedMessages.getFirst().getResponseType()).isEqualTo("action_result");
        assertRedacted(savedMessages.getFirst().getPayloadJson());
    }

    private AgentChatResponse draftSupportHandoffResponse(UUID draftActionId) {
        return new AgentChatResponse(
            null,
            null,
            "support",
            "draft_action",
            "Please confirm support handoff.",
            List.of(),
            new AgentDraftAction(
                draftActionId.toString(),
                "support.handoff",
                Map.of(
                    "summary", "Help customer@example.com by phone 0901234567",
                    "transcript", List.of(
                        Map.of("role", "user", "content", "Email customer@example.com token=raw-token"),
                        Map.of("role", "assistant", "content", "Call 0901234567")
                    )
                ),
                "pending",
                Instant.now().plusSeconds(60),
                true
            ),
            true,
            List.of(),
            List.of(),
            Map.of(),
            0.9,
            0.8,
            false,
            20.0,
            0
        );
    }

    private AgentChatResponse agentResponse() {
        return new AgentChatResponse(
            null,
            null,
            "support",
            "answer",
            "I found customer@example.com and 0901234567",
            List.of(),
            null,
            false,
            List.of(new AgentToolCallTrace(
                "support.lookup",
                "error",
                12.0,
                null,
                Map.of(
                    "email", "customer@example.com",
                    "phone", "0901234567",
                    "token", "raw-token"
                ),
                "lookup customer@example.com with token=raw-token",
                "called 0901234567 and returned token=raw-token",
                null,
                "failed for customer@example.com token=raw-token",
                "RuntimeException",
                "token=raw-token failed for 0901234567"
            )),
            List.of(new AgentNodeTrace(
                "route",
                "error",
                4.0,
                "support",
                "input customer@example.com token=raw-token",
                "output 0901234567 token=raw-token",
                0.7,
                0.8,
                "RuntimeException",
                "node failed for customer@example.com and 0901234567"
            )),
            Map.of("email", "customer@example.com", "token", "raw-token"),
            0.7,
            0.8,
            true,
            30.0,
            0
        );
    }

    private void assertRedacted(JsonNode node) {
        assertThat(node).isNotNull();
        assertRedacted(node.toString());
    }

    private void assertRedacted(String value) {
        assertThat(value).doesNotContain("customer@example.com", "0901234567", "raw-token");
    }
}
