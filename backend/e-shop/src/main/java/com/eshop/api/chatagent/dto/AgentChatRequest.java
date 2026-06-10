package com.eshop.api.chatagent.dto;

import jakarta.validation.constraints.NotBlank;

import java.util.Map;

public record AgentChatRequest(
    @NotBlank(message = "Message is required")
    String message,
    @NotBlank(message = "Session ID is required")
    String sessionId,
    String traceId,
    String requestId,
    String traceparent,
    String userId,
    Boolean authenticated,
    Map<String, Object> pageContext
) {
}
