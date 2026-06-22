package com.eshop.api.chatgateway.repository;

import com.eshop.api.chatgateway.model.ChatToolCall;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface ChatToolCallRepository extends JpaRepository<ChatToolCall, UUID> {
}
