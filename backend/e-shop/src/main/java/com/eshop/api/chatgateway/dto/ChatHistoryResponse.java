package com.eshop.api.chatgateway.dto;

import java.util.List;
import java.util.UUID;

public record ChatHistoryResponse(
    UUID sessionId,
    List<ChatHistoryMessageResponse> messages,
    int page,
    int size,
    boolean hasNext
) {
}
