package com.eshop.api.payment;

import com.eshop.api.payment.dto.PaymentConfirmationResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.util.Map;

@RestController
@RequestMapping("/api/payments")
@RequiredArgsConstructor
public class PaymentController {

    private final PaymentOrchestrationService paymentOrchestrationService;

    @PostMapping("/{provider}/confirm")
    public ResponseEntity<PaymentConfirmationResponse> confirmPayment(
        @PathVariable("provider") String provider,
        @RequestBody Map<String, String> payload
    ) {
        PaymentConfirmationResponse response = paymentOrchestrationService.confirm(
            PaymentProvider.fromValue(provider),
            payload
        );
        return ResponseEntity.ok(response);
    }
}
