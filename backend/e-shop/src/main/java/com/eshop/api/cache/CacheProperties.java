package com.eshop.api.cache;

import java.time.Duration;

import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Getter
@Setter
@Validated
@ConfigurationProperties(prefix = "app.cache")
public class CacheProperties {

    private String namespace = "eshop";
    private Duration defaultTtl = Duration.ofMinutes(15);
}
