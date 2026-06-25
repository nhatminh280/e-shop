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
