package com.eshop.api.cache;

import java.util.List;

public final class CacheNames {

    public static final String PRODUCTS = "products";
    public static final String CATEGORIES = "categories";

    private static final List<String> PHASE_ONE_CACHE_NAMES = List.of(PRODUCTS, CATEGORIES);

    private CacheNames() {
    }

    public static List<String> phaseOneCacheNames() {
        return PHASE_ONE_CACHE_NAMES;
    }
}
