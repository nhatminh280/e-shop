package com.eshop.api.chatgateway.util;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;

class ChatPayloadRedactorTest {

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final ChatPayloadRedactor redactor = new ChatPayloadRedactor(objectMapper);

    @Test
    void redactsSensitiveKeysAndNestedValues() {
        var node = objectMapper.valueToTree(Map.of(
            "Authorization", "Bearer abc.def.ghi",
            "message", "email me at customer@example.com or call 0901234567",
            "nested", Map.of(
                "cardNumber", "4111111111111111",
                "traceId", "trace-123"
            )
        ));

        var redacted = redactor.redact(node);

        assertThat(redacted.get("Authorization").asText()).isEqualTo("[REDACTED]");
        assertThat(redacted.get("message").asText()).doesNotContain("customer@example.com", "0901234567");
        assertThat(redacted.get("nested").get("cardNumber").asText()).isEqualTo("[REDACTED]");
        assertThat(redacted.get("nested").get("traceId").asText()).isEqualTo("trace-123");
    }

    @Test
    void redactsStringPatternsButKeepsNonSensitiveIds() {
        String redacted = redactor.redactText(
            "token=abc123 traceId=trace-1 sessionId=session-1 order ES123 card 4111 1111 1111 1111"
        );

        assertThat(redacted).contains("token=[REDACTED]");
        assertThat(redacted).contains("traceId=trace-1");
        assertThat(redacted).contains("sessionId=session-1");
        assertThat(redacted).contains("order ES123");
        assertThat(redacted).doesNotContain("4111 1111 1111 1111");
    }

    @Test
    void redactsFullBearerAndBasicCredentialsUntilWhitespace() {
        String redacted = redactor.redactText("Bearer abc+def/ghi== Basic abc+/=");

        assertThat(redacted).contains("Bearer [REDACTED]");
        assertThat(redacted).contains("Basic [REDACTED]");
        assertThat(redacted).doesNotContain("abc+def/ghi==", "abc+/=");
    }

    @Test
    void keepsNonSensitiveKeyValuesAndTypes() throws Exception {
        var node = objectMapper.readTree("""
            {
              "tokenCount": 17,
              "total_tokens": 42,
              "emailVerified": true,
              "phoneVerified": false,
              "discardReason": "not applicable",
              "cardinality": 3
            }
            """);

        var redacted = redactor.redact(node);

        assertThat(redacted.get("tokenCount").isNumber()).isTrue();
        assertThat(redacted.get("tokenCount").asInt()).isEqualTo(17);
        assertThat(redacted.get("total_tokens").isNumber()).isTrue();
        assertThat(redacted.get("total_tokens").asInt()).isEqualTo(42);
        assertThat(redacted.get("emailVerified").isBoolean()).isTrue();
        assertThat(redacted.get("emailVerified").asBoolean()).isTrue();
        assertThat(redacted.get("phoneVerified").isBoolean()).isTrue();
        assertThat(redacted.get("phoneVerified").asBoolean()).isFalse();
        assertThat(redacted.get("discardReason").isTextual()).isTrue();
        assertThat(redacted.get("discardReason").asText()).isEqualTo("not applicable");
        assertThat(redacted.get("cardinality").isNumber()).isTrue();
        assertThat(redacted.get("cardinality").asInt()).isEqualTo(3);
    }

    @Test
    void redactsSensitiveCamelCaseAndCompoundKeys() throws Exception {
        var node = objectMapper.readTree("""
            {
              "accessToken": "access-123",
              "cardNumber": "4111111111111111",
              "x-api-key": "api-123"
            }
            """);

        var redacted = redactor.redact(node);

        assertThat(redacted.get("accessToken").asText()).isEqualTo("[REDACTED]");
        assertThat(redacted.get("cardNumber").asText()).isEqualTo("[REDACTED]");
        assertThat(redacted.get("x-api-key").asText()).isEqualTo("[REDACTED]");
    }

    @Test
    void redactsCompoundKeysContainingSensitiveTokens() throws Exception {
        var node = objectMapper.readTree("""
            {
              "authorizationHeader": "Bearer abc.def.ghi",
              "sessionToken": "session-token-123",
              "userPassword": "password-123",
              "customerEmail": "customer@example.com",
              "shippingAddress": "123 Main St",
              "paymentMethod": "card"
            }
            """);

        var redacted = redactor.redact(node);

        assertThat(redacted.get("authorizationHeader").asText()).isEqualTo("[REDACTED]");
        assertThat(redacted.get("sessionToken").asText()).isEqualTo("[REDACTED]");
        assertThat(redacted.get("userPassword").asText()).isEqualTo("[REDACTED]");
        assertThat(redacted.get("customerEmail").asText()).isEqualTo("[REDACTED]");
        assertThat(redacted.get("shippingAddress").asText()).isEqualTo("[REDACTED]");
        assertThat(redacted.get("paymentMethod").asText()).isEqualTo("[REDACTED]");
    }

    @Test
    void recursivelyRedactsArraysAndPreservesNonTextPrimitives() throws Exception {
        var node = objectMapper.readTree("""
            {
              "items": [
                {
                  "accessToken": "access-123",
                  "tokenCount": 2,
                  "enabled": true
                },
                "Bearer abc.def.ghi",
                99,
                false
              ]
            }
            """);

        var redacted = redactor.redact(node);
        var items = redacted.get("items");

        assertThat(items.get(0).get("accessToken").asText()).isEqualTo("[REDACTED]");
        assertThat(items.get(0).get("tokenCount").isNumber()).isTrue();
        assertThat(items.get(0).get("tokenCount").asInt()).isEqualTo(2);
        assertThat(items.get(0).get("enabled").isBoolean()).isTrue();
        assertThat(items.get(0).get("enabled").asBoolean()).isTrue();
        assertThat(items.get(1).asText()).isEqualTo("Bearer [REDACTED]");
        assertThat(items.get(2).isNumber()).isTrue();
        assertThat(items.get(2).asInt()).isEqualTo(99);
        assertThat(items.get(3).isBoolean()).isTrue();
        assertThat(items.get(3).asBoolean()).isFalse();
    }

    @Test
    void preservesInvalidLuhnLikeLongNumbers() {
        String value = "reference 4111111111111112 remains";

        String redacted = redactor.redactText(value);

        assertThat(redacted).isEqualTo(value);
    }

    @Test
    void keepsNullAndBlankTextValues() {
        assertThat(redactor.redactText(null)).isNull();
        assertThat(redactor.redactText("   ")).isEqualTo("   ");
    }
}
