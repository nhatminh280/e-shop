package com.eshop.api.chatagent.client;

import com.eshop.api.chatagent.config.ChatAgentProperties;
import com.eshop.api.chatagent.dto.AgentChatRequest;
import com.eshop.api.chatagent.dto.AgentChatResponse;
import com.eshop.api.exception.ChatAgentUnavailableException;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.client.MockRestServiceServer;
import org.springframework.web.client.RestTemplate;

import java.util.Map;

import static org.assertj.core.api.Assertions.assertThat;
import static org.junit.jupiter.api.Assertions.assertThrows;
import static org.springframework.http.HttpMethod.POST;
import static org.springframework.test.web.client.ExpectedCount.once;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.header;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.jsonPath;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.method;
import static org.springframework.test.web.client.match.MockRestRequestMatchers.requestTo;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withServerError;
import static org.springframework.test.web.client.response.MockRestResponseCreators.withSuccess;

class ChatAgentClientTest {

    private RestTemplate restTemplate;
    private MockRestServiceServer server;
    private ChatAgentProperties properties;
    private ChatAgentClient client;

    @BeforeEach
    void setUp() {
        restTemplate = new RestTemplate();
        server = MockRestServiceServer.bindTo(restTemplate).build();
        properties = new ChatAgentProperties();
        properties.setBaseUrl("http://agent.local");
        properties.setEnabled(true);
        client = new ChatAgentClient(restTemplate, properties);
    }

    @Test
    void shouldForwardChatRequestAndHeaders() {
        server.expect(once(), requestTo("http://agent.local/agent/chat"))
            .andExpect(method(POST))
            .andExpect(header("Authorization", "Bearer token"))
            .andExpect(header("x-trace-id", "trace-1"))
            .andExpect(header("x-request-id", "request-1"))
            .andExpect(header("traceparent", "00-abc"))
            .andExpect(jsonPath("$.message").value("find jacket"))
            .andExpect(jsonPath("$.sessionId").value("session-1"))
            .andRespond(withSuccess("""
                {
                  "sessionId": "session-1",
                  "traceId": "trace-1",
                  "intent": "product_search",
                  "responseType": "product_results",
                  "answer": "I found matching products.",
                  "productCards": [],
                  "draftAction": null,
                  "needsConfirmation": false,
                  "toolCalls": [],
                  "nodeTraces": [],
                  "slots": {},
                  "intentConfidence": 0.8,
                  "routingConfidence": 0.9,
                  "needsReview": false,
                  "latencyMs": 12.0,
                  "fallbackCount": 0
                }
                """, MediaType.APPLICATION_JSON));

        AgentChatResponse response = client.chat(
            new AgentChatRequest("find jacket", "session-1", null, null, null, null, false, Map.of()),
            "Bearer token",
            "trace-1",
            "request-1",
            "00-abc"
        );

        assertThat(response.responseType()).isEqualTo("product_results");
        assertThat(response.answer()).isEqualTo("I found matching products.");
        server.verify();
    }

    @Test
    void shouldMapUpstreamFailureToUnavailableException() {
        server.expect(once(), requestTo("http://agent.local/agent/chat"))
            .andRespond(withServerError());

        assertThrows(ChatAgentUnavailableException.class, () -> client.chat(
            new AgentChatRequest("hello", "session-1", null, null, null, null, false, Map.of()),
            null,
            null,
            null,
            null
        ));
        server.verify();
    }

    @Test
    void shouldNotCallUpstreamWhenDisabled() {
        properties.setEnabled(false);

        assertThrows(ChatAgentUnavailableException.class, () -> client.chat(
            new AgentChatRequest("hello", "session-1", null, null, null, null, false, Map.of()),
            null,
            null,
            null,
            null
        ));
        server.verify();
    }
}
