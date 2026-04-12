package com.eshop.api.cache;

import java.time.Duration;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.cache.CacheManager;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;

import static org.assertj.core.api.Assertions.assertThat;

class RedisCacheConfigTests {

    private final ApplicationContextRunner contextRunner = new ApplicationContextRunner()
            .withUserConfiguration(RedisCacheConfig.class, TestRedisConnectionConfiguration.class)
            .withPropertyValues(
                    "app.cache.namespace=eshop::benchmark",
                    "app.cache.default-ttl=30m"
            );

    @Test
    void cacheNamesExposePhaseOneCacheNames() {
        assertThat(CacheNames.phaseOneCacheNames()).containsExactly(
                CacheNames.PRODUCTS,
                CacheNames.CATEGORIES
        );
    }

    @Test
    void cachePropertiesDefaultToSafeValues() {
        CacheProperties properties = new CacheProperties();

        assertThat(properties.getNamespace()).isEqualTo("eshop");
        assertThat(properties.getDefaultTtl()).isEqualTo(Duration.ofMinutes(15));
    }

    @Test
    void contextCreatesRedisCacheManagerWithConfiguredDefaults() {
        contextRunner.run(context -> {
            assertThat(context).hasSingleBean(CacheManager.class);
            assertThat(context.getBean(CacheManager.class)).isInstanceOf(RedisCacheManager.class);
            assertThat(context.getBean(CacheProperties.class).getNamespace()).isEqualTo("eshop::benchmark");
            assertThat(context.getBean(CacheProperties.class).getDefaultTtl()).isEqualTo(Duration.ofMinutes(30));
        });
    }

    @Configuration(proxyBeanMethods = false)
    static class TestRedisConnectionConfiguration {

        @Bean
        RedisConnectionFactory redisConnectionFactory() {
            return new LettuceConnectionFactory("localhost", 6379);
        }

        @Bean
        ObjectMapper objectMapper() {
            return new ObjectMapper().findAndRegisterModules();
        }
    }
}
