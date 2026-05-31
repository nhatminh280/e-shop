package com.eshop.api.chatagent.dto;

public record AgentNodeTrace(
    String nodeName,
    String status,
    Double latencyMs,
    String intent,
    String inputSummary,
    String outputSummary,
    Double intentConfidence,
    Double routingConfidence,
    String errorClass,
    String errorMessage
) {
}
