package com.eshop.api.cache;

import java.time.Duration;
import java.time.LocalDateTime;
import java.util.List;

import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.runner.ApplicationContextRunner;
import org.springframework.cache.CacheManager;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.connection.lettuce.LettuceConnectionFactory;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.serializer.RedisSerializer;

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
                CacheNames.ALL_CATEGORIES,
                CacheNames.COMMON_CATEGORIES,
                CacheNames.CATEGORY_BY_SLUG,
                CacheNames.PUBLIC_PRODUCTS,
                CacheNames.PRODUCT_BY_SLUG
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
            assertThat(context.getBean(RedisCacheConfiguration.class).getTtl()).isEqualTo(Duration.ofMinutes(30));
            assertThat(context.getBean(RedisCacheConfiguration.class).getKeyPrefixFor(CacheNames.ALL_CATEGORIES))
                    .isEqualTo("eshop::benchmark::catalog:categories:all::");
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

    @Test
    void serializerRoundTripsTypedCollectionsWithJavaTimeFields() {
        contextRunner.run(context -> {
            @SuppressWarnings("unchecked")
            RedisSerializer<Object> serializer = (RedisSerializer<Object>) context.getBean(RedisSerializer.class);
            CatalogPayload original = new CatalogPayload(
                    List.of(new CatalogEntry("coat", LocalDateTime.of(2026, 4, 12, 10, 30))),
                    LocalDateTime.of(2026, 4, 12, 10, 30)
            );

            byte[] serialized = serializer.serialize(original);
            Object deserialized = serializer.deserialize(serialized);

            assertThat(deserialized).isInstanceOf(CatalogPayload.class);
            CatalogPayload payload = (CatalogPayload) deserialized;
            assertThat(payload.generatedAt()).isEqualTo(LocalDateTime.of(2026, 4, 12, 10, 30));
            assertThat(payload.items()).hasSize(1);
            assertThat(payload.items().getFirst()).isInstanceOf(CatalogEntry.class);
            assertThat(payload.items().getFirst().updatedAt())
                    .isEqualTo(LocalDateTime.of(2026, 4, 12, 10, 30));
        });
    }

    @Test
    void blankNamespaceIsRejectedAtBindTime() {
        new ApplicationContextRunner()
                .withUserConfiguration(RedisCacheConfig.class, TestRedisConnectionConfiguration.class)
                .withPropertyValues("app.cache.namespace=", "app.cache.default-ttl=15m")
                .run(context -> {
                    assertThat(context).hasFailed();
                    assertThat(rootCause(context.getStartupFailure())).hasMessageContaining("field 'namespace'");
                });
    }

    @Test
    void nonPositiveTtlIsRejectedAtBindTime() {
        new ApplicationContextRunner()
                .withUserConfiguration(RedisCacheConfig.class, TestRedisConnectionConfiguration.class)
                .withPropertyValues("app.cache.namespace=eshop", "app.cache.default-ttl=0s")
                .run(context -> {
                    assertThat(context).hasFailed();
                    assertThat(rootCause(context.getStartupFailure())).hasMessageContaining("field 'defaultTtl'");
                });
    }

    record CatalogEntry(String name, LocalDateTime updatedAt) {
    }

    record CatalogPayload(List<CatalogEntry> items, LocalDateTime generatedAt) {
    }

    private static Throwable rootCause(Throwable throwable) {
        Throwable current = throwable;
        while (current != null && current.getCause() != null) {
            current = current.getCause();
        }
        return current;
    }
}
