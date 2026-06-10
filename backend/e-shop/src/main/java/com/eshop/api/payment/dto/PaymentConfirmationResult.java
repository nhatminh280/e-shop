package com.eshop.api.payment.dto;

import java.util.Map;

public record PaymentConfirmationResult(
    String merchantReference,
    PaymentConfirmationOutcome outcome,
    String providerTransactionId,
    Map<String, String> rawResponse,
    String errorCode,
    String errorMessage
) {
}
