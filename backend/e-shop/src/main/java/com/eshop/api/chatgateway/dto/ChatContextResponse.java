package com.eshop.api.chatgateway.dto;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.UUID;

public record ChatContextResponse(
    UserSummary user,
    CartSummary cartSummary,
    List<RecentOrderSummary> recentOrders,
    List<RecentViewSummary> recentViews,
    String locale,
    Instant generatedAt
) {
    public record UserSummary(UUID userId, String email) {
    }

    public record CartSummary(Integer itemCount, BigDecimal subtotal, String currency) {
    }

    public record RecentOrderSummary(UUID orderId, String orderNumber, String status) {
    }

    public record RecentViewSummary(UUID productId, UUID variantId, String slug) {
    }
}
