package com.eshop.api.payment;

import com.eshop.api.exception.handler.GlobalExceptionHandler;
import com.eshop.api.order.enums.OrderStatus;
import com.eshop.api.order.enums.PaymentStatus;
import com.eshop.api.payment.dto.PaymentConfirmationResponse;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;

import static org.mockito.ArgumentMatchers.anyMap;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class PaymentControllerTest {

    @Test
    void confirmsPaymentThroughGenericCaseInsensitiveProviderRoute() throws Exception {
        PaymentOrchestrationService service = mock(PaymentOrchestrationService.class);
        when(service.confirm(org.mockito.ArgumentMatchers.eq(PaymentProvider.VNPAY), anyMap()))
            .thenReturn(PaymentConfirmationResponse.builder()
                .orderNumber("ORD-001")
                .orderStatus(OrderStatus.PROCESSING)
                .paymentStatus(PaymentStatus.CAPTURED)
                .transactionStatus(PaymentStatus.CAPTURED)
                .alreadyProcessed(false)
                .build());
        MockMvc mvc = MockMvcBuilders
            .standaloneSetup(new PaymentController(service))
            .setControllerAdvice(new GlobalExceptionHandler())
            .build();

        mvc.perform(post("/api/payments/vNpAy/confirm")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"vnp_TxnRef\":\"ORD-001\"}"))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.orderNumber").value("ORD-001"))
            .andExpect(jsonPath("$.paymentStatus").value("CAPTURED"));

        verify(service).confirm(
            org.mockito.ArgumentMatchers.eq(PaymentProvider.VNPAY),
            anyMap()
        );
    }

    @Test
    void existingVnPayConfirmationUrlRemainsCompatible() throws Exception {
        PaymentOrchestrationService service = mock(PaymentOrchestrationService.class);
        when(service.confirm(org.mockito.ArgumentMatchers.eq(PaymentProvider.VNPAY), anyMap()))
            .thenReturn(PaymentConfirmationResponse.builder()
                .orderNumber("ORD-001")
                .orderStatus(OrderStatus.AWAITING_PAYMENT)
                .paymentStatus(PaymentStatus.PENDING)
                .transactionStatus(PaymentStatus.PENDING)
                .alreadyProcessed(false)
                .build());
        MockMvc mvc = MockMvcBuilders
            .standaloneSetup(new PaymentController(service))
            .setControllerAdvice(new GlobalExceptionHandler())
            .build();

        mvc.perform(post("/api/payments/vnpay/confirm")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"vnp_TxnRef\":\"ORD-001\"}"))
            .andExpect(status().isOk());
    }

    @Test
    void rejectsUnsupportedProviderBeforeOrchestration() throws Exception {
        PaymentOrchestrationService service = mock(PaymentOrchestrationService.class);
        MockMvc mvc = MockMvcBuilders
            .standaloneSetup(new PaymentController(service))
            .setControllerAdvice(new GlobalExceptionHandler())
            .build();

        mvc.perform(post("/api/payments/stripe/confirm")
                .contentType(MediaType.APPLICATION_JSON)
                .content("{}"))
            .andExpect(status().isBadRequest())
            .andExpect(jsonPath("$.message").value("Unsupported payment provider: stripe"));

        verify(service, never()).confirm(
            org.mockito.ArgumentMatchers.any(),
            anyMap()
        );
    }
}
