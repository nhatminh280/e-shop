package com.eshop.api.chatgateway.repository;

import com.eshop.api.chatgateway.model.ChatMessage;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.UUID;

public interface ChatMessageRepository extends JpaRepository<ChatMessage, UUID> {

    Page<ChatMessage> findBySession_IdOrderByCreatedAtAsc(UUID sessionId, Pageable pageable);
}
