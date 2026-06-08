package com.eshop.api.payment.vnpay;

import com.eshop.api.config.AppEnv;
import com.eshop.api.order.enums.PaymentMethod;
import com.eshop.api.order.model.Order;
import com.eshop.api.order.model.PaymentTransaction;
import com.eshop.api.payment.PaymentProvider;
import com.eshop.api.payment.dto.PaymentConfirmationOutcome;
import com.eshop.api.payment.dto.PaymentConfirmationRequest;
import com.eshop.api.payment.dto.PaymentInitiationRequest;
import com.eshop.api.payment.service.CurrencyConversionService;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class VnPayPaymentProviderTest {

    private VnPayPaymentProvider provider;

    @BeforeEach
    void setUp() {
        AppEnv appEnv = new AppEnv();
        AppEnv.Payment.Vnpay config = appEnv.getPayment().getVnpay();
        config.setTmnCode("TEST");
        config.setHashSecret("secret");
        config.setApiUrl("https://sandbox.example/pay");
        config.setReturnUrl("https://shop.example/payment-return");
        provider = new VnPayPaymentProvider(appEnv, new CurrencyConversionService());
    }

    @Test
    void initiatesVnPayPaymentWithCanonicalProviderAndMethod() {
        Order order = new Order();
        order.setOrderNumber("ORD-001");
        order.setTotalAmount(new BigDecimal("10.00"));
        PaymentTransaction transaction = PaymentTransaction.builder()
            .idempotencyKey("ORD-001")
            .build();

        var result = provider.initiate(new PaymentInitiationRequest(order, transaction, "127.0.0.1"));

        assertThat(result.provider()).isEqualTo(PaymentProvider.VNPAY);
        assertThat(result.paymentMethod()).isEqualTo(PaymentMethod.CARD);
        assertThat(result.providerAmount()).isEqualByComparingTo("263555.30");
        assertThat(result.paymentUrl())
            .startsWith("https://sandbox.example/pay?")
            .contains("vnp_TxnRef=ORD-001")
            .contains("vnp_SecureHash=");
        assertThat(result.expiresAt()).isNotNull();
    }

    @Test
    void mapsSuccessfulConfirmationToCaptured() {
        var result = provider.confirm(new PaymentConfirmationRequest(payload("00", "00")));

        assertThat(result.merchantReference()).isEqualTo("ORD-001");
        assertThat(result.outcome()).isEqualTo(PaymentConfirmationOutcome.CAPTURED);
        assertThat(result.providerTransactionId()).isEqualTo("TXN-001");
    }

    @Test
    void mapsTerminalUnsuccessfulConfirmationToFailed() {
        var result = provider.confirm(new PaymentConfirmationRequest(payload("24", "02")));

        assertThat(result.outcome()).isEqualTo(PaymentConfirmationOutcome.FAILED);
        assertThat(result.errorCode()).isEqualTo("24");
        assertThat(result.errorMessage()).isEqualTo("02");
    }

    @Test
    void mapsIncompleteConfirmationToPending() {
        var result = provider.confirm(new PaymentConfirmationRequest(payload("00", "01")));

        assertThat(result.outcome()).isEqualTo(PaymentConfirmationOutcome.PENDING);
    }

    private Map<String, String> payload(String responseCode, String transactionStatus) {
        return Map.of(
            "vnp_TxnRef", "ORD-001",
            "vnp_ResponseCode", responseCode,
            "vnp_TransactionStatus", transactionStatus,
            "vnp_TransactionNo", "TXN-001"
        );
    }
}
