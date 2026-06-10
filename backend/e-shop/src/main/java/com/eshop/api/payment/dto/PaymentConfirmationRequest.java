package com.eshop.api.payment.dto;

import java.util.Map;

public record PaymentConfirmationRequest(Map<String, String> payload) {
}
