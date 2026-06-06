package com.eshop.api.chatagent.config;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

import java.time.Duration;

@Configuration
@ConfigurationProperties(prefix = "chat-agent")
@Getter
@Setter
public class ChatAgentProperties {

    private String baseUrl = "http://localhost:8010";

    private boolean enabled = false;

    private Duration connectTimeout = Duration.ofSeconds(2);

    private Duration readTimeout = Duration.ofSeconds(5);
}
