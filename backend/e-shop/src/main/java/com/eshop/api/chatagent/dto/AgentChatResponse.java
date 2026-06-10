package com.eshop.api.chatagent.dto;

import java.util.List;
import java.util.Map;

public record AgentChatResponse(
    String sessionId,
    String traceId,
    String intent,
    String responseType,
    String answer,
    List<AgentProductCard> productCards,
    AgentDraftAction draftAction,
    Boolean needsConfirmation,
    List<AgentToolCallTrace> toolCalls,
    List<AgentNodeTrace> nodeTraces,
    Map<String, Object> slots,
    Double intentConfidence,
    Double routingConfidence,
    Boolean needsReview,
    Double latencyMs,
    Integer fallbackCount
) {
}
