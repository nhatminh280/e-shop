# Payment Confirmation Concurrency Fix

React StrictMode double-mounts components in development, causing `PaymentResult` to call `POST /api/payments/vnpay/confirm` twice for the same order nearly simultaneously. `VnPayCallbackService.handleReturn()` has an idempotency guard (check if transaction is already CAPTURED/FAILED before processing), but there is a **TOCTOU race window**: both requests can read the transaction as `PENDING` before either one commits, so both proceed through the full success path — potentially double-deducting inventory, double-logging analytics events, and producing inconsistent state.

The fix is **pessimistic locking** on the `PaymentTransaction` row. The first request acquires a `SELECT … FOR UPDATE` lock on the row; the second blocks at the DB level until the first commits, then re-reads the row, finds `CAPTURED`, and exits through the existing idempotency guard.

## Proposed Changes

### Payment — Repository layer

#### [MODIFY] PaymentTransactionRepository.java
- Add a new locked query method:
  ```java
  @Lock(LockModeType.PESSIMISTIC_WRITE)
  @QueryHints(@QueryHint(name = "jakarta.persistence.lock.timeout", value = "5000"))
  @Query("SELECT pt FROM PaymentTransaction pt WHERE pt.order.orderNumber = :orderNumber ORDER BY pt.createdAt DESC LIMIT 1")
  Optional<PaymentTransaction> findTopByOrderNumberWithLock(@Param("orderNumber") String orderNumber);
  ```
- The `@Lock` annotation translates to `SELECT … FOR UPDATE` at the DB level (PostgreSQL).
- The 5-second lock timeout prevents indefinite blocking and causes an exception if the lock cannot be acquired in time.

### Payment — Service layer

#### [MODIFY] VnPayCallbackService.java
- Replace the existing `paymentTransactionRepository.findTopByOrder_OrderNumberOrderByCreatedAtDesc(orderNumber)` call with the new locked query `findTopByOrderNumberWithLock(orderNumber)`.
- No other logic changes needed — the existing `alreadyCaptured || alreadyFailed` guard already handles the idempotent return correctly once the race window is closed.

## Verification Plan

### Automated Tests

**New unit test** — `VnPayCallbackServiceConcurrencyTest` (Mockito-based, no DB):

Purpose: Verify that when `handleReturn()` is called concurrently and the first call flips the transaction to `CAPTURED`, the second call exits via the idempotency guard and does not invoke `applySuccess`, inventory clear, analytics, etc.

Run with:
```bash
cd /home/finnzxje/repos/e-shop/cache/backend/e-shop
./mvnw test -Dtest=VnPayCallbackServiceConcurrencyTest -pl .
```

### Manual Verification

1. Start the backend locally.
2. In a REST client (e.g. Postman), send `POST /api/payments/vnpay/confirm` twice simultaneously (use two tabs or a collection runner with zero delay) with a valid VNPay success payload for the same order.
3. Check the DB: the `payment_transactions` table should have exactly one row with status `CAPTURED`.
4. Check the DB: the `order_status_history` table should have exactly one new `PROCESSING` history entry for that order.
5. Confirm the `orders` table shows the order status as `PROCESSING` and `payment_status` as `CAPTURED` (not duplicated/corrupted).
