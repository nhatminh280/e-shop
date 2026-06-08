package com.eshop.api.payment.dto;

import com.eshop.api.order.enums.PaymentMethod;
import com.eshop.api.payment.PaymentProvider;

import java.math.BigDecimal;
import java.time.Instant;

public record PaymentInitiationResult(
    PaymentProvider provider,
    PaymentMethod paymentMethod,
    String paymentUrl,
    Instant expiresAt,
    BigDecimal providerAmount
) {
}
