package com.eshop.api.order.repository;

import com.eshop.api.order.enums.PaymentStatus;
import com.eshop.api.order.model.Order;
import com.eshop.api.order.model.PaymentTransaction;
import jakarta.persistence.LockModeType;
import jakarta.persistence.QueryHint;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.JpaSpecificationExecutor;
import org.springframework.data.jpa.repository.Lock;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.jpa.repository.QueryHints;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.Collection;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

@Repository
public interface PaymentTransactionRepository extends JpaRepository<PaymentTransaction, UUID>, JpaSpecificationExecutor<PaymentTransaction> {

    Optional<PaymentTransaction> findByIdempotencyKey(String idempotencyKey);

    Optional<PaymentTransaction> findTopByOrder_OrderNumberOrderByCreatedAtDesc(String orderNumber);

    @Lock(LockModeType.PESSIMISTIC_WRITE)
    @QueryHints(@QueryHint(name = "jakarta.persistence.lock.timeout", value = "5000"))
    @Query("SELECT pt FROM PaymentTransaction pt WHERE pt.order.orderNumber = :orderNumber ORDER BY pt.createdAt DESC LIMIT 1")
    Optional<PaymentTransaction> findTopByOrderNumberWithLock(@Param("orderNumber") String orderNumber);

    List<PaymentTransaction> findByOrder_OrderNumberOrderByCreatedAtDesc(String orderNumber);

    List<PaymentTransaction> findByOrderInAndStatus(Collection<Order> orders,
                                                    PaymentStatus status);

    @Query("""
        SELECT SUM(COALESCE(pt.capturedAmount, pt.amount))
        FROM PaymentTransaction pt
        WHERE pt.status = :status
          AND pt.createdAt >= :start
    """)
    BigDecimal sumCapturedAmountByStatusSince(@Param("status") PaymentStatus status,
                                              @Param("start") Instant start);

}
