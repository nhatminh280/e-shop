package com.eshop.api.order.service;

import com.eshop.api.order.enums.OrderStatus;
import com.eshop.api.order.enums.PaymentMethod;
import com.eshop.api.order.enums.PaymentStatus;
import com.eshop.api.order.model.Order;
import com.eshop.api.order.model.PaymentTransaction;
import com.eshop.api.order.repository.OrderRepository;
import com.eshop.api.order.repository.OrderStatusHistoryRepository;
import com.eshop.api.order.repository.PaymentTransactionRepository;
import com.eshop.api.payment.PaymentProvider;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.test.util.ReflectionTestUtils;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

class OrderCleanupSchedulerTest {

    private OrderRepository orderRepository;
    private OrderStatusHistoryRepository orderStatusHistoryRepository;
    private PaymentTransactionRepository paymentTransactionRepository;
    private InventoryService inventoryService;
    private OrderCleanupScheduler scheduler;

    @BeforeEach
    void setUp() {
        orderRepository = mock(OrderRepository.class);
        orderStatusHistoryRepository = mock(OrderStatusHistoryRepository.class);
        paymentTransactionRepository = mock(PaymentTransactionRepository.class);
        inventoryService = mock(InventoryService.class);

        scheduler = new OrderCleanupScheduler(
            orderRepository,
            orderStatusHistoryRepository,
            paymentTransactionRepository,
            inventoryService
        );
        ReflectionTestUtils.setField(scheduler, "awaitingPaymentTimeoutMinutes", 30L);
    }

    @Test
    void cancelsStaleOrdersAndMarksPendingPaymentTransactionsFailed() {
        Order order = staleAwaitingPaymentOrder();
        PaymentTransaction transaction = pendingTransaction(order);
        when(orderRepository.findByStatusAndPaymentStatusAndPlacedAtBefore(
            eq(OrderStatus.AWAITING_PAYMENT),
            eq(PaymentStatus.PENDING),
            any(Instant.class)
        )).thenReturn(List.of(order));
        when(paymentTransactionRepository.findByOrderInAndStatus(List.of(order), PaymentStatus.PENDING))
            .thenReturn(List.of(transaction));

        scheduler.cancelStaleAwaitingPaymentOrders();

        assertThat(order.getStatus()).isEqualTo(OrderStatus.CANCELLED);
        assertThat(order.getPaymentStatus()).isEqualTo(PaymentStatus.FAILED);
        assertThat(order.getCancelledAt()).isNotNull();
        assertThat(transaction.getStatus()).isEqualTo(PaymentStatus.FAILED);
        assertThat(transaction.getErrorCode()).isEqualTo("PAYMENT_TIMEOUT");
        assertThat(transaction.getErrorMessage()).isEqualTo("Payment timed out before confirmation");
        verify(paymentTransactionRepository).saveAll(List.of(transaction));
        verify(orderRepository).save(order);
        verify(orderStatusHistoryRepository).save(any());
        verify(inventoryService).releaseOrderItems(order.getItems());
    }

    private Order staleAwaitingPaymentOrder() {
        Order order = new Order();
        order.setStatus(OrderStatus.AWAITING_PAYMENT);
        order.setPaymentStatus(PaymentStatus.PENDING);
        order.setPlacedAt(Instant.now().minusSeconds(3600));
        order.setItems(Set.of());
        return order;
    }

    private PaymentTransaction pendingTransaction(Order order) {
        return PaymentTransaction.builder()
            .order(order)
            .provider(PaymentProvider.VNPAY)
            .status(PaymentStatus.PENDING)
            .amount(new BigDecimal("100.00"))
            .currency("USD")
            .method(PaymentMethod.CARD)
            .build();
    }
}
