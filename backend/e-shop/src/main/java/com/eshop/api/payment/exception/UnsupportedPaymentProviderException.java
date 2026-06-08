package com.eshop.api.payment.exception;

import com.eshop.api.exception.ApiException;

public class UnsupportedPaymentProviderException extends ApiException {

    public UnsupportedPaymentProviderException(String provider) {
        super("Unsupported payment provider: " + provider, 400);
    }
}
