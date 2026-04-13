package com.eshop.api.catalog.service;

import com.eshop.api.cache.CatalogCacheInvalidationService;
import com.eshop.api.cache.CatalogCacheKeys;
import com.eshop.api.cache.CacheNames;
import com.eshop.api.catalog.dto.CategoryCreateRequest;
import com.eshop.api.catalog.dto.CategoryResponse;
import com.eshop.api.catalog.model.Category;
import com.eshop.api.catalog.repository.CategoryRepository;
import com.eshop.api.exception.CategoryAlreadyExistsException;
import com.eshop.api.exception.CategoryNotFoundException;
import lombok.RequiredArgsConstructor;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.ArrayList;
import java.util.List;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class CategoryService {

    private final CategoryRepository categoryRepository;
    private final CatalogCacheInvalidationService catalogCacheInvalidationService;

    @Cacheable(
        cacheNames = CacheNames.ALL_CATEGORIES,
        key = "T(com.eshop.api.cache.CatalogCacheKeys).allCategoriesList()",
        unless = "#result == null"
    )
    public List<CategoryResponse> getAllCategories() {
        List<Category> categories = categoryRepository.findAll(Sort.by(Sort.Direction.ASC, "displayOrder", "name"));
        return categories.stream()
            .map(this::toResponse)
            .collect(ArrayList::new, ArrayList::add, ArrayList::addAll);
    }

    @Cacheable(
        cacheNames = CacheNames.COMMON_CATEGORIES,
        key = "T(com.eshop.api.cache.CatalogCacheKeys).commonCategoriesList()",
        unless = "#result == null"
    )
    public List<CategoryResponse> getCommonCategories() {
        List<Category> categories = categoryRepository
            .findByParentCategoryIsNotNullAndParentCategory_ParentCategoryIsNull(
                Sort.by(Sort.Direction.ASC, "parentCategory.displayOrder", "displayOrder", "name"));

        return categories.stream()
            .map(this::toResponse)
            .collect(ArrayList::new, ArrayList::add, ArrayList::addAll);
    }

    @Cacheable(
        cacheNames = CacheNames.CATEGORY_BY_SLUG,
        key = "T(com.eshop.api.cache.CatalogCacheKeys).categoryBySlug(#slug)",
        condition = "#slug != null && !#slug.isBlank()",
        unless = "#result == null"
    )
    public CategoryResponse getCategoryBySlug(String slug) {
        String normalizedSlug = CatalogCacheKeys.categoryBySlug(slug);
        Category category = categoryRepository.findBySlug(normalizedSlug)
            .orElseThrow(() -> new CategoryNotFoundException(slug));
        return toResponse(category);
    }

    @Transactional
    public CategoryResponse createCategory(CategoryCreateRequest request) {
        String normalizedSlug = CatalogCacheKeys.categoryBySlug(request.getSlug());

        if (categoryRepository.existsBySlug(normalizedSlug)) {
            throw new CategoryAlreadyExistsException(normalizedSlug);
        }

        Category parent = null;
        if (request.getParentCategoryId() != null) {
            parent = categoryRepository.findById(request.getParentCategoryId())
                .orElseThrow(() -> new CategoryNotFoundException(request.getParentCategoryId()));
        }

        Category category = Category.builder()
            .name(request.getName())
            .slug(normalizedSlug)
            .parentCategory(parent)
            .displayOrder(request.getDisplayOrder() != null ? request.getDisplayOrder() : 0)
            .active(request.getActive() != null ? request.getActive() : Boolean.TRUE)
            .build();

        Category saved = categoryRepository.save(category);
        catalogCacheInvalidationService.invalidateCategoryCatalog(saved.getSlug());
        return toResponse(saved);
    }

    private CategoryResponse toResponse(Category category) {
        Integer parentId = category.getParentCategory() != null ? category.getParentCategory().getId() : null;
        return CategoryResponse.builder()
            .id(category.getId())
            .name(category.getName())
            .slug(category.getSlug())
            .displayOrder(category.getDisplayOrder())
            .active(category.getActive())
            .parentCategoryId(parentId)
            .createdAt(category.getCreatedAt())
            .build();
    }

}
