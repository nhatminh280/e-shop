package com.eshop.api.payment;

import com.eshop.api.order.enums.PaymentMethod;
import com.eshop.api.payment.dto.PaymentConfirmationRequest;
import com.eshop.api.payment.dto.PaymentConfirmationResult;
import com.eshop.api.payment.dto.PaymentInitiationRequest;
import com.eshop.api.payment.dto.PaymentInitiationResult;

public interface PaymentProviderStrategy {

    PaymentProvider provider();

    PaymentMethod paymentMethod();

    PaymentInitiationResult initiate(PaymentInitiationRequest request);

    PaymentConfirmationResult confirm(PaymentConfirmationRequest request);
}
