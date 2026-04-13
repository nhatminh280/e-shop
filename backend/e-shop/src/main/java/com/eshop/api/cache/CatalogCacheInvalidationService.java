package com.eshop.api.cache;

import lombok.RequiredArgsConstructor;
import org.springframework.cache.Cache;
import org.springframework.cache.CacheManager;
import org.springframework.stereotype.Service;
import org.springframework.transaction.support.TransactionSynchronization;
import org.springframework.transaction.support.TransactionSynchronizationManager;

import java.util.Objects;

@Service
@RequiredArgsConstructor
public class CatalogCacheInvalidationService {

    private final CacheManager cacheManager;

    public void invalidateCategoryCatalog(String slug) {
        executeAfterCommit(() -> {
            evict(CacheNames.ALL_CATEGORIES, CatalogCacheKeys.allCategoriesList());
            evict(CacheNames.COMMON_CATEGORIES, CatalogCacheKeys.commonCategoriesList());
            evict(CacheNames.CATEGORY_BY_SLUG, CatalogCacheKeys.categoryBySlug(slug));
        });
    }

    public void invalidatePublicProductCatalog(String slug) {
        executeAfterCommit(() -> {
            clear(CacheNames.PUBLIC_PRODUCTS);
            evict(CacheNames.PRODUCT_BY_SLUG, CatalogCacheKeys.productBySlug(slug));
        });
    }

    public void invalidatePublicProductCatalog(String previousSlug, String currentSlug) {
        executeAfterCommit(() -> {
            clear(CacheNames.PUBLIC_PRODUCTS);

            String previousKey = CatalogCacheKeys.productBySlug(previousSlug);
            String currentKey = CatalogCacheKeys.productBySlug(currentSlug);

            evict(CacheNames.PRODUCT_BY_SLUG, previousKey);
            if (!Objects.equals(previousKey, currentKey)) {
                evict(CacheNames.PRODUCT_BY_SLUG, currentKey);
            }
        });
    }

    public void invalidateProductDetail(String slug) {
        executeAfterCommit(() -> evict(CacheNames.PRODUCT_BY_SLUG, CatalogCacheKeys.productBySlug(slug)));
    }

    private void executeAfterCommit(Runnable action) {
        if (TransactionSynchronizationManager.isSynchronizationActive()
            && TransactionSynchronizationManager.isActualTransactionActive()) {
            TransactionSynchronizationManager.registerSynchronization(new TransactionSynchronization() {
                @Override
                public void afterCommit() {
                    action.run();
                }
            });
            return;
        }

        action.run();
    }

    private void clear(String cacheName) {
        Cache cache = cacheManager.getCache(cacheName);
        if (cache != null) {
            cache.clear();
        }
    }

    private void evict(String cacheName, Object key) {
        if (key == null) {
            return;
        }

        Cache cache = cacheManager.getCache(cacheName);
        if (cache != null) {
            cache.evict(key);
        }
    }
}
