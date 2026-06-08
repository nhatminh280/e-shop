package com.eshop.api.payment;

import com.eshop.api.payment.exception.UnsupportedPaymentProviderException;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatIllegalStateException;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

class PaymentProviderRegistryTest {

    @Test
    void parsesProviderCaseInsensitively() {
        assertThat(PaymentProvider.fromValue("vNpAy")).isEqualTo(PaymentProvider.VNPAY);
        assertThat(PaymentProvider.fromValue(null)).isEqualTo(PaymentProvider.VNPAY);
    }

    @Test
    void selectsRegisteredProvider() {
        PaymentProviderStrategy strategy = strategyFor(PaymentProvider.VNPAY);

        PaymentProviderRegistry registry = new PaymentProviderRegistry(List.of(strategy));

        assertThat(registry.get(PaymentProvider.VNPAY)).isSameAs(strategy);
    }

    @Test
    void rejectsUnsupportedProvider() {
        assertThatThrownBy(() -> PaymentProvider.fromValue("stripe"))
            .isInstanceOf(UnsupportedPaymentProviderException.class)
            .hasMessageContaining("stripe");
    }

    @Test
    void rejectsDuplicateProviderRegistrations() {
        PaymentProviderStrategy first = strategyFor(PaymentProvider.VNPAY);
        PaymentProviderStrategy second = strategyFor(PaymentProvider.VNPAY);

        assertThatIllegalStateException()
            .isThrownBy(() -> new PaymentProviderRegistry(List.of(first, second)))
            .withMessageContaining("VNPAY");
    }

    private PaymentProviderStrategy strategyFor(PaymentProvider provider) {
        PaymentProviderStrategy strategy = mock(PaymentProviderStrategy.class);
        when(strategy.provider()).thenReturn(provider);
        return strategy;
    }
}
