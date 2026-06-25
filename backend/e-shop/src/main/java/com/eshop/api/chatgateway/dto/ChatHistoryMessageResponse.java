package com.eshop.api.chatgateway.dto;

import com.eshop.api.chatagent.dto.AgentDraftAction;
import com.eshop.api.chatagent.dto.AgentProductCard;
import com.eshop.api.chatgateway.enums.ChatMessageRole;

import java.time.Instant;
import java.util.List;
import java.util.Map;
import java.util.UUID;

public record ChatHistoryMessageResponse(
    UUID id,
    ChatMessageRole role,
    String body,
    String responseType,
    List<AgentProductCard> productCards,
    AgentDraftAction draftAction,
    String traceId,
    String intent,
    Map<String, Object> slots,
    Instant createdAt
) {
}
