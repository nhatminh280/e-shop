package com.eshop.api.payment;

import com.eshop.api.payment.exception.UnsupportedPaymentProviderException;
import com.fasterxml.jackson.annotation.JsonCreator;
import com.fasterxml.jackson.annotation.JsonValue;

import java.util.Locale;

public enum PaymentProvider {
    VNPAY;

    @JsonCreator
    public static PaymentProvider fromValue(String value) {
        if (value == null || value.isBlank()) {
            return VNPAY;
        }

        try {
            return valueOf(value.trim().toUpperCase(Locale.ENGLISH));
        } catch (IllegalArgumentException exception) {
            throw new UnsupportedPaymentProviderException(value);
        }
    }

    @JsonValue
    public String value() {
        return name();
    }
}
