package com.eshop.api.payment;

import com.eshop.api.payment.exception.UnsupportedPaymentProviderException;
import org.springframework.stereotype.Component;

import java.util.EnumMap;
import java.util.List;
import java.util.Map;

@Component
public class PaymentProviderRegistry {

    private final Map<PaymentProvider, PaymentProviderStrategy> strategies;

    public PaymentProviderRegistry(List<PaymentProviderStrategy> strategies) {
        EnumMap<PaymentProvider, PaymentProviderStrategy> registrations = new EnumMap<>(PaymentProvider.class);
        for (PaymentProviderStrategy strategy : strategies) {
            PaymentProvider provider = strategy.provider();
            PaymentProviderStrategy duplicate = registrations.putIfAbsent(provider, strategy);
            if (duplicate != null) {
                throw new IllegalStateException("Duplicate payment provider strategy: " + provider);
            }
        }
        this.strategies = Map.copyOf(registrations);
    }

    public PaymentProviderStrategy get(PaymentProvider provider) {
        PaymentProviderStrategy strategy = strategies.get(provider);
        if (strategy == null) {
            throw new UnsupportedPaymentProviderException(provider == null ? null : provider.value());
        }
        return strategy;
    }
}
