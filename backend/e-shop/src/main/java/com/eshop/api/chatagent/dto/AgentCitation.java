package com.eshop.api.chatagent.dto;

public record AgentCitation(
    String sourceId,
    String sourceType,
    String title,
    String snippet,
    Double score
) {
}
