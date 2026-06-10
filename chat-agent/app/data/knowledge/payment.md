---
sourceId: payment
sourceType: payment
title: Payment Methods and Policy
locale: en-US
---

# Payment Methods and Policy

This document describes the payment methods we accept, the order payment lifecycle, the currencies we support, and how to handle common payment issues. It applies to all online orders and gift card purchases.

## Accepted Payment Methods

We accept the following payment methods on the storefront. The methods available at checkout depend on your billing country, the items in your cart, and current processor status.

- **Credit and debit cards.** Visa, Mastercard, JCB, and American Express.
- **Domestic ATM cards.** All Vietnamese banks supported by NAPAS.
- **E-wallets.** Momo, ZaloPay, and VNPay.
- **Bank transfer.** Direct transfer to our designated VPBank account.
- **Cash on delivery (COD).** Available for domestic orders under 5,000,000 VND.
- **Gift cards and store credit.** Issued by us as part of returns or promotions.

We do not accept cheques, money orders, or cryptocurrency. International credit cards are accepted on the storefront but may be subject to additional verification by the issuing bank.

## Currency

All prices on the storefront are displayed and charged in Vietnamese Dong (VND). Card payments using non-VND issuers are converted to VND by the card network at the time of authorization. The exchange rate and any foreign transaction fee are set by the card issuer and not by us.

## Payment Status Lifecycle

Each order moves through a defined payment status. The status is visible on the order details page and used by support during follow-up.

- **PENDING.** Order is created. Payment is awaiting authorization or transfer.
- **AUTHORIZED.** Card or wallet has authorized the charge. Funds are reserved but not captured.
- **PAID.** Payment is captured. Order moves to fulfillment.
- **FAILED.** Authorization or capture failed. Order is held for 24 hours, then cancelled if not retried.
- **REFUNDED.** Payment has been fully refunded after a return or cancellation.
- **PARTIAL_REFUND.** A portion of the payment has been refunded. The remainder is retained.

For COD orders, the status moves to `PAID` only after the carrier confirms cash collection on delivery.

## Authorization and Capture

For card and wallet payments, we authorize at checkout and capture at the time of shipment. If your order ships in multiple parcels, we capture the corresponding amount when each parcel ships.

If a partial capture is not supported by your card issuer, we capture the full order amount on the first parcel shipment. Items that are subsequently cancelled before shipment are refunded automatically.

## Bank Transfer Orders

If you choose bank transfer, the order is created in `PENDING` status. Transfer details and a unique reference code appear on the order confirmation page and in the confirmation email. Use the reference code in the transfer description.

We reconcile incoming transfers within 1 business day. Once the transfer is matched, the order status moves to `PAID` and fulfillment starts. Orders unmatched after 3 business days are cancelled and any received funds are returned to the sender.

## Cash on Delivery

COD orders are confirmed by phone before shipment. We may decline COD for any of the following reasons:

- The cart total exceeds 5,000,000 VND.
- The destination is outside our COD service area.
- The customer has declined two or more recent COD deliveries.

You can convert a COD order to prepaid through the order details page before the order ships. Prepaid orders ship faster because they skip the phone confirmation step.

## Failed Payments

If your payment fails, the order remains in `PENDING` for 24 hours. You can retry payment from the order details page using the same or a different method. After 24 hours without a successful retry, the order is cancelled automatically and any reserved stock is released.

Common reasons for failure include:

- Insufficient funds or daily card limit reached.
- Card blocked for online or international transactions.
- 3-D Secure authentication declined.
- Wallet session expired before confirmation.

If you are unsure why a payment failed, contact your bank first. We do not receive the specific decline reason from the issuer.

## Refunds

Refunds are processed back to the original payment method. Refund timing depends on the method:

- **Cards.** 5 to 10 business days after we initiate the refund.
- **E-wallets.** 1 to 3 business days.
- **Bank transfer.** 3 to 5 business days.
- **COD.** Refunded by bank transfer to an account you provide.
- **Gift card.** Returned to the gift card balance immediately.

We send an email when a refund is initiated and another when it is fully processed. The order details page reflects refund status in real time.

## Fraud Prevention

To protect your account, we may decline or pause an order for additional verification if it triggers our fraud signals. Examples include a billing address that does not match the issuing bank record, repeated failed authorizations, or rapid orders from new accounts.

If we pause your order, we contact you within one business day with the verification steps. If we cannot reach you within 72 hours, the order is cancelled and the authorization is released.

## Receipts and Invoices

A digital receipt is emailed when payment is confirmed. To request a tax invoice for your order, sign in, open the order, and select Request Invoice. Provide your tax ID and registered company name. Invoices are issued within 3 business days.

## Questions

For payment questions, contact support through the help center, include your order number, and select the Payments category. Sensitive details such as full card numbers should never be shared in chat or email.
