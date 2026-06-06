package com.eshop.api.chatagent.service;

import com.eshop.api.chatagent.client.ChatAgentClient;
import com.eshop.api.chatagent.dto.AgentChatRequest;
import com.eshop.api.chatagent.dto.AgentChatResponse;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.ArgumentCaptor;
import org.mockito.InjectMocks;
import org.mockito.Mock;
import org.mockito.junit.jupiter.MockitoExtension;

import java.security.Principal;
import java.util.List;
import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(MockitoExtension.class)
class ChatAgentBridgeServiceTest {

    @Mock
    private ChatAgentClient chatAgentClient;

    @InjectMocks
    private ChatAgentBridgeService service;

    @Test
    void shouldEnrichRequestWithAuthenticatedPrincipalAndTraceHeaders() {
        AgentChatResponse expected = new AgentChatResponse(
            "session-1",
            "trace-1",
            "general",
            "answer",
            "hello",
            List.of(),
            null,
            false,
            List.of(),
            List.of(),
            Map.of(),
            1.0,
            1.0,
            false,
            1.0,
            0
        );
        when(chatAgentClient.chat(any(), any(), any(), any(), any())).thenReturn(expected);

        Principal principal = () -> "customer@example.com";
        AgentChatResponse actual = service.chat(
            new AgentChatRequest("hello", "session-1", null, null, null, "client-value", false, Map.of("route", "/contact")),
            principal,
            "Bearer token",
            "trace-1",
            "request-1",
            "00-abc"
        );

        ArgumentCaptor<AgentChatRequest> requestCaptor = ArgumentCaptor.forClass(AgentChatRequest.class);
        verify(chatAgentClient).chat(requestCaptor.capture(), eq("Bearer token"), eq("trace-1"), eq("request-1"), eq("00-abc"));

        AgentChatRequest enriched = requestCaptor.getValue();
        assertThat(actual).isSameAs(expected);
        assertThat(enriched.userId()).isEqualTo("customer@example.com");
        assertThat(enriched.authenticated()).isTrue();
        assertThat(enriched.traceId()).isEqualTo("trace-1");
        assertThat(enriched.requestId()).isEqualTo("request-1");
        assertThat(enriched.traceparent()).isEqualTo("00-abc");
        assertThat(enriched.pageContext()).containsEntry("route", "/contact");
    }
}
