package com.eshop.api.payment;

import com.eshop.api.analytics.service.ProductInteractionEventService;
import com.eshop.api.order.enums.OrderStatus;
import com.eshop.api.order.enums.PaymentMethod;
import com.eshop.api.order.enums.PaymentStatus;
import com.eshop.api.order.exception.PaymentValidationException;
import com.eshop.api.order.model.Order;
import com.eshop.api.order.model.PaymentTransaction;
import com.eshop.api.order.repository.OrderRepository;
import com.eshop.api.order.repository.OrderStatusHistoryRepository;
import com.eshop.api.order.repository.PaymentTransactionRepository;
import com.eshop.api.order.service.InventoryService;
import com.eshop.api.payment.dto.PaymentConfirmationOutcome;
import com.eshop.api.payment.dto.PaymentConfirmationResult;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class PaymentOrchestrationServiceTest {

    private static final String ORDER_NUMBER = "ORD-001";

    private PaymentProviderStrategy strategy;
    private PaymentTransactionRepository paymentTransactionRepository;
    private OrderRepository orderRepository;
    private OrderStatusHistoryRepository historyRepository;
    private InventoryService inventoryService;
    private ProductInteractionEventService interactionEventService;
    private PaymentOrchestrationService service;

    @BeforeEach
    void setUp() {
        strategy = mock(PaymentProviderStrategy.class);
        when(strategy.provider()).thenReturn(PaymentProvider.VNPAY);
        paymentTransactionRepository = mock(PaymentTransactionRepository.class);
        orderRepository = mock(OrderRepository.class);
        historyRepository = mock(OrderStatusHistoryRepository.class);
        inventoryService = mock(InventoryService.class);
        interactionEventService = mock(ProductInteractionEventService.class);

        service = new PaymentOrchestrationService(
            new PaymentProviderRegistry(java.util.List.of(strategy)),
            paymentTransactionRepository,
            orderRepository,
            historyRepository,
            inventoryService,
            interactionEventService,
            new ObjectMapper()
        );
    }

    @Test
    void capturedConfirmationProcessesPaymentAndCart() {
        Order order = pendingOrder();
        PaymentTransaction transaction = transaction(order, PaymentProvider.VNPAY, PaymentStatus.PENDING);
        arrangeConfirmation(transaction, result(PaymentConfirmationOutcome.CAPTURED));

        var response = service.confirm(PaymentProvider.VNPAY, Map.of("payload", "value"));

        assertThat(response.getPaymentStatus()).isEqualTo(PaymentStatus.CAPTURED);
        assertThat(response.isAlreadyProcessed()).isFalse();
        assertThat(transaction.getStatus()).isEqualTo(PaymentStatus.CAPTURED);
        assertThat(order.getStatus()).isEqualTo(OrderStatus.PROCESSING);
        verify(inventoryService).clearCart(order.getCart());
        verify(inventoryService, never()).releaseOrderItems(any());
        verify(historyRepository).save(any());
    }

    @Test
    void failedConfirmationCancelsOrderAndReleasesInventory() {
        Order order = pendingOrder();
        PaymentTransaction transaction = transaction(order, PaymentProvider.VNPAY, PaymentStatus.PENDING);
        arrangeConfirmation(transaction, result(PaymentConfirmationOutcome.FAILED));

        var response = service.confirm(PaymentProvider.VNPAY, Map.of("payload", "value"));

        assertThat(response.getPaymentStatus()).isEqualTo(PaymentStatus.FAILED);
        assertThat(order.getStatus()).isEqualTo(OrderStatus.CANCELLED);
        verify(inventoryService).releaseOrderItems(order.getItems());
        verify(inventoryService, never()).clearCart(any());
        verify(historyRepository).save(any());
    }

    @Test
    void pendingConfirmationOnlyRecordsProviderResponse() {
        Order order = pendingOrder();
        PaymentTransaction transaction = transaction(order, PaymentProvider.VNPAY, PaymentStatus.PENDING);
        arrangeConfirmation(transaction, result(PaymentConfirmationOutcome.PENDING));

        var response = service.confirm(PaymentProvider.VNPAY, Map.of("payload", "value"));

        assertThat(response.getPaymentStatus()).isEqualTo(PaymentStatus.PENDING);
        assertThat(order.getStatus()).isEqualTo(OrderStatus.AWAITING_PAYMENT);
        verify(paymentTransactionRepository).save(transaction);
        verify(orderRepository, never()).save(any());
        verify(historyRepository, never()).save(any());
        verify(inventoryService, never()).clearCart(any());
        verify(inventoryService, never()).releaseOrderItems(any());
    }

    @Test
    void terminalTransactionReturnsIdempotentResponseWithoutSideEffects() {
        Order order = pendingOrder();
        order.setPaymentStatus(PaymentStatus.CAPTURED);
        order.setStatus(OrderStatus.PROCESSING);
        PaymentTransaction transaction = transaction(order, PaymentProvider.VNPAY, PaymentStatus.CAPTURED);
        arrangeConfirmation(transaction, result(PaymentConfirmationOutcome.CAPTURED));

        var response = service.confirm(PaymentProvider.VNPAY, Map.of("payload", "value"));

        assertThat(response.isAlreadyProcessed()).isTrue();
        verify(paymentTransactionRepository, never()).save(any());
        verify(orderRepository, never()).save(any());
        verify(historyRepository, never()).save(any());
        verify(inventoryService, never()).clearCart(any());
    }

    @Test
    void rejectsRouteProviderThatDoesNotMatchStoredTransaction() {
        PaymentProviderStrategy otherStrategy = mock(PaymentProviderStrategy.class);
        when(otherStrategy.provider()).thenReturn(PaymentProvider.VNPAY);
        Order order = pendingOrder();
        PaymentTransaction transaction = transaction(order, null, PaymentStatus.PENDING);
        arrangeConfirmation(transaction, result(PaymentConfirmationOutcome.CAPTURED));

        assertThatThrownBy(() -> service.confirm(PaymentProvider.VNPAY, Map.of("payload", "value")))
            .isInstanceOf(PaymentValidationException.class)
            .hasMessageContaining("does not match");

        verify(paymentTransactionRepository, never()).save(any());
        verify(orderRepository, never()).save(any());
    }

    private void arrangeConfirmation(PaymentTransaction transaction, PaymentConfirmationResult result) {
        when(strategy.confirm(any())).thenReturn(result);
        when(paymentTransactionRepository.findTopByOrderNumberWithLock(ORDER_NUMBER))
            .thenReturn(Optional.of(transaction));
        when(paymentTransactionRepository.save(any())).thenAnswer(invocation -> invocation.getArgument(0));
        when(orderRepository.save(any())).thenAnswer(invocation -> invocation.getArgument(0));
    }

    private PaymentConfirmationResult result(PaymentConfirmationOutcome outcome) {
        return new PaymentConfirmationResult(
            ORDER_NUMBER,
            outcome,
            "TXN-001",
            Map.of("provider", "response"),
            outcome == PaymentConfirmationOutcome.FAILED ? "24" : null,
            outcome == PaymentConfirmationOutcome.FAILED ? "02" : null
        );
    }

    private Order pendingOrder() {
        Order order = new Order();
        order.setOrderNumber(ORDER_NUMBER);
        order.setStatus(OrderStatus.AWAITING_PAYMENT);
        order.setPaymentStatus(PaymentStatus.PENDING);
        order.setTotalAmount(new BigDecimal("100.00"));
        order.setItems(Set.of());
        return order;
    }

    private PaymentTransaction transaction(
        Order order,
        PaymentProvider provider,
        PaymentStatus status
    ) {
        return PaymentTransaction.builder()
            .order(order)
            .provider(provider)
            .status(status)
            .amount(new BigDecimal("100.00"))
            .currency("USD")
            .method(PaymentMethod.CARD)
            .build();
    }
}
