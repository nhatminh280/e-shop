package com.eshop.api.chatgateway.repository;

import com.eshop.api.chatgateway.model.ChatSession;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.Optional;
import java.util.UUID;

public interface ChatSessionRepository extends JpaRepository<ChatSession, UUID> {

    Optional<ChatSession> findByIdAndUser_Id(UUID id, UUID userId);
}
