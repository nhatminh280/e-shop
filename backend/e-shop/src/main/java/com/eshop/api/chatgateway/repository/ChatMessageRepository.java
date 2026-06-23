package com.eshop.api.chatgateway.repository;

import com.eshop.api.chatgateway.model.ChatMessage;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;

import java.util.UUID;

public interface ChatMessageRepository extends JpaRepository<ChatMessage, UUID> {

    Page<ChatMessage> findBySession_IdOrderByCreatedAtAsc(UUID sessionId, Pageable pageable);

    @Query("""
        select message
        from ChatMessage message
        where message.role = com.eshop.api.chatgateway.enums.ChatMessageRole.ASSISTANT
          and (
            message.fallbackCount > 0
            or lower(coalesce(message.responseType, '')) in ('tool_error', 'fallback')
            or exists (
                select toolCall.id
                from ChatToolCall toolCall
                where toolCall.message = message
                  and lower(toolCall.status) in ('timeout', 'backend_error', 'validation_error')
            )
          )
        order by message.createdAt desc
        """)
    Page<ChatMessage> findReviewCandidates(Pageable pageable);
}
