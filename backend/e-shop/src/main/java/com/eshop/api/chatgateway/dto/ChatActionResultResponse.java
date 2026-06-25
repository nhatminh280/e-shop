package com.eshop.api.chatgateway.dto;

import java.util.Map;
import java.util.UUID;

public record ChatActionResultResponse(
    UUID draftActionId,
    String status,
    String actionType,
    Map<String, Object> result
) {
}
