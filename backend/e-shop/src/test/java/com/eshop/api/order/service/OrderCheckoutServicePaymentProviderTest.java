package com.eshop.api.order.service;

import com.eshop.api.cart.repository.CartRepository;
import com.eshop.api.order.dto.CheckoutRequest;
import com.eshop.api.order.repository.AddressRepository;
import com.eshop.api.order.repository.OrderAddressRepository;
import com.eshop.api.order.repository.OrderRepository;
import com.eshop.api.order.repository.OrderStatusHistoryRepository;
import com.eshop.api.order.repository.PaymentTransactionRepository;
import com.eshop.api.payment.PaymentProviderRegistry;
import com.eshop.api.payment.exception.UnsupportedPaymentProviderException;
import com.eshop.api.user.UserRepository;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.List;

import static org.assertj.core.api.Assertions.assertThatThrownBy;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;

class OrderCheckoutServicePaymentProviderTest {

    @Test
    void rejectsUnavailableProviderBeforeReadingOrPersistingCheckoutData() {
        UserRepository userRepository = mock(UserRepository.class);
        OrderRepository orderRepository = mock(OrderRepository.class);
        OrderCheckoutService service = new OrderCheckoutService(
            userRepository,
            mock(CartRepository.class),
            mock(AddressRepository.class),
            orderRepository,
            mock(OrderAddressRepository.class),
            mock(OrderStatusHistoryRepository.class),
            mock(PaymentTransactionRepository.class),
            new PaymentProviderRegistry(List.of()),
            mock(InventoryService.class),
            new ObjectMapper()
        );

        assertThatThrownBy(() -> service.checkout(
            "customer@example.com",
            new CheckoutRequest(),
            "127.0.0.1"
        )).isInstanceOf(UnsupportedPaymentProviderException.class);

        verify(userRepository, never()).findByEmailIgnoreCase(org.mockito.ArgumentMatchers.anyString());
        verify(orderRepository, never()).save(org.mockito.ArgumentMatchers.any());
    }
}
