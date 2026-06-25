package com.eshop.api.chatgateway.controller;

import com.eshop.api.chatagent.dto.AgentChatResponse;
import com.eshop.api.chatgateway.dto.ChatActionResultResponse;
import com.eshop.api.chatgateway.dto.ChatContextResponse;
import com.eshop.api.chatgateway.dto.ChatHistoryResponse;
import com.eshop.api.chatgateway.dto.ChatMessageRequest;
import com.eshop.api.chatgateway.dto.ChatReviewMessageDetailResponse;
import com.eshop.api.chatgateway.dto.ChatReviewMessageResponse;
import com.eshop.api.chatgateway.service.ChatGatewayService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.validation.beanvalidation.LocalValidatorFactoryBean;

import java.security.Principal;
import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class ChatGatewayControllerTest {

    private ChatGatewayService chatGatewayService;
    private MockMvc mockMvc;
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        chatGatewayService = mock(ChatGatewayService.class);
        LocalValidatorFactoryBean validator = new LocalValidatorFactoryBean();
        validator.afterPropertiesSet();
        mockMvc = MockMvcBuilders
            .standaloneSetup(new ChatGatewayController(chatGatewayService))
            .setValidator(validator)
            .build();
        objectMapper = new ObjectMapper();
    }

    @Test
    void shouldAcceptMessageWithoutSessionIdAndReturnStructuredResponse() throws Exception {
        UUID sessionId = UUID.randomUUID();
        when(chatGatewayService.sendMessage(any(), any(Principal.class), eq("Bearer token"), eq("trace-1"), eq("request-1"), eq("00-abc")))
            .thenReturn(new AgentChatResponse(
                sessionId.toString(),
                "trace-1",
                "product_search",
                "product_results",
                "I found matching products.",
                List.of(),
                null,
                false,
                List.of(),
                List.of(),
                Map.of(),
                List.of(),
                0.9,
                0.9,
                false,
                123.4,
                0
            ));

        mockMvc.perform(post("/api/chat/messages")
                .principal(() -> "customer@example.com")
                .header("Authorization", "Bearer token")
                .header("x-trace-id", "trace-1")
                .header("x-request-id", "request-1")
                .header("traceparent", "00-abc")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(new ChatMessageRequest(
                    null,
                    "ao khoac den size M",
                    Map.of("locale", "vi-VN")
                ))))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.sessionId").value(sessionId.toString()))
            .andExpect(jsonPath("$.intent").value("product_search"))
            .andExpect(jsonPath("$.responseType").value("product_results"))
            .andExpect(jsonPath("$.answer").value("I found matching products."));
    }

    @Test
    void shouldConfirmDraftAction() throws Exception {
        UUID draftActionId = UUID.randomUUID();
        when(chatGatewayService.confirmAction(eq(draftActionId), any(Principal.class)))
            .thenReturn(new ChatActionResultResponse(draftActionId, "completed", "cart.add", Map.of("cartItemCount", 3)));

        mockMvc.perform(post("/api/chat/actions/{draftActionId}/confirm", draftActionId)
                .principal(() -> "customer@example.com"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.draftActionId").value(draftActionId.toString()))
            .andExpect(jsonPath("$.status").value("completed"))
            .andExpect(jsonPath("$.actionType").value("cart.add"));
    }

    @Test
    void shouldCancelDraftAction() throws Exception {
        UUID draftActionId = UUID.randomUUID();
        when(chatGatewayService.cancelAction(eq(draftActionId), any(Principal.class)))
            .thenReturn(new ChatActionResultResponse(draftActionId, "cancelled", "cart.add", Map.of()));

        mockMvc.perform(post("/api/chat/actions/{draftActionId}/cancel", draftActionId)
                .principal(() -> "customer@example.com"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.draftActionId").value(draftActionId.toString()))
            .andExpect(jsonPath("$.status").value("cancelled"));
    }

    @Test
    void shouldLoadChatHistory() throws Exception {
        UUID sessionId = UUID.randomUUID();
        when(chatGatewayService.getHistory(eq(sessionId), eq(0), eq(50), any(Principal.class)))
            .thenReturn(new ChatHistoryResponse(sessionId, List.of(), 0, 50, false));

        mockMvc.perform(get("/api/chat/sessions/{sessionId}/messages", sessionId)
                .principal(() -> "customer@example.com")
                .param("page", "0")
                .param("size", "50"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.sessionId").value(sessionId.toString()))
            .andExpect(jsonPath("$.page").value(0))
            .andExpect(jsonPath("$.size").value(50));
    }

    @Test
    void shouldReturnChatContext() throws Exception {
        when(chatGatewayService.getContext(any(Principal.class), eq("vi-VN")))
            .thenReturn(new ChatContextResponse(
                new ChatContextResponse.UserSummary(UUID.randomUUID(), null),
                new ChatContextResponse.CartSummary(2, java.math.BigDecimal.valueOf(780000), "VND"),
                List.of(),
                List.of(),
                "vi-VN",
                null
            ));

        mockMvc.perform(get("/api/chat/context")
                .principal(() -> "customer@example.com")
                .param("locale", "vi-VN"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.cartSummary.itemCount").value(2))
            .andExpect(jsonPath("$.locale").value("vi-VN"));
    }

    @Test
    void shouldReturnReviewMessages() throws Exception {
        UUID messageId = UUID.randomUUID();
        UUID sessionId = UUID.randomUUID();
        UUID userId = UUID.randomUUID();
        when(chatGatewayService.getReviewMessages(
            eq(0),
            eq(25),
            isNull(),
            isNull(),
            isNull(),
            isNull(),
            any(Principal.class)
        ))
            .thenReturn(new PageImpl<>(List.of(new ChatReviewMessageResponse(
                messageId,
                sessionId,
                userId,
                "Fallback answer",
                "fallback",
                "fallback",
                "trace-review-1",
                1,
                Instant.parse("2026-06-22T10:15:30Z"),
                List.of("fallback_count")
            )), PageRequest.of(0, 25), 1));

        mockMvc.perform(get("/api/chat/review/messages")
                .principal(() -> "customer@example.com")
                .param("page", "0")
                .param("size", "25"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.content[0].messageId").value(messageId.toString()))
            .andExpect(jsonPath("$.content[0].sessionId").value(sessionId.toString()))
            .andExpect(jsonPath("$.content[0].reviewReasons[0]").value("fallback_count"));
    }

    @Test
    void shouldPassReviewQueueFilters() throws Exception {
        when(chatGatewayService.getReviewMessages(
            eq(1),
            eq(10),
            eq(UUID.fromString("3e61ff9e-6c31-4804-bfb0-b9224cc611e3")),
            eq("tool_error"),
            eq(true),
            eq("timeout"),
            any(Principal.class)
        )).thenReturn(new PageImpl<>(List.of(), PageRequest.of(1, 10), 0));

        mockMvc.perform(get("/api/chat/review/messages")
                .principal(() -> "staff@example.com")
                .param("page", "1")
                .param("size", "10")
                .param("sessionId", "3e61ff9e-6c31-4804-bfb0-b9224cc611e3")
                .param("responseType", "tool_error")
                .param("hasFallback", "true")
                .param("toolStatus", "timeout"))
            .andExpect(status().isOk());
    }

    @Test
    void shouldReturnReviewMessageDetail() throws Exception {
        UUID messageId = UUID.randomUUID();
        UUID sessionId = UUID.randomUUID();
        UUID userId = UUID.randomUUID();
        when(chatGatewayService.getReviewMessageDetail(eq(messageId), any(Principal.class)))
            .thenReturn(new ChatReviewMessageDetailResponse(
                messageId,
                sessionId,
                userId,
                "Fallback answer",
                "fallback",
                "tool_error",
                "trace-review-detail-1",
                1,
                Instant.parse("2026-06-22T10:15:30Z"),
                List.of("fallback_count", "response_type"),
                List.of(
                    new ChatReviewMessageDetailResponse.SessionMessage(
                        UUID.randomUUID(),
                        "USER",
                        "ao khoac den",
                        null,
                        "trace-review-detail-1",
                        Instant.parse("2026-06-22T10:15:00Z")
                    ),
                    new ChatReviewMessageDetailResponse.SessionMessage(
                        messageId,
                        "ASSISTANT",
                        "Fallback answer",
                        "tool_error",
                        "trace-review-detail-1",
                        Instant.parse("2026-06-22T10:15:30Z")
                    )
                ),
                List.of(
                    new ChatReviewMessageDetailResponse.ToolCall(
                        UUID.randomUUID(),
                        "catalog.search",
                        "timeout",
                        "trace-review-detail-1",
                        Instant.parse("2026-06-22T10:15:20Z")
                    )
                ),
                List.of(
                    new ChatReviewMessageDetailResponse.NodeTrace(
                        UUID.randomUUID(),
                        "route_intent",
                        "success",
                        "product_search",
                        "trace-review-detail-1",
                        Instant.parse("2026-06-22T10:15:18Z")
                    )
                ),
                List.of(
                    new ChatReviewMessageDetailResponse.DraftAction(
                        UUID.randomUUID(),
                        "cart.add",
                        "pending",
                        Instant.parse("2026-06-22T10:20:30Z")
                    )
                )
            ));

        mockMvc.perform(get("/api/chat/review/messages/{messageId}", messageId)
                .principal(() -> "staff@example.com"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.messageId").value(messageId.toString()))
            .andExpect(jsonPath("$.sessionMessages[1].role").value("ASSISTANT"))
            .andExpect(jsonPath("$.toolCalls[0].toolName").value("catalog.search"))
            .andExpect(jsonPath("$.draftActions[0].actionType").value("cart.add"));
    }
}
