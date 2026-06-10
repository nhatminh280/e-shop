# Payment Provider Strategy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a complete payment-provider strategy lifecycle while preserving VNPay's current checkout and browser-confirmation behavior.

**Architecture:** Provider strategies translate provider-specific initialization and confirmation payloads into provider-neutral results. A registry resolves strategies by canonical provider identity, while checkout and a shared orchestration service retain ownership of order, inventory, persistence, history, and analytics effects.

**Tech Stack:** Java 21, Spring Boot 3.5, Spring MVC, Spring Data JPA, JUnit 5, Mockito, AssertJ

---

### Task 1: Provider Contracts And Registry

**Files:**
- Create: `src/main/java/com/eshop/api/payment/PaymentProvider.java`
- Create: `src/main/java/com/eshop/api/payment/PaymentProviderStrategy.java`
- Create: `src/main/java/com/eshop/api/payment/PaymentProviderRegistry.java`
- Create: `src/main/java/com/eshop/api/payment/dto/PaymentInitiationRequest.java`
- Create: `src/main/java/com/eshop/api/payment/dto/PaymentInitiationResult.java`
- Create: `src/main/java/com/eshop/api/payment/dto/PaymentConfirmationRequest.java`
- Create: `src/main/java/com/eshop/api/payment/dto/PaymentConfirmationResult.java`
- Create: `src/main/java/com/eshop/api/payment/dto/PaymentConfirmationOutcome.java`
- Test: `src/test/java/com/eshop/api/payment/PaymentProviderRegistryTest.java`

- [x] Write tests proving case-insensitive parsing, VNPay selection, unsupported-provider rejection, and duplicate-registration startup failure.
- [x] Run `./mvnw -Dtest=PaymentProviderRegistryTest test` and verify the tests fail because the contracts do not exist.
- [x] Implement the provider enum, provider-neutral records, strategy interface, registry, and bad-request exception.
- [x] Re-run the focused test and verify it passes.

### Task 2: VNPay Strategy

**Files:**
- Create: `src/main/java/com/eshop/api/payment/vnpay/VnPayPaymentProvider.java`
- Delete: `src/main/java/com/eshop/api/payment/service/VnPayPaymentService.java`
- Delete: `src/main/java/com/eshop/api/payment/service/VnPayCallbackService.java`
- Delete: `src/main/java/com/eshop/api/payment/dto/VnPayInitResponse.java`
- Test: `src/test/java/com/eshop/api/payment/vnpay/VnPayPaymentProviderTest.java`

- [x] Write tests proving VNPay initializes a signed URL lazily and maps success, failure, and non-terminal payloads to `CAPTURED`, `FAILED`, and `PENDING`.
- [x] Run the focused test and verify it fails because the strategy is absent.
- [x] Move the current URL generation and payload interpretation into `VnPayPaymentProvider`, without adding callback signature or amount verification.
- [x] Re-run the focused test and verify it passes.

### Task 3: Shared Confirmation Orchestration

**Files:**
- Create: `src/main/java/com/eshop/api/payment/PaymentOrchestrationService.java`
- Create: `src/main/java/com/eshop/api/payment/dto/PaymentConfirmationResponse.java`
- Replace: `src/test/java/com/eshop/api/payment/VnPayCallbackServiceTest.java`
- Test: `src/test/java/com/eshop/api/payment/PaymentOrchestrationServiceTest.java`

- [x] Write tests for provider mismatch, idempotent terminal callbacks, and the agreed captured, failed, and pending effects.
- [x] Run the focused tests and verify they fail against the missing orchestration service.
- [x] Implement transaction locking, provider matching, state transitions, inventory/history/analytics effects, and provider-neutral responses.
- [x] Re-run the focused tests and verify they pass.

### Task 4: Checkout And HTTP Integration

**Files:**
- Modify: `src/main/java/com/eshop/api/order/dto/CheckoutRequest.java`
- Modify: `src/main/java/com/eshop/api/order/dto/CheckoutResponse.java`
- Modify: `src/main/java/com/eshop/api/order/model/PaymentTransaction.java`
- Modify: `src/main/java/com/eshop/api/order/service/OrderCheckoutService.java`
- Modify: `src/main/java/com/eshop/api/order/service/AdminPaymentTransactionService.java`
- Modify: `src/main/java/com/eshop/api/order/dto/PaymentTransactionResponse.java`
- Replace: `src/main/java/com/eshop/api/payment/vnpay/VnPayController.java`
- Test: `src/test/java/com/eshop/api/payment/PaymentControllerTest.java`

- [x] Write tests proving checkout defaults to VNPay, explicit provider input is case-insensitive, unsupported providers fail before side effects, and `/api/payments/vnpay/confirm` remains compatible through the generic route.
- [x] Run focused tests and verify they fail against the hardcoded checkout/controller.
- [x] Resolve the strategy before checkout persistence, derive payment method from the strategy, persist canonical provider identity, and expose `POST /api/payments/{provider}/confirm`.
- [x] Re-run focused tests and verify they pass.

### Task 5: Documentation And Verification

**Files:**
- Modify: `docs/orders-payments-api.md`
- Modify: `docs/adr/0001-payment-provider-strategy.md`

- [x] Document the optional checkout provider, generic confirmation route, compatibility URL, pending behavior, and intentionally unchanged VNPay validation limitations.
- [x] Run `./mvnw test` and verify zero failures.
- [x] Run `./mvnw package -DskipTests` and verify the application compiles and packages.
- [x] Review `git diff --check` and the final diff for accidental unrelated changes.
