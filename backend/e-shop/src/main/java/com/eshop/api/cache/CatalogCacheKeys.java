package com.eshop.api.cache;

import org.springframework.data.domain.Pageable;

import java.util.Locale;
import java.util.stream.Collectors;

public final class CatalogCacheKeys {

    private static final String ALL_CATEGORIES_KEY = "all";
    private static final String COMMON_CATEGORIES_KEY = "common";

    private CatalogCacheKeys() {
    }

    public static String allCategoriesList() {
        return ALL_CATEGORIES_KEY;
    }

    public static String commonCategoriesList() {
        return COMMON_CATEGORIES_KEY;
    }

    public static String categoryBySlug(String slug) {
        return trimSlug(slug);
    }

    public static String productBySlug(String slug) {
        String normalizedSlug = trimSlug(slug);
        return normalizedSlug == null ? null : normalizedSlug.toLowerCase(Locale.ROOT);
    }

    public static String publicProductsPage(Pageable pageable) {
        if (pageable == null) {
            return "null";
        }

        String sortKey = pageable.getSort().stream()
            .map(order -> order.getProperty() + ":" + order.getDirection())
            .collect(Collectors.joining(","));
        return pageable.getPageNumber() + ":" + pageable.getPageSize() + ":" + sortKey;
    }

    public static String trimSlug(String slug) {
        return slug == null ? null : slug.trim();
    }
}
