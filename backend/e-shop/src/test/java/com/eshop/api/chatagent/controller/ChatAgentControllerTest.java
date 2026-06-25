package com.eshop.api.chatagent.controller;

import com.eshop.api.chatagent.dto.AgentChatRequest;
import com.eshop.api.chatagent.dto.AgentChatResponse;
import com.eshop.api.chatagent.service.ChatAgentBridgeService;
import com.eshop.api.exception.ChatAgentUnavailableException;
import com.eshop.api.exception.handler.GlobalExceptionHandler;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.MockMvc;
import org.springframework.test.web.servlet.setup.MockMvcBuilders;
import org.springframework.validation.beanvalidation.LocalValidatorFactoryBean;

import java.security.Principal;
import java.util.List;
import java.util.Map;

import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.post;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

class ChatAgentControllerTest {

    private ChatAgentBridgeService chatAgentBridgeService;
    private MockMvc mockMvc;
    private ObjectMapper objectMapper;

    @BeforeEach
    void setUp() {
        chatAgentBridgeService = mock(ChatAgentBridgeService.class);
        LocalValidatorFactoryBean validator = new LocalValidatorFactoryBean();
        validator.afterPropertiesSet();
        mockMvc = MockMvcBuilders
            .standaloneSetup(new ChatAgentController(chatAgentBridgeService))
            .setControllerAdvice(new GlobalExceptionHandler())
            .setValidator(validator)
            .build();
        objectMapper = new ObjectMapper();
    }

    @Test
    void shouldReturnAgentResponse() throws Exception {
        when(chatAgentBridgeService.chat(any(), any(Principal.class), eq("Bearer token"), eq("trace-1"), eq("request-1"), eq("00-abc")))
            .thenReturn(new AgentChatResponse(
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
                List.of(),
                1.0,
                1.0,
                false,
                1.0,
                0
            ));

        mockMvc.perform(post("/api/agent/chat")
                .principal(() -> "customer@example.com")
                .header("Authorization", "Bearer token")
                .header("x-trace-id", "trace-1")
                .header("x-request-id", "request-1")
                .header("traceparent", "00-abc")
                .contentType(MediaType.APPLICATION_JSON)
                .content(objectMapper.writeValueAsString(new AgentChatRequest(
                    "hello",
                    "session-1",
                    null,
                    null,
                    null,
                    null,
                    null,
                    Map.of()
                ))))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.sessionId").value("session-1"))
            .andExpect(jsonPath("$.responseType").value("answer"))
            .andExpect(jsonPath("$.answer").value("hello"));
    }

    @Test
    void shouldRejectBlankMessage() throws Exception {
        mockMvc.perform(post("/api/agent/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {
                      "message": " ",
                      "sessionId": "session-1"
                    }
                    """))
            .andExpect(status().isBadRequest());
    }

    @Test
    void shouldRejectBlankSessionId() throws Exception {
        mockMvc.perform(post("/api/agent/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {
                      "message": "hello",
                      "sessionId": " "
                    }
                    """))
            .andExpect(status().isBadRequest());
    }

    @Test
    void shouldReturnUnavailableWhenBridgeDisabled() throws Exception {
        when(chatAgentBridgeService.chat(any(), any(), any(), any(), any(), any()))
            .thenThrow(new ChatAgentUnavailableException("Chat agent bridge is disabled"));

        mockMvc.perform(post("/api/agent/chat")
                .contentType(MediaType.APPLICATION_JSON)
                .content("""
                    {
                      "message": "hello",
                      "sessionId": "session-1"
                    }
                    """))
            .andExpect(status().isServiceUnavailable())
            .andExpect(jsonPath("$.message").value("Chat agent bridge is disabled"));
    }
}
