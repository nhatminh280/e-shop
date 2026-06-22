package com.eshop.api.chatgateway.util;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.fasterxml.jackson.databind.node.TextNode;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Component;

import java.util.Iterator;
import java.util.Locale;
import java.util.Map;
import java.util.Set;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

@Component
@RequiredArgsConstructor
public class ChatPayloadRedactor {

    public static final String REDACTED = "[REDACTED]";

    private static final Set<String> SENSITIVE_KEY_NAMES = Set.of(
        "authorization", "password", "secret", "jwt", "cookie", "email", "phone", "address",
        "payment", "card", "cvv", "cvc", "token"
    );
    private static final Set<String> SENSITIVE_COMPOUND_KEY_NAMES = Set.of(
        "access_token", "refresh_token", "id_token", "api_key", "x_api_key", "card_number",
        "client_secret", "bank_account", "set_cookie"
    );
    private static final Set<String> NON_SENSITIVE_KEY_NAMES = Set.of(
        "token_count", "total_tokens", "email_verified", "phone_verified", "discard_reason", "cardinality"
    );
    private static final Pattern BEARER = Pattern.compile("(?i)Bearer\\s+[^\\s]+");
    private static final Pattern BASIC = Pattern.compile("(?i)Basic\\s+[^\\s]+");
    private static final Pattern JWT = Pattern.compile("\\beyJ[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\.[A-Za-z0-9_-]+\\b");
    private static final Pattern TOKEN_PARAM = Pattern.compile("(?i)\\b(access_token|api_key|apikey|auth|client_secret|id_token|jwt|refresh_token|secret|token)=([^&\\s]+)");
    private static final Pattern EMAIL = Pattern.compile("[\\w.+-]+@[\\w.-]+\\.[A-Za-z]{2,}");
    private static final Pattern VIETNAM_PHONE = Pattern.compile("\\b(?:\\+?84|0)\\d(?:[\\s.-]?\\d){7,9}\\b");
    private static final Pattern CARD_CANDIDATE = Pattern.compile("\\b(?:\\d[ -]?){13,19}\\b");

    private final ObjectMapper objectMapper;

    public JsonNode redact(JsonNode node) {
        if (node == null || node.isNull()) {
            return node;
        }
        if (node.isObject()) {
            ObjectNode copy = objectMapper.createObjectNode();
            Iterator<Map.Entry<String, JsonNode>> fields = node.fields();
            while (fields.hasNext()) {
                Map.Entry<String, JsonNode> field = fields.next();
                JsonNode value = isSensitiveKey(field.getKey()) ? TextNode.valueOf(REDACTED) : redact(field.getValue());
                copy.set(field.getKey(), value);
            }
            return copy;
        }
        if (node.isArray()) {
            ArrayNode copy = objectMapper.createArrayNode();
            node.forEach(item -> copy.add(redact(item)));
            return copy;
        }
        if (node.isTextual()) {
            return TextNode.valueOf(redactText(node.asText()));
        }
        return node;
    }

    public String redactText(String value) {
        if (value == null || value.isBlank()) {
            return value;
        }
        String redacted = BEARER.matcher(value).replaceAll("Bearer " + REDACTED);
        redacted = BASIC.matcher(redacted).replaceAll("Basic " + REDACTED);
        redacted = JWT.matcher(redacted).replaceAll(REDACTED);
        redacted = TOKEN_PARAM.matcher(redacted).replaceAll("$1=" + REDACTED);
        redacted = EMAIL.matcher(redacted).replaceAll(REDACTED);
        redacted = VIETNAM_PHONE.matcher(redacted).replaceAll(REDACTED);
        return redactCardNumbers(redacted);
    }

    private boolean isSensitiveKey(String key) {
        String normalized = normalizeKey(key);
        if (NON_SENSITIVE_KEY_NAMES.contains(normalized)) {
            return false;
        }
        if (SENSITIVE_COMPOUND_KEY_NAMES.contains(normalized)) {
            return true;
        }
        String[] tokens = normalized.split("_+");
        for (String token : tokens) {
            if (SENSITIVE_KEY_NAMES.contains(token)) {
                return true;
            }
        }
        return false;
    }

    private String normalizeKey(String key) {
        return key
            .replaceAll("([a-z0-9])([A-Z])", "$1_$2")
            .replaceAll("([A-Z]+)([A-Z][a-z])", "$1_$2")
            .replaceAll("[^A-Za-z0-9]+", "_")
            .replaceAll("_+", "_")
            .replaceAll("^_|_$", "")
            .toLowerCase(Locale.ROOT);
    }

    private String redactCardNumbers(String value) {
        Matcher matcher = CARD_CANDIDATE.matcher(value);
        StringBuffer buffer = new StringBuffer();
        while (matcher.find()) {
            String candidate = matcher.group();
            String digits = candidate.replaceAll("\\D", "");
            String replacement = passesLuhn(digits) ? REDACTED : candidate;
            matcher.appendReplacement(buffer, Matcher.quoteReplacement(replacement));
        }
        matcher.appendTail(buffer);
        return buffer.toString();
    }

    private boolean passesLuhn(String digits) {
        if (digits.length() < 13 || digits.length() > 19) {
            return false;
        }
        int sum = 0;
        boolean doubleDigit = false;
        for (int index = digits.length() - 1; index >= 0; index--) {
            int value = Character.digit(digits.charAt(index), 10);
            if (doubleDigit) {
                value *= 2;
                if (value > 9) {
                    value -= 9;
                }
            }
            sum += value;
            doubleDigit = !doubleDigit;
        }
        return sum % 10 == 0;
    }
}
