package com.eshop.api.cache;

import com.eshop.api.catalog.dto.CategoryResponse;
import com.eshop.api.catalog.dto.CategorySummary;
import com.eshop.api.catalog.dto.PageResponse;
import com.eshop.api.catalog.dto.ProductResponse;
import com.eshop.api.catalog.dto.ProductSummaryResponse;
import com.eshop.api.catalog.enums.Gender;
import com.eshop.api.catalog.enums.ProductStatus;
import java.util.ArrayList;
import java.time.Duration;
import java.time.Instant;
import java.time.LocalDateTime;
import java.util.List;
import java.util.UUID;

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
                    .isEqualTo("eshop::benchmark::v5::catalog:categories:all::");
            assertThat(context.getBean(RedisCacheManager.class).getCacheNames())
                    .containsExactlyInAnyOrderElementsOf(CacheNames.phaseOneCacheNames());
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
    void serializerRoundTripsCategoryResponseList() {
        contextRunner.run(context -> {
            @SuppressWarnings("unchecked")
            RedisSerializer<Object> serializer = (RedisSerializer<Object>) context.getBean(RedisSerializer.class);
            List<CategoryResponse> original = new ArrayList<>(List.of(
                    CategoryResponse.builder()
                            .id(1)
                            .name("Women")
                            .slug("women")
                            .displayOrder(0)
                            .active(Boolean.TRUE)
                            .parentCategoryId(null)
                            .createdAt(Instant.parse("2026-04-12T10:30:00Z"))
                            .build()
            ));

            byte[] serialized = serializer.serialize(original);
            Object deserialized = serializer.deserialize(serialized);

            assertThat(deserialized).isInstanceOf(List.class);
            @SuppressWarnings("unchecked")
            List<CategoryResponse> payload = (List<CategoryResponse>) deserialized;
            assertThat(payload).hasSize(1);
            assertThat(payload.getFirst()).isInstanceOf(CategoryResponse.class);
            assertThat(payload.getFirst().getSlug()).isEqualTo("women");
        });
    }

    @Test
    void serializerRoundTripsProductPageResponse() {
        contextRunner.run(context -> {
            @SuppressWarnings("unchecked")
            RedisSerializer<Object> serializer = (RedisSerializer<Object>) context.getBean(RedisSerializer.class);
            PageResponse<ProductSummaryResponse> original = PageResponse.<ProductSummaryResponse>builder()
                    .content(List.of(ProductSummaryResponse.builder()
                            .id(UUID.fromString("1df3fb3f-3ad4-4b63-a659-5fe0ad403ce7"))
                            .name("Classic Coat")
                            .slug("classic-coat")
                            .description("Wool coat")
                            .status(ProductStatus.ACTIVE)
                            .featured(Boolean.TRUE)
                            .gender(Gender.womens)
                            .productType("outerwear")
                            .createdAt(Instant.parse("2026-04-12T10:30:00Z"))
                            .updatedAt(Instant.parse("2026-04-12T10:45:00Z"))
                            .category(CategorySummary.builder()
                                    .id(10)
                                    .name("Women")
                                    .slug("women")
                                    .build())
                            .build()))
                    .totalElements(1)
                    .totalPages(1)
                    .page(0)
                    .size(12)
                    .hasNext(false)
                    .hasPrevious(false)
                    .build();

            byte[] serialized = serializer.serialize(original);
            Object deserialized = serializer.deserialize(serialized);

            assertThat(deserialized).isInstanceOf(PageResponse.class);
            @SuppressWarnings("unchecked")
            PageResponse<ProductSummaryResponse> payload = (PageResponse<ProductSummaryResponse>) deserialized;
            assertThat(payload.getContent()).hasSize(1);
            assertThat(payload.getContent().getFirst()).isInstanceOf(ProductSummaryResponse.class);
            assertThat(payload.getContent().getFirst().getSlug()).isEqualTo("classic-coat");
            assertThat(payload.getContent().getFirst().getCreatedAt()).isEqualTo(Instant.parse("2026-04-12T10:30:00Z"));
        });
    }

    @Test
    void serializerRoundTripsProductResponse() {
        contextRunner.run(context -> {
            @SuppressWarnings("unchecked")
            RedisSerializer<Object> serializer = (RedisSerializer<Object>) context.getBean(RedisSerializer.class);
            ProductResponse original = ProductResponse.builder()
                    .id(UUID.fromString("1df3fb3f-3ad4-4b63-a659-5fe0ad403ce7"))
                    .name("Classic Coat")
                    .slug("classic-coat")
                    .description("Wool coat")
                    .status(ProductStatus.ACTIVE)
                    .featured(Boolean.TRUE)
                    .gender(Gender.womens)
                    .taxonomyPath(List.of("women", "coats"))
                    .productType("outerwear")
                    .createdAt(Instant.parse("2026-04-12T10:30:00Z"))
                    .updatedAt(Instant.parse("2026-04-12T10:45:00Z"))
                    .category(CategorySummary.builder()
                            .id(10)
                            .name("Women")
                            .slug("women")
                            .build())
                    .tags(List.of())
                    .variants(List.of())
                    .images(List.of())
                    .build();

            byte[] serialized = serializer.serialize(original);
            Object deserialized = serializer.deserialize(serialized);

            assertThat(deserialized).isInstanceOf(ProductResponse.class);
            ProductResponse payload = (ProductResponse) deserialized;
            assertThat(payload.getSlug()).isEqualTo("classic-coat");
            assertThat(payload.getTaxonomyPath()).containsExactly("women", "coats");
            assertThat(payload.getCreatedAt()).isEqualTo(Instant.parse("2026-04-12T10:30:00Z"));
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
