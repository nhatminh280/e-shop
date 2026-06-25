package com.eshop.api.chatgateway.repository;

import com.eshop.api.chatgateway.model.ChatDraftAction;
import org.springframework.data.jpa.repository.JpaRepository;

import java.util.List;
import java.util.Optional;
import java.util.UUID;

public interface ChatDraftActionRepository extends JpaRepository<ChatDraftAction, UUID> {

    Optional<ChatDraftAction> findByIdAndUser_Id(UUID id, UUID userId);

    List<ChatDraftAction> findByMessage_IdOrderByCreatedAtAsc(UUID messageId);
}
