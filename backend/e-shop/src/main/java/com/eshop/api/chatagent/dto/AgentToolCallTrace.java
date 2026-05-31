package com.eshop.api.chatagent.dto;

import java.util.Map;

public record AgentToolCallTrace(
    String toolName,
    String status,
    Double latencyMs,
    String traceId,
    Map<String, Object> input,
    String requestSummary,
    String responseSummary,
    String outputSummary,
    String error,
    String errorClass,
    String errorMessage
) {
}
