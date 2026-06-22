package com.eshop.api.chatgateway.controller;

import com.eshop.api.chatagent.dto.AgentChatResponse;
import com.eshop.api.chatgateway.dto.ChatActionResultResponse;
import com.eshop.api.chatgateway.dto.ChatContextResponse;
import com.eshop.api.chatgateway.dto.ChatHistoryResponse;
import com.eshop.api.chatgateway.dto.ChatMessageRequest;
import com.eshop.api.chatgateway.service.ChatGatewayService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import java.security.Principal;
import java.util.UUID;

@RestController
@RequestMapping("/api/chat")
@RequiredArgsConstructor
public class ChatGatewayController {

    private final ChatGatewayService chatGatewayService;

    @PostMapping("/messages")
    public ResponseEntity<AgentChatResponse> sendMessage(
        @Valid @RequestBody ChatMessageRequest request,
        Principal principal,
        @RequestHeader(value = HttpHeaders.AUTHORIZATION, required = false) String authorization,
        @RequestHeader(value = "x-trace-id", required = false) String traceId,
        @RequestHeader(value = "x-request-id", required = false) String requestId,
        @RequestHeader(value = "traceparent", required = false) String traceparent
    ) {
        AgentChatResponse response = chatGatewayService.sendMessage(
            request,
            principal,
            authorization,
            traceId,
            requestId,
            traceparent
        );
        return ResponseEntity.ok(response);
    }

    @PostMapping("/actions/{draftActionId}/confirm")
    public ResponseEntity<ChatActionResultResponse> confirmAction(
        @PathVariable UUID draftActionId,
        Principal principal
    ) {
        return ResponseEntity.ok(chatGatewayService.confirmAction(draftActionId, principal));
    }

    @PostMapping("/actions/{draftActionId}/cancel")
    public ResponseEntity<ChatActionResultResponse> cancelAction(
        @PathVariable UUID draftActionId,
        Principal principal
    ) {
        return ResponseEntity.ok(chatGatewayService.cancelAction(draftActionId, principal));
    }

    @GetMapping("/sessions/{sessionId}/messages")
    public ResponseEntity<ChatHistoryResponse> getHistory(
        @PathVariable UUID sessionId,
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "50") int size,
        Principal principal
    ) {
        return ResponseEntity.ok(chatGatewayService.getHistory(sessionId, page, size, principal));
    }

    @GetMapping("/context")
    public ResponseEntity<ChatContextResponse> getContext(
        Principal principal,
        @RequestParam(value = "locale", required = false) String locale
    ) {
        return ResponseEntity.ok(chatGatewayService.getContext(principal, locale));
    }
}
