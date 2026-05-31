package com.eshop.api.chatagent.controller;

import com.eshop.api.chatagent.dto.AgentChatRequest;
import com.eshop.api.chatagent.dto.AgentChatResponse;
import com.eshop.api.chatagent.service.ChatAgentBridgeService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.HttpHeaders;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestHeader;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

import java.security.Principal;

@RestController
@RequestMapping("/api/agent")
@RequiredArgsConstructor
public class ChatAgentController {

    private final ChatAgentBridgeService chatAgentBridgeService;

    @PostMapping("/chat")
    public ResponseEntity<AgentChatResponse> chat(
        @Valid @RequestBody AgentChatRequest request,
        Principal principal,
        @RequestHeader(value = HttpHeaders.AUTHORIZATION, required = false) String authorization,
        @RequestHeader(value = "x-trace-id", required = false) String traceId,
        @RequestHeader(value = "x-request-id", required = false) String requestId,
        @RequestHeader(value = "traceparent", required = false) String traceparent
    ) {
        AgentChatResponse response = chatAgentBridgeService.chat(
            request,
            principal,
            authorization,
            traceId,
            requestId,
            traceparent
        );
        return ResponseEntity.ok(response);
    }
}
