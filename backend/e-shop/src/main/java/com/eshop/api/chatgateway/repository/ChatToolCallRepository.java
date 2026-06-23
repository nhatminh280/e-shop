package com.eshop.api.chatgateway.repository;

import com.eshop.api.chatgateway.model.ChatToolCall;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Collection;
import java.util.List;
import java.util.UUID;

public interface ChatToolCallRepository extends JpaRepository<ChatToolCall, UUID> {

    List<ChatToolCall> findByMessage_IdAndStatusIn(UUID messageId, Collection<String> statuses);
}
