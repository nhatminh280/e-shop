package com.eshop.api.chatgateway.dto;

import jakarta.validation.constraints.NotBlank;

import java.util.Map;
import java.util.UUID;

public record ChatMessageRequest(
    UUID sessionId,
    @NotBlank(message = "Message is required")
    String message,
    Map<String, Object> clientContext
) {
}
