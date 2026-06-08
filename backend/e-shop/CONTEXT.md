# E-Shop

The e-shop context covers customer ordering, payment, catalog, and fulfillment concepts used by the commerce backend.

## Language

**Payment Provider**:
An external service that processes a payment, such as VNPay.
_Avoid_: Payment method, gateway

**Payment Method**:
The means by which a customer funds a payment, such as a card, bank transfer, or wallet.
_Avoid_: Payment provider

**Payment Confirmation Outcome**:
The provider-reported state of a payment attempt: captured, failed, or still pending.
_Avoid_: Success flag, payment status
