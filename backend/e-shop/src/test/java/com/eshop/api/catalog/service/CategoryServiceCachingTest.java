package com.eshop.api.catalog.service;

import com.eshop.api.cache.CacheNames;
import com.eshop.api.cache.CatalogCacheInvalidationService;
import com.eshop.api.catalog.dto.CategoryResponse;
import com.eshop.api.catalog.model.Category;
import com.eshop.api.catalog.repository.CategoryRepository;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.springframework.aop.support.AopUtils;
import org.springframework.cache.CacheManager;
import org.springframework.cache.annotation.EnableCaching;
import org.springframework.cache.concurrent.ConcurrentMapCacheManager;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.test.context.ContextConfiguration;
import org.springframework.test.context.junit.jupiter.SpringExtension;

import java.time.Instant;
import java.util.List;

import static org.assertj.core.api.Assertions.assertThat;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.reset;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

@ExtendWith(SpringExtension.class)
@ContextConfiguration(classes = CategoryServiceCachingTest.TestConfig.class)
class CategoryServiceCachingTest {

    @org.springframework.beans.factory.annotation.Autowired
    private CategoryService categoryService;

    @org.springframework.beans.factory.annotation.Autowired
    private CategoryRepository categoryRepository;

    @org.springframework.beans.factory.annotation.Autowired
    private CatalogCacheInvalidationService catalogCacheInvalidationService;

    @org.springframework.beans.factory.annotation.Autowired
    private CacheManager cacheManager;

    @BeforeEach
    void setUp() {
        reset(categoryRepository, catalogCacheInvalidationService);
        cacheManager.getCacheNames().forEach(cacheName -> cacheManager.getCache(cacheName).clear());
    }

    @Test
    void getAllCategoriesCachesRepeatedCalls() {
        List<Category> categories = List.of(
            category(1, "Women", "women"),
            category(2, "Men", "men")
        );
        when(categoryRepository.findAll(any(org.springframework.data.domain.Sort.class))).thenReturn(categories);

        List<CategoryResponse> firstResult = categoryService.getAllCategories();
        List<CategoryResponse> secondResult = categoryService.getAllCategories();

        assertThat(AopUtils.isAopProxy(categoryService)).isTrue();
        assertThat(secondResult).isEqualTo(firstResult);
        verify(categoryRepository, times(1)).findAll(any(org.springframework.data.domain.Sort.class));
    }

    @Test
    void getCommonCategoriesCachesRepeatedCalls() {
        Category parent = category(10, "Women", "women");
        List<Category> categories = List.of(
            category(11, "Dresses", "dresses", parent),
            category(12, "Shoes", "shoes", parent)
        );
        when(categoryRepository.findByParentCategoryIsNotNullAndParentCategory_ParentCategoryIsNull(any(org.springframework.data.domain.Sort.class)))
            .thenReturn(categories);

        List<CategoryResponse> firstResult = categoryService.getCommonCategories();
        List<CategoryResponse> secondResult = categoryService.getCommonCategories();

        assertThat(secondResult).isEqualTo(firstResult);
        verify(categoryRepository, times(1))
            .findByParentCategoryIsNotNullAndParentCategory_ParentCategoryIsNull(any(org.springframework.data.domain.Sort.class));
    }

    private static Category category(int id, String name, String slug) {
        return category(id, name, slug, null);
    }

    private static Category category(int id, String name, String slug, Category parent) {
        return Category.builder()
            .id(id)
            .name(name)
            .slug(slug)
            .parentCategory(parent)
            .displayOrder(id)
            .active(true)
            .createdAt(Instant.parse("2026-04-12T10:15:30Z"))
            .build();
    }

    @Configuration(proxyBeanMethods = false)
    @EnableCaching(proxyTargetClass = true)
    static class TestConfig {

        @Bean
        CategoryRepository categoryRepository() {
            return mock(CategoryRepository.class);
        }

        @Bean
        CatalogCacheInvalidationService catalogCacheInvalidationService() {
            return mock(CatalogCacheInvalidationService.class);
        }

        @Bean
        CacheManager cacheManager() {
            return new ConcurrentMapCacheManager(
                CacheNames.ALL_CATEGORIES,
                CacheNames.COMMON_CATEGORIES,
                CacheNames.CATEGORY_BY_SLUG
            );
        }

        @Bean
        CategoryService categoryService(
            CategoryRepository categoryRepository,
            CatalogCacheInvalidationService catalogCacheInvalidationService
        ) {
            return new CategoryService(categoryRepository, catalogCacheInvalidationService);
        }
    }
}
