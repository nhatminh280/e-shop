package com.eshop.api.cache;

import java.util.List;

public final class CacheNames {

    public static final String ALL_CATEGORIES = "catalog:categories:all";
    public static final String COMMON_CATEGORIES = "catalog:categories:common";
    public static final String CATEGORY_BY_SLUG = "catalog:categories:by-slug";
    public static final String PUBLIC_PRODUCTS = "catalog:products:public";
    public static final String PRODUCT_BY_SLUG = "catalog:products:by-slug";

    private static final List<String> PHASE_ONE_CACHE_NAMES = List.of(
            ALL_CATEGORIES,
            COMMON_CATEGORIES,
            CATEGORY_BY_SLUG,
            PUBLIC_PRODUCTS,
            PRODUCT_BY_SLUG
    );

    private CacheNames() {
    }

    public static List<String> phaseOneCacheNames() {
        return PHASE_ONE_CACHE_NAMES;
    }
}
