package com.eshop.api.chatgateway.dto;

import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record ChatReviewMessageDetailResponse(
    UUID messageId,
    UUID sessionId,
    UUID userId,
    String body,
    String intent,
    String responseType,
    String traceId,
    Integer fallbackCount,
    Instant createdAt,
    List<String> reviewReasons,
    List<SessionMessage> sessionMessages,
    List<ToolCall> toolCalls,
    List<NodeTrace> nodeTraces,
    List<DraftAction> draftActions
) {
    public record SessionMessage(
        UUID messageId,
        String role,
        String body,
        String responseType,
        String traceId,
        Instant createdAt
    ) {
    }

    public record ToolCall(
        UUID toolCallId,
        String toolName,
        String status,
        String traceId,
        Instant createdAt
    ) {
    }

    public record NodeTrace(
        UUID nodeTraceId,
        String nodeName,
        String status,
        String intent,
        String traceId,
        Instant createdAt
    ) {
    }

    public record DraftAction(
        UUID draftActionId,
        String actionType,
        String status,
        Instant expiresAt
    ) {
    }
}
