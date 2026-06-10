package com.eshop.api.payment;

import com.eshop.api.analytics.enums.InteractionType;
import com.eshop.api.analytics.service.ProductInteractionEventService;
import com.eshop.api.catalog.model.Product;
import com.eshop.api.catalog.model.ProductVariant;
import com.eshop.api.order.enums.OrderStatus;
import com.eshop.api.order.enums.PaymentStatus;
import com.eshop.api.order.exception.PaymentValidationException;
import com.eshop.api.order.model.Order;
import com.eshop.api.order.model.OrderStatusHistory;
import com.eshop.api.order.model.PaymentTransaction;
import com.eshop.api.order.repository.OrderRepository;
import com.eshop.api.order.repository.OrderStatusHistoryRepository;
import com.eshop.api.order.repository.PaymentTransactionRepository;
import com.eshop.api.order.service.InventoryService;
import com.eshop.api.payment.dto.PaymentConfirmationOutcome;
import com.eshop.api.payment.dto.PaymentConfirmationRequest;
import com.eshop.api.payment.dto.PaymentConfirmationResponse;
import com.eshop.api.payment.dto.PaymentConfirmationResult;
import com.fasterxml.jackson.databind.ObjectMapper;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Map;
import java.util.Optional;

@Service
@RequiredArgsConstructor
@Slf4j
public class PaymentOrchestrationService {

    private final PaymentProviderRegistry providerRegistry;
    private final PaymentTransactionRepository paymentTransactionRepository;
    private final OrderRepository orderRepository;
    private final OrderStatusHistoryRepository orderStatusHistoryRepository;
    private final InventoryService inventoryService;
    private final ProductInteractionEventService interactionEventService;
    private final ObjectMapper objectMapper;

    @Transactional
    public PaymentConfirmationResponse confirm(PaymentProvider provider, Map<String, String> payload) {
        PaymentProviderStrategy strategy = providerRegistry.get(provider);
        PaymentConfirmationResult result = strategy.confirm(new PaymentConfirmationRequest(payload));
        String orderNumber = result.merchantReference();

        PaymentTransaction transaction = paymentTransactionRepository
            .findTopByOrderNumberWithLock(orderNumber)
            .orElseThrow(() -> new PaymentValidationException(
                "Payment transaction not found for order: " + orderNumber));
        Order order = transaction.getOrder();
        if (order == null) {
            throw new PaymentValidationException("Order not found: " + orderNumber);
        }
        if (transaction.getProvider() != provider) {
            throw new PaymentValidationException(
                "Payment provider " + provider + " does not match transaction provider "
                    + transaction.getProvider());
        }

        if (transaction.getStatus() == PaymentStatus.CAPTURED
            || transaction.getStatus() == PaymentStatus.FAILED) {
            return response(order, transaction, true);
        }

        transaction.setRawResponse(objectMapper.valueToTree(result.rawResponse()));
        transaction.setProviderTransactionId(result.providerTransactionId());
        transaction.setErrorCode(result.errorCode());
        transaction.setErrorMessage(result.errorMessage());

        if (result.outcome() == PaymentConfirmationOutcome.CAPTURED) {
            applyCaptured(order, transaction);
            logPurchaseEvents(order);
            inventoryService.clearCart(order.getCart());
            persistStateChange(order, transaction, provider + " payment captured");
            log.info("{} payment captured for order {}", provider, orderNumber);
        } else if (result.outcome() == PaymentConfirmationOutcome.FAILED) {
            applyFailed(order, transaction);
            inventoryService.releaseOrderItems(order.getItems());
            persistStateChange(order, transaction, provider + " payment failed");
            log.warn("{} payment failed for order {}", provider, orderNumber);
        } else {
            paymentTransactionRepository.save(transaction);
            log.info("{} payment remains pending for order {}", provider, orderNumber);
        }

        return response(order, transaction, false);
    }

    private void applyCaptured(Order order, PaymentTransaction transaction) {
        transaction.setStatus(PaymentStatus.CAPTURED);
        transaction.setCapturedAmount(order.getTotalAmount());
        order.setPaymentStatus(PaymentStatus.CAPTURED);
        order.setPaidAt(Instant.now());
        if (order.getStatus() == OrderStatus.AWAITING_PAYMENT || order.getStatus() == OrderStatus.PENDING) {
            order.setStatus(OrderStatus.PROCESSING);
        }
    }

    private void applyFailed(Order order, PaymentTransaction transaction) {
        transaction.setStatus(PaymentStatus.FAILED);
        order.setPaymentStatus(PaymentStatus.FAILED);
        order.setCancelledAt(Instant.now());
        order.setStatus(OrderStatus.CANCELLED);
    }

    private void persistStateChange(
        Order order,
        PaymentTransaction transaction,
        String comment
    ) {
        paymentTransactionRepository.save(transaction);
        orderRepository.save(order);
        OrderStatusHistory history = OrderStatusHistory.builder()
            .order(order)
            .status(order.getStatus())
            .paymentStatus(order.getPaymentStatus())
            .comment(comment)
            .build();
        order.addStatusHistory(history);
        orderStatusHistoryRepository.save(history);
    }

    private PaymentConfirmationResponse response(
        Order order,
        PaymentTransaction transaction,
        boolean alreadyProcessed
    ) {
        return PaymentConfirmationResponse.builder()
            .orderNumber(order.getOrderNumber())
            .orderStatus(order.getStatus())
            .paymentStatus(order.getPaymentStatus())
            .transactionStatus(transaction.getStatus())
            .alreadyProcessed(alreadyProcessed)
            .build();
    }

    private void logPurchaseEvents(Order order) {
        if (order.getItems() == null || order.getItems().isEmpty()) {
            return;
        }

        order.getItems().forEach(orderItem -> {
            Product product = orderItem.getProduct();
            ProductVariant variant = orderItem.getVariant();
            if (product == null && variant != null) {
                product = variant.getProduct();
            }

            Product productRef = product;
            ProductVariant variantRef = variant;
            Integer quantity = orderItem.getQuantity();
            BigDecimal lineTotal = orderItem.getTotalAmount();
            interactionEventService.recordInteraction(
                order.getUser(),
                productRef,
                variantRef,
                InteractionType.PURCHASE,
                metadata -> {
                    Optional.ofNullable(order.getId())
                        .ifPresent(id -> metadata.put("orderId", id.toString()));
                    Optional.ofNullable(order.getOrderNumber())
                        .ifPresent(number -> metadata.put("orderNumber", number));
                    Optional.ofNullable(quantity)
                        .ifPresent(value -> metadata.put("quantity", value));
                    Optional.ofNullable(lineTotal)
                        .ifPresent(value -> metadata.put("totalAmount", value.doubleValue()));
                }
            );
        });
    }
}
