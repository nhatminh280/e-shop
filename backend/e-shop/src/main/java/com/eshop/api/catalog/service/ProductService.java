package com.eshop.api.catalog.service;

import com.eshop.api.cache.CacheNames;
import com.eshop.api.catalog.dto.PageResponse;
import com.eshop.api.catalog.dto.ProductResponse;
import com.eshop.api.catalog.dto.ProductSummaryResponse;
import com.eshop.api.catalog.enums.Gender;
import com.eshop.api.catalog.enums.ProductStatus;
import com.eshop.api.catalog.model.Category;
import com.eshop.api.catalog.model.Product;
import com.eshop.api.catalog.repository.CategoryRepository;
import com.eshop.api.catalog.repository.ProductRepository;
import com.eshop.api.exception.CategoryNotFoundException;
import com.eshop.api.exception.InvalidPriceRangeException;
import com.eshop.api.exception.InvalidSearchQueryException;
import com.eshop.api.exception.ProductNotFoundException;
import lombok.RequiredArgsConstructor;
import org.springframework.cache.annotation.Cacheable;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.domain.Specification;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.math.BigDecimal;
import java.util.Arrays;
import java.util.ArrayList;
import java.util.HashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;
import java.util.stream.Collectors;

@Service
@RequiredArgsConstructor
@Transactional(readOnly = true)
public class ProductService {

    private final ProductRepository productRepository;
    private final CategoryRepository categoryRepository;
    private final ProductMapper productMapper;

    @Cacheable(
        cacheNames = CacheNames.PUBLIC_PRODUCTS,
        key = "T(com.eshop.api.catalog.service.ProductService).pageableCacheKey(#pageable)",
        unless = "#result == null"
    )
    public PageResponse<ProductSummaryResponse> getProducts(Pageable pageable) {
        Page<Product> page = productRepository.findByStatus(ProductStatus.ACTIVE, pageable);
        return productMapper.toPageResponse(page);
    }

    public PageResponse<ProductSummaryResponse> getProductsByGender(Gender gender, Pageable pageable) {
        Page<Product> page = productRepository.findByGenderAndStatus(gender, ProductStatus.ACTIVE, pageable);
        return productMapper.toPageResponse(page);
    }

    public PageResponse<ProductSummaryResponse> getProductsByCategorySlug(String categorySlug, Pageable pageable) {
        if (categorySlug == null || categorySlug.isBlank()) {
            throw new CategoryNotFoundException(categorySlug);
        }

        List<Integer> categoryIds = resolveCategoryHierarchy(categorySlug);

        Page<Product> page = productRepository.findByCategory_IdInAndStatus(categoryIds, ProductStatus.ACTIVE, pageable);
        return productMapper.toPageResponse(page);
    }

    public PageResponse<ProductSummaryResponse> getProductsByFilters(
        Gender gender,
        String categorySlug,
        List<String> colorFilters,
        List<String> sizeFilters,
        Boolean inStock,
        BigDecimal priceMin,
        BigDecimal priceMax,
        Pageable pageable
    ) {
        List<String> normalizedColors = normalizeListParameter(colorFilters);
        List<String> normalizedSizes = normalizeListParameter(sizeFilters);

        if (priceMin != null && priceMax != null && priceMin.compareTo(priceMax) > 0) {
            throw new InvalidPriceRangeException();
        }

        if (categorySlug != null && categorySlug.isBlank()) {
            throw new CategoryNotFoundException(categorySlug);
        }

        boolean hasCategory = categorySlug != null && !categorySlug.isBlank();
        List<Integer> categoryIds = hasCategory ? resolveCategoryHierarchy(categorySlug) : List.of();

        boolean hasAnyFilter = gender != null
            || hasCategory
            || !normalizedColors.isEmpty()
            || !normalizedSizes.isEmpty()
            || Boolean.TRUE.equals(inStock)
            || priceMin != null
            || priceMax != null;

        if (!hasAnyFilter) {
            Page<Product> page = productRepository.findByStatus(ProductStatus.ACTIVE, pageable);
            return productMapper.toPageResponse(page);
        }

        boolean requiresAdvancedFiltering = !normalizedColors.isEmpty()
            || !normalizedSizes.isEmpty()
            || Boolean.TRUE.equals(inStock)
            || priceMin != null
            || priceMax != null;

        Page<Product> page;

        if (requiresAdvancedFiltering) {
            page = productRepository.findByFilters(
                gender,
                categoryIds,
                normalizedColors,
                normalizedSizes,
                Boolean.TRUE.equals(inStock) ? Boolean.TRUE : null,
                priceMin,
                priceMax,
                ProductStatus.ACTIVE,
                pageable
            );
        } else if (gender != null && hasCategory) {
            page = productRepository.findByGenderAndCategory_IdInAndStatus(gender, categoryIds, ProductStatus.ACTIVE, pageable);
        } else if (gender != null) {
            page = productRepository.findByGenderAndStatus(gender, ProductStatus.ACTIVE, pageable);
        } else {
            page = productRepository.findByCategory_IdInAndStatus(categoryIds, ProductStatus.ACTIVE, pageable);
        }

        return productMapper.toPageResponse(page);
    }

    public PageResponse<ProductSummaryResponse> searchProducts(String query, Pageable pageable) {
        String normalizedQuery = normalizeQuery(query);

        final String normalizedTerm = normalizedQuery.toLowerCase(Locale.ROOT);
        Specification<Product> specification = (root, criteriaQuery, cb) -> {
            String like = "%" + normalizedTerm + "%";
            return cb.and(
                cb.equal(root.get("status"), ProductStatus.ACTIVE),
                cb.or(
                    cb.like(cb.lower(root.get("name")), like),
                    cb.like(cb.lower(root.get("slug")), like),
                    cb.like(cb.lower(root.get("description")), like)
                )
            );
        };

        Page<Product> page = productRepository.findAll(specification, pageable);

        return productMapper.toPageResponse(page);
    }

    @Cacheable(
        cacheNames = CacheNames.PRODUCT_BY_SLUG,
        key = "T(com.eshop.api.catalog.service.ProductService).normalizeSlugKey(#slug)",
        condition = "#slug != null && !#slug.isBlank()",
        unless = "#result == null"
    )
    public ProductResponse getProductBySlug(String slug) throws ProductNotFoundException {
        String normalizedSlug = normalizeSlugKey(slug);
        Product product = productRepository.findWithDetailsBySlug(normalizedSlug)
            .orElseThrow(() -> new ProductNotFoundException(slug));
        return productMapper.toProductResponse(product);
    }

    private List<Integer> resolveCategoryHierarchy(String categorySlug) {
        String normalizedSlug = normalizeSlugKey(categorySlug);

        if (normalizedSlug == null || normalizedSlug.isBlank()) {
            throw new CategoryNotFoundException(categorySlug);
        }

        Category category = categoryRepository.findBySlug(normalizedSlug)
            .orElseThrow(() -> new CategoryNotFoundException(categorySlug));

        return collectCategoryIds(category);
    }

    private List<Integer> collectCategoryIds(Category root) {
        List<Integer> ids = new ArrayList<>();
        collectCategoryIds(root, ids, new HashSet<>());
        return ids;
    }

    private void collectCategoryIds(Category category, List<Integer> ids, Set<Integer> visited) {
        if (category == null || category.getId() == null) {
            return;
        }
        if (!visited.add(category.getId())) {
            return;
        }

        ids.add(category.getId());
        if (category.getChildren() == null || category.getChildren().isEmpty()) {
            return;
        }

        category.getChildren().forEach(child -> collectCategoryIds(child, ids, visited));
    }

    private String normalizeQuery(String query) {
        if (query == null) {
            throw new InvalidSearchQueryException(null);
        }

        String normalized = query.trim();
        if (normalized.isEmpty()) {
            throw new InvalidSearchQueryException(query);
        }

        return normalized;
    }

    public static String normalizeSlugKey(String slug) {
        return slug == null ? null : slug.trim();
    }

    public static String pageableCacheKey(Pageable pageable) {
        if (pageable == null) {
            return "null";
        }

        String sortKey = pageable.getSort().stream()
            .map(order -> order.getProperty() + ":" + order.getDirection())
            .collect(Collectors.joining(","));
        return pageable.getPageNumber() + ":" + pageable.getPageSize() + ":" + sortKey;
    }

    private List<String> normalizeListParameter(List<String> rawValues) {
        if (rawValues == null || rawValues.isEmpty()) {
            return List.of();
        }

        return rawValues.stream()
            .flatMap(value -> Arrays.stream(value.split(",")))
            .map(String::trim)
            .filter(token -> !token.isEmpty())
            .map(String::toLowerCase)
            .distinct()
            .toList();
    }
}
