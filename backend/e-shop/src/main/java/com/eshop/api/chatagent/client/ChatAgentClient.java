package com.eshop.api.chatagent.client;

import com.eshop.api.chatagent.config.ChatAgentProperties;
import com.eshop.api.chatagent.dto.AgentChatRequest;
import com.eshop.api.chatagent.dto.AgentChatResponse;
import com.eshop.api.exception.ChatAgentUnavailableException;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Qualifier;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.util.StringUtils;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.net.URI;

@Component
@Slf4j
public class ChatAgentClient {

    private final RestTemplate chatAgentRestTemplate;
    private final ChatAgentProperties properties;

    public ChatAgentClient(
        @Qualifier("chatAgentRestTemplate") RestTemplate chatAgentRestTemplate,
        ChatAgentProperties properties
    ) {
        this.chatAgentRestTemplate = chatAgentRestTemplate;
        this.properties = properties;
    }

    public AgentChatResponse chat(
        AgentChatRequest request,
        String authorization,
        String traceId,
        String requestId,
        String traceparent
    ) {
        if (!properties.isEnabled()) {
            throw new ChatAgentUnavailableException("Chat agent bridge is disabled");
        }
        if (!StringUtils.hasText(properties.getBaseUrl())) {
            throw new ChatAgentUnavailableException("Chat agent base URL is not configured");
        }

        URI uri = UriComponentsBuilder
            .fromUriString(properties.getBaseUrl())
            .pathSegment("agent", "chat")
            .build()
            .toUri();

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        copyHeader(headers, HttpHeaders.AUTHORIZATION, authorization);
        copyHeader(headers, "x-trace-id", traceId);
        copyHeader(headers, "x-request-id", requestId);
        copyHeader(headers, "traceparent", traceparent);

        try {
            ResponseEntity<AgentChatResponse> response = chatAgentRestTemplate.postForEntity(
                uri,
                new HttpEntity<>(request, headers),
                AgentChatResponse.class
            );
            if (response.getBody() == null) {
                throw new ChatAgentUnavailableException("Chat agent returned an empty response");
            }
            return response.getBody();
        } catch (ChatAgentUnavailableException ex) {
            throw ex;
        } catch (RestClientException ex) {
            log.error("Failed to call chat agent", ex);
            throw new ChatAgentUnavailableException("Unable to reach chat agent", ex);
        }
    }

    private void copyHeader(HttpHeaders headers, String name, String value) {
        if (StringUtils.hasText(value)) {
            headers.set(name, value);
        }
    }
}
