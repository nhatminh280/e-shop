package com.eshop.api.cache;

import com.fasterxml.jackson.databind.SerializationFeature;
import java.util.Map;
import java.util.stream.Collectors;
import lombok.RequiredArgsConstructor;
import org.springframework.boot.context.properties.EnableConfigurationProperties;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.redis.cache.BatchStrategies;
import org.springframework.data.redis.cache.RedisCacheConfiguration;
import org.springframework.data.redis.cache.RedisCacheManager;
import org.springframework.data.redis.cache.RedisCacheWriter;
import org.springframework.data.redis.connection.RedisConnectionFactory;
import org.springframework.data.redis.serializer.GenericJackson2JsonRedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializer;
import org.springframework.data.redis.serializer.RedisSerializationContext;

@Configuration
@EnableConfigurationProperties(CacheProperties.class)
@RequiredArgsConstructor
public class RedisCacheConfig {

    private static final String CACHE_FORMAT_VERSION = "v5";

    private final CacheProperties cacheProperties;

    @Bean
    public RedisSerializer<Object> redisCacheValueSerializer() {
        GenericJackson2JsonRedisSerializer serializer = new GenericJackson2JsonRedisSerializer();
        serializer.configure(mapper -> {
            mapper.findAndRegisterModules();
            mapper.disable(SerializationFeature.WRITE_DATES_AS_TIMESTAMPS);
        });
        return serializer;
    }

    @Bean
    public RedisCacheConfiguration redisCacheConfiguration(RedisSerializer<Object> redisCacheValueSerializer) {
        return RedisCacheConfiguration.defaultCacheConfig()
                .entryTtl(cacheProperties.getDefaultTtl())
                .computePrefixWith(cacheName -> cacheProperties.getNamespace() + "::" + CACHE_FORMAT_VERSION + "::" + cacheName + "::")
                .serializeValuesWith(RedisSerializationContext.SerializationPair.fromSerializer(redisCacheValueSerializer));
    }

    @Bean
    public RedisCacheManager cacheManager(
            RedisConnectionFactory connectionFactory,
            RedisCacheConfiguration redisCacheConfiguration) {
        Map<String, RedisCacheConfiguration> initialCacheConfigurations = CacheNames.phaseOneCacheNames().stream()
                .collect(Collectors.toUnmodifiableMap(
                        cacheName -> cacheName,
                        cacheName -> redisCacheConfiguration
                ));

        RedisCacheWriter cacheWriter = RedisCacheWriter.nonLockingRedisCacheWriter(
                connectionFactory,
                BatchStrategies.scan(1000)
        );

        return RedisCacheManager.builder(cacheWriter)
                .cacheDefaults(redisCacheConfiguration)
                .withInitialCacheConfigurations(initialCacheConfigurations)
                .build();
    }
}
