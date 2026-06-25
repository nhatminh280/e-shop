package com.eshop.api.chatgateway.model;

import com.fasterxml.jackson.databind.JsonNode;
import jakarta.persistence.Column;
import jakarta.persistence.Entity;
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
@Table(name = "chat_tool_calls")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatToolCall {

    @Id
    @UuidGenerator
    @Column(name = "id", nullable = false, updatable = false)
    private UUID id;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "session_id", nullable = false)
    private ChatSession session;

    @ManyToOne(fetch = FetchType.LAZY, optional = false)
    @JoinColumn(name = "message_id", nullable = false)
    private ChatMessage message;

    @Column(name = "trace_id", length = 128)
    private String traceId;

    @Column(name = "tool_name", nullable = false, length = 120)
    private String toolName;

    @Column(name = "status", nullable = false, length = 40)
    private String status;

    @Column(name = "latency_ms")
    private BigDecimal latencyMs;

    @Column(name = "request_summary")
    private String requestSummary;

    @Column(name = "response_summary")
    private String responseSummary;

    @JdbcTypeCode(SqlTypes.JSON)
    @Column(name = "input_json")
    private JsonNode inputJson;

    @Column(name = "error_message")
    private String errorMessage;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();
}
