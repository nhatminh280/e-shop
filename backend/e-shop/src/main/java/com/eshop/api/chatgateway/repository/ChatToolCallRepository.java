package com.eshop.api.chatgateway.repository;

import com.eshop.api.chatgateway.model.ChatToolCall;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

import java.util.Collection;
import java.util.List;
import java.util.UUID;

public interface ChatToolCallRepository extends JpaRepository<ChatToolCall, UUID> {

    List<ChatToolCall> findByMessage_IdOrderByCreatedAtAsc(UUID messageId);

    @Query("""
        select distinct toolCall.message.id
        from ChatToolCall toolCall
        where toolCall.message.id in :messageIds
          and lower(toolCall.status) in ('timeout', 'backend_error', 'validation_error')
        """)
    List<UUID> findMessageIdsWithReviewableStatuses(@Param("messageIds") Collection<UUID> messageIds);
}
