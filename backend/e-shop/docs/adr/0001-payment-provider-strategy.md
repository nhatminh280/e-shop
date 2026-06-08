---
status: accepted
---

# Use strategies for payment providers

Payment providers use different initialization and confirmation protocols, while order, inventory, history, and analytics effects must remain consistent. Each provider will therefore implement a payment-provider strategy that translates its external protocol into provider-neutral initiation and confirmation results, while a shared orchestration service owns persistence and commerce effects.

Provider identity is distinct from payment method and is represented by a controlled, case-insensitive value that is stored canonically. Checkout selects a provider explicitly and defaults to VNPay for compatibility; unsupported providers are rejected before checkout creates or reserves anything. Strategies are registered in a provider registry, and duplicate registrations fail application startup.

Confirmation uses a generic `/api/payments/{provider}/confirm` route, with the existing VNPay route retained as a compatibility alias. The route provider must match the provider stored on the payment transaction. Provider strategies return `CAPTURED`, `FAILED`, or `PENDING` rather than mutating orders directly.

VNPay retains its current browser-mediated confirmation behavior because enabling provider-to-server notification has an external cost. Signature and amount verification are intentionally not added at this time, accepting the resulting payment-forgery risk. The current one-payment-transaction-per-order behavior also remains: payment retries and provider switching are outside this decision.
