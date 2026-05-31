package com.eshop.api.payment;

import com.eshop.api.analytics.enums.InteractionType;
import com.eshop.api.analytics.service.ProductInteractionEventService;
import com.eshop.api.order.enums.OrderStatus;
import com.eshop.api.order.enums.PaymentStatus;
import com.eshop.api.order.model.Order;
import com.eshop.api.order.model.OrderStatusHistory;
import com.eshop.api.order.model.PaymentTransaction;
import com.eshop.api.order.repository.OrderRepository;
import com.eshop.api.order.repository.OrderStatusHistoryRepository;
import com.eshop.api.order.repository.PaymentTransactionRepository;
import com.eshop.api.order.service.InventoryService;
import com.eshop.api.payment.dto.VnPayConfirmResponse;
import com.eshop.api.payment.service.CurrencyConversionService;
import com.eshop.api.payment.service.VnPayCallbackService;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;

import java.math.BigDecimal;
import java.util.Map;
import java.util.Optional;
import java.util.Set;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

class VnPayCallbackServiceTest {

    private PaymentTransactionRepository paymentTransactionRepository;
    private OrderRepository orderRepository;
    private OrderStatusHistoryRepository orderStatusHistoryRepository;
    private InventoryService inventoryService;
    private ProductInteractionEventService interactionEventService;
    private VnPayCallbackService service;

    private static final String ORDER_NUMBER = "ORD-001";

    @BeforeEach
    void setUp() {
        paymentTransactionRepository = mock(PaymentTransactionRepository.class);
        orderRepository = mock(OrderRepository.class);
        orderStatusHistoryRepository = mock(OrderStatusHistoryRepository.class);
        inventoryService = mock(InventoryService.class);
        interactionEventService = mock(ProductInteractionEventService.class);

        service = new VnPayCallbackService(
                orderRepository,
                paymentTransactionRepository,
                orderStatusHistoryRepository,
                new ObjectMapper(),
                inventoryService,
                mock(CurrencyConversionService.class),
                interactionEventService
        );
    }

    @Test
    void handleReturn_firstCall_capturesPaymentAndProcessesSideEffects() {
        Order order = buildPendingOrder();
        PaymentTransaction tx = buildTransaction(PaymentStatus.PENDING, order);

        when(orderRepository.findByOrderNumber(ORDER_NUMBER)).thenReturn(Optional.of(order));
        when(paymentTransactionRepository.findTopByOrderNumberWithLock(ORDER_NUMBER)).thenReturn(Optional.of(tx));
        when(paymentTransactionRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        when(orderRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        when(orderStatusHistoryRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        VnPayConfirmResponse response = service.handleReturn(successPayload());

        assertThat(response.getPaymentStatus()).isEqualTo(PaymentStatus.CAPTURED);
        assertThat(response.isAlreadyProcessed()).isFalse();
        assertThat(tx.getStatus()).isEqualTo(PaymentStatus.CAPTURED);
        assertThat(order.getPaymentStatus()).isEqualTo(PaymentStatus.CAPTURED);
        assertThat(order.getStatus()).isEqualTo(OrderStatus.PROCESSING);
        verify(inventoryService, times(1)).clearCart(order.getCart());
    }

    @Test
    void handleReturn_secondConcurrentCall_returnsIdempotentResponseWithoutSideEffects() {
        Order order = buildAlreadyCapturedOrder();
        PaymentTransaction tx = buildTransaction(PaymentStatus.CAPTURED, order);

        when(orderRepository.findByOrderNumber(ORDER_NUMBER)).thenReturn(Optional.of(order));
        when(paymentTransactionRepository.findTopByOrderNumberWithLock(ORDER_NUMBER)).thenReturn(Optional.of(tx));

        VnPayConfirmResponse response = service.handleReturn(successPayload());

        assertThat(response.isAlreadyProcessed()).isTrue();
        assertThat(response.getPaymentStatus()).isEqualTo(PaymentStatus.CAPTURED);

        // No side effects on duplicate call
        verify(inventoryService, never()).clearCart(any());
        verify(inventoryService, never()).releaseOrderItems(any());
        verify(interactionEventService, never()).recordInteraction(any(), any(), any(), eq(InteractionType.PURCHASE), any());
        verify(paymentTransactionRepository, never()).save(any());
        verify(orderRepository, never()).save(any());
        verify(orderStatusHistoryRepository, never()).save(any());
    }

    @Test
    void handleReturn_failedPayment_releasesInventoryAndDoesNotCapture() {
        Order order = buildPendingOrder();
        PaymentTransaction tx = buildTransaction(PaymentStatus.PENDING, order);

        when(orderRepository.findByOrderNumber(ORDER_NUMBER)).thenReturn(Optional.of(order));
        when(paymentTransactionRepository.findTopByOrderNumberWithLock(ORDER_NUMBER)).thenReturn(Optional.of(tx));
        when(paymentTransactionRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        when(orderRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));
        when(orderStatusHistoryRepository.save(any())).thenAnswer(inv -> inv.getArgument(0));

        VnPayConfirmResponse response = service.handleReturn(failurePayload());

        assertThat(response.getPaymentStatus()).isEqualTo(PaymentStatus.FAILED);
        assertThat(response.isAlreadyProcessed()).isFalse();
        assertThat(tx.getStatus()).isEqualTo(PaymentStatus.FAILED);
        assertThat(order.getStatus()).isEqualTo(OrderStatus.CANCELLED);
        verify(inventoryService, times(1)).releaseOrderItems(order.getItems());
        verify(inventoryService, never()).clearCart(any());
    }

    // --- Helpers ---

    private Order buildPendingOrder() {
        Order order = new Order();
        order.setOrderNumber(ORDER_NUMBER);
        order.setStatus(OrderStatus.AWAITING_PAYMENT);
        order.setPaymentStatus(PaymentStatus.PENDING);
        order.setTotalAmount(BigDecimal.valueOf(100_000));
        order.setItems(Set.of());
        return order;
    }

    private Order buildAlreadyCapturedOrder() {
        Order order = buildPendingOrder();
        order.setStatus(OrderStatus.PROCESSING);
        order.setPaymentStatus(PaymentStatus.CAPTURED);
        return order;
    }

    private PaymentTransaction buildTransaction(PaymentStatus status, Order order) {
        return PaymentTransaction.builder()
                .order(order)
                .status(status)
                .amount(BigDecimal.valueOf(100_000))
                .currency("VND")
                .provider("vnpay")
                .method(com.eshop.api.order.enums.PaymentMethod.BANK_TRANSFER)
                .build();
    }

    private Map<String, String> successPayload() {
        return Map.of(
                "vnp_TxnRef", ORDER_NUMBER,
                "vnp_ResponseCode", "00",
                "vnp_TransactionStatus", "00",
                "vnp_Amount", "10000000",
                "vnp_TransactionNo", "TXN-TEST-001"
        );
    }

    private Map<String, String> failurePayload() {
        return Map.of(
                "vnp_TxnRef", ORDER_NUMBER,
                "vnp_ResponseCode", "24",
                "vnp_TransactionStatus", "02",
                "vnp_Amount", "10000000",
                "vnp_TransactionNo", "TXN-TEST-002"
        );
    }
}
