package com.eshop.api.payment.dto;

import com.eshop.api.order.model.Order;
import com.eshop.api.order.model.PaymentTransaction;

public record PaymentInitiationRequest(
    Order order,
    PaymentTransaction transaction,
    String clientIp
) {
}
