package com.eshop.api.cache;

import java.time.Duration;

import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.NotNull;
import lombok.Getter;
import lombok.Setter;
import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.validation.annotation.Validated;

@Getter
@Setter
@Validated
@ConfigurationProperties(prefix = "app.cache")
public class CacheProperties {

    @NotBlank
    private String namespace = "eshop";

    @NotNull
    @PositiveDuration
    private Duration defaultTtl = Duration.ofMinutes(15);
}
