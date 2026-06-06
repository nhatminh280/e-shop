package com.eshop.api.chatagent.service;

import com.eshop.api.chatagent.client.ChatAgentClient;
import com.eshop.api.chatagent.dto.AgentChatRequest;
import com.eshop.api.chatagent.dto.AgentChatResponse;
import lombok.RequiredArgsConstructor;
import org.springframework.stereotype.Service;

import java.security.Principal;
import java.util.Map;

@Service
@RequiredArgsConstructor
public class ChatAgentBridgeService {

    private final ChatAgentClient chatAgentClient;

    public AgentChatResponse chat(
        AgentChatRequest request,
        Principal principal,
        String authorization,
        String traceId,
        String requestId,
        String traceparent
    ) {
        boolean authenticated = principal != null;
        String userId = authenticated ? principal.getName() : request.userId();

        AgentChatRequest enriched = new AgentChatRequest(
            request.message(),
            request.sessionId(),
            firstNonNull(request.traceId(), traceId),
            firstNonNull(request.requestId(), requestId),
            firstNonNull(request.traceparent(), traceparent),
            userId,
            authenticated,
            request.pageContext() != null ? request.pageContext() : Map.of()
        );

        return chatAgentClient.chat(enriched, authorization, traceId, requestId, traceparent);
    }

    private String firstNonNull(String primary, String fallback) {
        return primary != null ? primary : fallback;
    }
}
