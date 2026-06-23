package com.eshop.api.chatgateway.repository;

import com.eshop.api.chatgateway.model.ChatMessage;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;

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

    @Query("""
        select message
        from ChatMessage message
        where message.role = com.eshop.api.chatgateway.enums.ChatMessageRole.ASSISTANT
          and (:sessionId is null or message.session.id = :sessionId)
          and (:responseType is null or lower(coalesce(message.responseType, '')) = :responseType)
          and (
            :hasFallback is null
            or (:hasFallback = true and message.fallbackCount > 0)
            or (:hasFallback = false and coalesce(message.fallbackCount, 0) = 0)
          )
          and (
            message.fallbackCount > 0
            or lower(coalesce(message.responseType, '')) in ('tool_error', 'fallback')
            or exists (
                select reviewToolCall.id
                from ChatToolCall reviewToolCall
                where reviewToolCall.message = message
                  and lower(reviewToolCall.status) in ('timeout', 'backend_error', 'validation_error')
            )
          )
          and (
            :toolStatus is null
            or exists (
                select filteredToolCall.id
                from ChatToolCall filteredToolCall
                where filteredToolCall.message = message
                  and lower(filteredToolCall.status) = :toolStatus
            )
          )
        order by message.createdAt desc
        """)
    Page<ChatMessage> findReviewCandidatesFiltered(
        @Param("sessionId") UUID sessionId,
        @Param("responseType") String responseType,
        @Param("hasFallback") Boolean hasFallback,
        @Param("toolStatus") String toolStatus,
        Pageable pageable
    );
}
