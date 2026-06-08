package com.eshop.api.order.dto;

import com.eshop.api.payment.PaymentProvider;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import static org.assertj.core.api.Assertions.assertThat;

class CheckoutRequestPaymentProviderTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Test
    void defaultsPaymentProviderToVnPay() throws Exception {
        CheckoutRequest request = objectMapper.readValue("{}", CheckoutRequest.class);

        assertThat(request.getPaymentProvider()).isEqualTo(PaymentProvider.VNPAY);
    }

    @Test
    void parsesPaymentProviderCaseInsensitively() throws Exception {
        CheckoutRequest request = objectMapper.readValue(
            "{\"paymentProvider\":\"vNpAy\"}",
            CheckoutRequest.class
        );

        assertThat(request.getPaymentProvider()).isEqualTo(PaymentProvider.VNPAY);
    }
}
