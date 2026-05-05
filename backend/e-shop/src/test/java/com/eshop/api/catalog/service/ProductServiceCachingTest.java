package com.eshop.api.catalog.service;

import com.eshop.api.cache.CacheNames;
import com.eshop.api.cache.CatalogCacheKeys;
import com.eshop.api.catalog.dto.PageResponse;
import com.eshop.api.catalog.dto.ProductResponse;
import com.eshop.api.catalog.dto.ProductSummaryResponse;
import com.eshop.api.catalog.enums.ProductStatus;
import com.eshop.api.catalog.model.Category;
import com.eshop.api.catalog.model.Product;
import com.eshop.api.catalog.repository.CategoryRepository;
import com.eshop.api.catalog.repository.ProductRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.aop.support.AopUtils;
import org.springframework.cache.Cache;
import org.springframework.cache.CacheManager;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.cache.concurrent.ConcurrentMapCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.junit.jupiter.SpringExtension;

import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
import java.util.Optional;
import java.util.UUID;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(SpringExtension.class)
@ContextConfiguration(classes = ProductServiceCachingTest.TestConfig.class)
class ProductServiceCachingTest {

    @org.springframework.beans.factory.annotation.Autowired
    private ProductService productService;

    @org.springframework.beans.factory.annotation.Autowired
    private ProductRepository productRepository;

    @org.springframework.beans.factory.annotation.Autowired
    private CategoryRepository categoryRepository;

    @org.springframework.beans.factory.annotation.Autowired
    private ProductMapper productMapper;

    @org.springframework.beans.factory.annotation.Autowired
    private CacheManager cacheManager;

    @BeforeEach
    void setUp() {
        reset(productRepository, categoryRepository, productMapper);
        cacheManager.getCacheNames().forEach(cacheName -> cacheManager.getCache(cacheName).clear());
    }

    @Test
    void getProductsCachesUsingCatalogPageKey() {
        Pageable pageable = PageRequest.of(0, 12, Sort.by(Sort.Direction.ASC, "name"));
        String expectedCacheKey = CatalogCacheKeys.publicProductsPage(pageable);
        Product product = product("classic-coat");
        Page<Product> page = new PageImpl<>(List.of(product), pageable, 1);
        PageResponse<ProductSummaryResponse> response = PageResponse.<ProductSummaryResponse>builder()
            .content(List.of(ProductSummaryResponse.builder()
                .id(product.getId())
                .name(product.getName())
                .slug(product.getSlug())
                .status(ProductStatus.ACTIVE)
                .build()))
            .totalElements(1)
            .totalPages(1)
            .page(0)
            .size(12)
            .hasNext(false)
            .hasPrevious(false)
            .build();
        when(productRepository.findByStatus(ProductStatus.ACTIVE, pageable)).thenReturn(page);
        when(productMapper.toPageResponse(page)).thenReturn(response);

        PageResponse<ProductSummaryResponse> firstResult = productService.getProducts(pageable);
        Cache.ValueWrapper cachedValue = cacheManager.getCache(CacheNames.PUBLIC_PRODUCTS).get(expectedCacheKey);
        PageResponse<ProductSummaryResponse> secondResult = productService.getProducts(pageable);

        assertThat(AopUtils.isAopProxy(productService)).isTrue();
        assertThat(cachedValue).isNotNull();
        assertThat(cachedValue.get()).isEqualTo(firstResult);
        assertThat(cacheManager.getCache(CacheNames.PUBLIC_PRODUCTS).get(pageable)).isNull();
        assertThat(secondResult).isEqualTo(firstResult);
        verify(productRepository, times(1)).findByStatus(ProductStatus.ACTIVE, pageable);
        verify(productMapper, times(1)).toPageResponse(page);
    }

    @Test
    void getProductBySlugCachesNormalizedSlugLookups() {
        Product product = product("classic-coat");
        ProductResponse response = ProductResponse.builder()
            .id(product.getId())
            .name(product.getName())
            .slug(product.getSlug())
            .description(product.getDescription())
            .basePrice(product.getBasePrice())
            .status(product.getStatus())
            .featured(product.getFeatured())
            .productType(product.getProductType())
            .createdAt(product.getCreatedAt())
            .updatedAt(product.getUpdatedAt())
            .taxonomyPath(List.of())
            .tags(List.of())
            .variants(List.of())
            .images(List.of())
            .build();
        when(productRepository.findWithDetailsBySlug("classic-coat")).thenReturn(Optional.of(product));
        when(productMapper.toProductResponse(product)).thenReturn(response);

        ProductResponse firstResult = productService.getProductBySlug("  CLASSIC-COAT  ");
        ProductResponse secondResult = productService.getProductBySlug("classic-coat");

        assertThat(secondResult).isEqualTo(firstResult);
        verify(productRepository, times(1)).findWithDetailsBySlug("classic-coat");
        verify(productMapper, times(1)).toProductResponse(product);
    }

    private static Product product(String slug) {
        Category category = Category.builder()
            .id(7)
            .name("Outerwear")
            .slug("outerwear")
            .build();

        return Product.builder()
            .id(UUID.fromString("11111111-1111-1111-1111-111111111111"))
            .name("Classic Coat")
            .slug(slug)
            .description("Wool coat")
            .category(category)
            .basePrice(new BigDecimal("129.00"))
            .status(ProductStatus.ACTIVE)
            .featured(true)
            .productType("coat")
            .createdAt(Instant.parse("2026-04-12T10:15:30Z"))
            .updatedAt(Instant.parse("2026-04-12T10:15:30Z"))
            .build();
    }

    @Configuration(proxyBeanMethods = false)
    @EnableCaching(proxyTargetClass = true)
    static class TestConfig {

        @Bean
        ProductRepository productRepository() {
            return mock(ProductRepository.class);
        }

        @Bean
        CategoryRepository categoryRepository() {
            return mock(CategoryRepository.class);
        }

        @Bean
        ProductMapper productMapper() {
            return mock(ProductMapper.class);
        }

        @Bean
        CacheManager cacheManager() {
            return new ConcurrentMapCacheManager(
                CacheNames.PUBLIC_PRODUCTS,
                CacheNames.PRODUCT_BY_SLUG
            );
        }

        @Bean
        ProductService productService(
            ProductRepository productRepository,
            CategoryRepository categoryRepository,
            ProductMapper productMapper
        ) {
            return new ProductService(productRepository, categoryRepository, productMapper);
        }
    }
}
