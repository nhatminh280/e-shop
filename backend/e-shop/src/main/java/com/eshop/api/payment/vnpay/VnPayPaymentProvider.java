package com.eshop.api.payment.vnpay;

import com.eshop.api.config.AppEnv;
import com.eshop.api.order.enums.PaymentMethod;
import com.eshop.api.order.exception.PaymentInitializationException;
import com.eshop.api.order.exception.PaymentValidationException;
import com.eshop.api.order.model.Order;
import com.eshop.api.payment.PaymentProvider;
import com.eshop.api.payment.PaymentProviderStrategy;
import com.eshop.api.payment.dto.PaymentConfirmationOutcome;
import com.eshop.api.payment.dto.PaymentConfirmationRequest;
import com.eshop.api.payment.dto.PaymentConfirmationResult;
import com.eshop.api.payment.dto.PaymentInitiationRequest;
import com.eshop.api.payment.dto.PaymentInitiationResult;
import com.eshop.api.payment.service.CurrencyConversionService;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Component;

import javax.crypto.Mac;
import javax.crypto.spec.SecretKeySpec;
import java.math.BigDecimal;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.time.Duration;
import java.time.Instant;
import java.time.ZoneId;
import java.time.format.DateTimeFormatter;
import java.util.Map;
import java.util.Objects;
import java.util.Set;
import java.util.TreeMap;

@Component
@RequiredArgsConstructor
@Slf4j
public class VnPayPaymentProvider implements PaymentProviderStrategy {

    private static final String SUCCESS_CODE = "00";
    private static final Set<String> PENDING_STATUSES = Set.of("01", "05");
    private static final DateTimeFormatter TIMESTAMP_FORMAT =
        DateTimeFormatter.ofPattern("yyyyMMddHHmmss").withZone(ZoneId.of("Asia/Ho_Chi_Minh"));

    private final AppEnv appEnv;
    private final CurrencyConversionService currencyConversionService;

    @Override
    public PaymentProvider provider() {
        return PaymentProvider.VNPAY;
    }

    @Override
    public PaymentMethod paymentMethod() {
        return PaymentMethod.CARD;
    }

    @Override
    public PaymentInitiationResult initiate(PaymentInitiationRequest request) {
        AppEnv.Payment.Vnpay config = requireVnPayConfig();
        ensureConfigValue(config.getTmnCode(), "tmn-code");
        ensureConfigValue(config.getHashSecret(), "hash-secret");
        ensureConfigValue(config.getApiUrl(), "api-url");
        ensureConfigValue(config.getReturnUrl(), "return-url");

        Order order = request.order();
        BigDecimal totalVnd = currencyConversionService.usdToVnd(order.getTotalAmount());
        String amountMinorUnit = currencyConversionService.toMinorUnitString(totalVnd);
        Instant now = Instant.now();
        Instant expiry = now.plus(Duration.ofMinutes(config.getExpireAfterMinutes()));

        Map<String, String> params = new TreeMap<>();
        params.put("vnp_Version", Objects.requireNonNullElse(config.getVersion(), "2.1.0"));
        params.put("vnp_Command", Objects.requireNonNullElse(config.getCommand(), "pay"));
        params.put("vnp_TmnCode", config.getTmnCode());
        params.put("vnp_Amount", amountMinorUnit);
        params.put("vnp_CurrCode", "VND");
        params.put("vnp_TxnRef", Objects.requireNonNullElse(
            request.transaction().getIdempotencyKey(), order.getOrderNumber()));
        params.put("vnp_OrderInfo", buildOrderInfo(config, order));
        params.put("vnp_OrderType", Objects.requireNonNullElse(config.getOrderType(), "other"));
        params.put("vnp_Locale", Objects.requireNonNullElse(config.getLocale(), "vn"));
        params.put("vnp_ReturnUrl", config.getReturnUrl());
        params.put("vnp_IpAddr", request.clientIp() == null || request.clientIp().isBlank()
            ? "0.0.0.0" : request.clientIp());
        params.put("vnp_CreateDate", TIMESTAMP_FORMAT.format(now));
        params.put("vnp_ExpireDate", TIMESTAMP_FORMAT.format(expiry));

        String queryString = buildQueryString(params, true);
        String hashData = buildQueryString(params, false);
        String secureHash = hmacSHA512(config.getHashSecret(), hashData);
        String paymentUrl = config.getApiUrl() + "?" + queryString + "&vnp_SecureHash=" + secureHash;

        return new PaymentInitiationResult(provider(), paymentMethod(), paymentUrl, expiry, totalVnd);
    }

    @Override
    public PaymentConfirmationResult confirm(PaymentConfirmationRequest request) {
        Map<String, String> payload = request.payload();
        if (payload == null || payload.isEmpty()) {
            throw new PaymentValidationException("VNPay payload is empty");
        }

        String merchantReference = payload.get("vnp_TxnRef");
        if (merchantReference == null || merchantReference.isBlank()) {
            throw new PaymentValidationException("Missing order reference in VNPay response");
        }

        String responseCode = payload.get("vnp_ResponseCode");
        String transactionStatus = payload.get("vnp_TransactionStatus");
        PaymentConfirmationOutcome outcome;
        if (SUCCESS_CODE.equals(responseCode) && SUCCESS_CODE.equals(transactionStatus)) {
            outcome = PaymentConfirmationOutcome.CAPTURED;
        } else if (PENDING_STATUSES.contains(transactionStatus)) {
            outcome = PaymentConfirmationOutcome.PENDING;
        } else {
            outcome = PaymentConfirmationOutcome.FAILED;
        }

        return new PaymentConfirmationResult(
            merchantReference,
            outcome,
            payload.get("vnp_TransactionNo"),
            Map.copyOf(payload),
            outcome == PaymentConfirmationOutcome.FAILED ? responseCode : null,
            outcome == PaymentConfirmationOutcome.FAILED ? transactionStatus : null
        );
    }

    private String buildOrderInfo(AppEnv.Payment.Vnpay config, Order order) {
        return Objects.requireNonNullElse(config.getOrderInfoPrefix(), "E-Shop Order")
            + " " + order.getOrderNumber();
    }

    private AppEnv.Payment.Vnpay requireVnPayConfig() {
        if (appEnv.getPayment() == null || appEnv.getPayment().getVnpay() == null) {
            throw new PaymentInitializationException("VNPay configuration is missing");
        }
        return appEnv.getPayment().getVnpay();
    }

    private void ensureConfigValue(String value, String name) {
        if (value == null || value.isBlank()) {
            throw new PaymentInitializationException("VNPay configuration " + name + " must be provided");
        }
    }

    private String buildQueryString(Map<String, String> params, boolean encodeKeys) {
        StringBuilder builder = new StringBuilder();
        for (Map.Entry<String, String> entry : params.entrySet()) {
            if (entry.getValue() == null || entry.getValue().isBlank()) {
                continue;
            }
            if (!builder.isEmpty()) {
                builder.append('&');
            }
            String key = encodeKeys
                ? URLEncoder.encode(entry.getKey(), StandardCharsets.US_ASCII)
                : entry.getKey();
            builder.append(key)
                .append('=')
                .append(URLEncoder.encode(entry.getValue(), StandardCharsets.US_ASCII));
        }
        return builder.toString();
    }

    private String hmacSHA512(String key, String data) {
        try {
            Mac mac = Mac.getInstance("HmacSHA512");
            mac.init(new SecretKeySpec(key.getBytes(StandardCharsets.UTF_8), "HmacSHA512"));
            byte[] rawHmac = mac.doFinal(data.getBytes(StandardCharsets.UTF_8));
            StringBuilder result = new StringBuilder(rawHmac.length * 2);
            for (byte value : rawHmac) {
                result.append(String.format("%02x", value & 0xff));
            }
            return result.toString();
        } catch (Exception exception) {
            log.error("Failed to compute VNPay HMAC", exception);
            throw new PaymentInitializationException("Failed to compute VNPay secure hash", exception);
        }
    }
}
