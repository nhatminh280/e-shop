package com.eshop.api.chatagent.dto;

import java.util.List;

public record AgentProductCard(
    String productId,
    String variantId,
    String name,
    String slug,
    String category,
    String gender,
    Integer price,
    String currency,
    String imageUrl,
    List<String> colors,
    List<String> sizes,
    Boolean inStock,
    Integer stock,
    String reason,
    Integer recommendationRank,
    Double recommendationScore,
    String recommendationReason
) {
}
