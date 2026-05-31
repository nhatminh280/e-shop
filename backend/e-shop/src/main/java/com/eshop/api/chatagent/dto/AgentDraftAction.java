package com.eshop.api.chatagent.dto;

import java.time.Instant;
import java.util.Map;

public record AgentDraftAction(
    String draftActionId,
    String actionType,
    Map<String, Object> payload,
    String status,
    Instant expiresAt,
    Boolean needsConfirmation
) {
}
