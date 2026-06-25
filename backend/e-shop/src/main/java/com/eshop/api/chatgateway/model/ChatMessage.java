package com.eshop.api.chatgateway.model;

import com.eshop.api.chatgateway.enums.ChatMessageRole;
import com.eshop.api.user.User;
import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.EnumType;
import jakarta.persistence.Enumerated;
import jakarta.persistence.FetchType;
import jakarta.persistence.Id;
import jakarta.persistence.JoinColumn;
import jakarta.persistence.ManyToOne;
import jakarta.persistence.Table;
import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Getter;
import lombok.NoArgsConstructor;
import lombok.Setter;
import org.hibernate.annotations.CreationTimestamp;
import org.hibernate.annotations.JdbcTypeCode;
import org.hibernate.annotations.UuidGenerator;
import org.hibernate.type.SqlTypes;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "chat_messages")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatMessage {

    @Id
    @UuidGenerator
    @Column(name = "id", nullable = false, updatable = false)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "session_id", nullable = false)
    private ChatSession session;

    @ManyToOne(fetch = FetchType.LAZY)
    @JoinColumn(name = "user_id")
    private User user;

    @Enumerated(EnumType.STRING)
    @Column(name = "role", nullable = false, length = 24)
    private ChatMessageRole role;

    @Column(name = "body", nullable = false)
    private String body;

    @Column(name = "intent", length = 80)
    private String intent;

    @Column(name = "response_type", length = 80)
    private String responseType;

    @Column(name = "trace_id", length = 128)
    private String traceId;

    @Column(name = "latency_ms")
    private BigDecimal latencyMs;

    @Column(name = "fallback_count", nullable = false)
    @Builder.Default
    private Integer fallbackCount = 0;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "payload_json")
    private JsonNode payloadJson;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();
}
