package com.eshop.api.chatgateway.model;

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
import org.hibernate.annotations.UuidGenerator;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.UUID;

@Entity
@Table(name = "chat_node_traces")
@Getter
@Setter
@Builder
@NoArgsConstructor
@AllArgsConstructor
public class ChatNodeTrace {

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

    @Column(name = "node_name", nullable = false, length = 120)
    private String nodeName;

    @Column(name = "intent", length = 80)
    private String intent;

    @Column(name = "status", nullable = false, length = 40)
    private String status;

    @Column(name = "latency_ms")
    private BigDecimal latencyMs;

    @Column(name = "intent_confidence")
    private BigDecimal intentConfidence;

    @Column(name = "routing_confidence")
    private BigDecimal routingConfidence;

    @Column(name = "input_summary")
    private String inputSummary;

    @Column(name = "output_summary")
    private String outputSummary;

    @Column(name = "error_message")
    private String errorMessage;

    @CreationTimestamp
    @Column(name = "created_at", nullable = false, updatable = false)
    @Builder.Default
    private Instant createdAt = Instant.now();
}
