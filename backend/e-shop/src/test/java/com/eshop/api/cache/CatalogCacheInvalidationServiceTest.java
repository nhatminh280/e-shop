package com.eshop.api.cache;

import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.springframework.cache.Cache;
import org.springframework.cache.concurrent.ConcurrentMapCacheManager;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Sort;
import org.springframework.transaction.TransactionDefinition;
import org.springframework.transaction.support.AbstractPlatformTransactionManager;
import org.springframework.transaction.support.DefaultTransactionStatus;
import org.springframework.transaction.support.TransactionTemplate;

import static org.assertj.core.api.Assertions.assertThat;

class CatalogCacheInvalidationServiceTest {

    private ConcurrentMapCacheManager cacheManager;
    private CatalogCacheInvalidationService catalogCacheInvalidationService;
    private TransactionTemplate transactionTemplate;
    private AssertingTransactionManager transactionManager;

    @BeforeEach
    void setUp() {
        cacheManager = new ConcurrentMapCacheManager(
            CacheNames.ALL_CATEGORIES,
            CacheNames.COMMON_CATEGORIES,
            CacheNames.CATEGORY_BY_SLUG,
            CacheNames.PUBLIC_PRODUCTS,
            CacheNames.PRODUCT_BY_SLUG
        );
        catalogCacheInvalidationService = new CatalogCacheInvalidationService(cacheManager);
        transactionManager = new AssertingTransactionManager();
        transactionTemplate = new TransactionTemplate(transactionManager);
    }

    @Test
    void invalidatePublicProductCatalogDefersEvictionUntilAfterCommit() {
        String firstPageKey = CatalogCacheKeys.publicProductsPage(PageRequest.of(0, 12, Sort.by(Sort.Direction.ASC, "name")));
        String secondPageKey = CatalogCacheKeys.publicProductsPage(PageRequest.of(1, 12, Sort.by(Sort.Direction.DESC, "createdAt")));
        String productKey = CatalogCacheKeys.productBySlug("classic-coat");
        String untouchedProductKey = CatalogCacheKeys.productBySlug("field-jacket");
        put(CacheNames.PUBLIC_PRODUCTS, firstPageKey, "page-1");
        put(CacheNames.PUBLIC_PRODUCTS, secondPageKey, "page-2");
        put(CacheNames.PRODUCT_BY_SLUG, productKey, "classic-coat");
        put(CacheNames.PRODUCT_BY_SLUG, untouchedProductKey, "field-jacket");
        transactionManager.beforeAfterCommit(() -> {
            assertThat(get(CacheNames.PUBLIC_PRODUCTS, firstPageKey)).isEqualTo("page-1");
            assertThat(get(CacheNames.PUBLIC_PRODUCTS, secondPageKey)).isEqualTo("page-2");
            assertThat(get(CacheNames.PRODUCT_BY_SLUG, productKey)).isEqualTo("classic-coat");
            assertThat(get(CacheNames.PRODUCT_BY_SLUG, untouchedProductKey)).isEqualTo("field-jacket");
        });

        transactionTemplate.executeWithoutResult(status -> {
            catalogCacheInvalidationService.invalidatePublicProductCatalog("classic-coat");

            assertThat(get(CacheNames.PUBLIC_PRODUCTS, firstPageKey)).isEqualTo("page-1");
            assertThat(get(CacheNames.PUBLIC_PRODUCTS, secondPageKey)).isEqualTo("page-2");
            assertThat(get(CacheNames.PRODUCT_BY_SLUG, productKey)).isEqualTo("classic-coat");
            assertThat(get(CacheNames.PRODUCT_BY_SLUG, untouchedProductKey)).isEqualTo("field-jacket");
        });

        assertThat(get(CacheNames.PUBLIC_PRODUCTS, firstPageKey)).isNull();
        assertThat(get(CacheNames.PUBLIC_PRODUCTS, secondPageKey)).isNull();
        assertThat(get(CacheNames.PRODUCT_BY_SLUG, productKey)).isNull();
        assertThat(get(CacheNames.PRODUCT_BY_SLUG, untouchedProductKey)).isEqualTo("field-jacket");
    }

    @Test
    void invalidatePublicProductCatalogSkipsEvictionOnRollback() {
        String pageKey = CatalogCacheKeys.publicProductsPage(PageRequest.of(0, 12, Sort.by(Sort.Direction.ASC, "name")));
        String productKey = CatalogCacheKeys.productBySlug("classic-coat");
        put(CacheNames.PUBLIC_PRODUCTS, pageKey, "page-1");
        put(CacheNames.PRODUCT_BY_SLUG, productKey, "classic-coat");

        transactionTemplate.executeWithoutResult(status -> {
            catalogCacheInvalidationService.invalidatePublicProductCatalog("classic-coat");
            status.setRollbackOnly();

            assertThat(get(CacheNames.PUBLIC_PRODUCTS, pageKey)).isEqualTo("page-1");
            assertThat(get(CacheNames.PRODUCT_BY_SLUG, productKey)).isEqualTo("classic-coat");
        });

        assertThat(get(CacheNames.PUBLIC_PRODUCTS, pageKey)).isEqualTo("page-1");
        assertThat(get(CacheNames.PRODUCT_BY_SLUG, productKey)).isEqualTo("classic-coat");
    }

    @Test
    void invalidateCategoryCatalogEvictsListCachesAndTargetSlugAfterCommit() {
        String allKey = CatalogCacheKeys.allCategoriesList();
        String commonKey = CatalogCacheKeys.commonCategoriesList();
        String targetCategoryKey = CatalogCacheKeys.categoryBySlug("women");
        String untouchedCategoryKey = CatalogCacheKeys.categoryBySlug("men");
        put(CacheNames.ALL_CATEGORIES, allKey, "all-categories");
        put(CacheNames.COMMON_CATEGORIES, commonKey, "common-categories");
        put(CacheNames.CATEGORY_BY_SLUG, targetCategoryKey, "women");
        put(CacheNames.CATEGORY_BY_SLUG, untouchedCategoryKey, "men");
        put(CacheNames.PUBLIC_PRODUCTS, "should-stay", "public-products");
        transactionManager.beforeAfterCommit(() -> {
            assertThat(get(CacheNames.ALL_CATEGORIES, allKey)).isEqualTo("all-categories");
            assertThat(get(CacheNames.COMMON_CATEGORIES, commonKey)).isEqualTo("common-categories");
            assertThat(get(CacheNames.CATEGORY_BY_SLUG, targetCategoryKey)).isEqualTo("women");
            assertThat(get(CacheNames.CATEGORY_BY_SLUG, untouchedCategoryKey)).isEqualTo("men");
            assertThat(get(CacheNames.PUBLIC_PRODUCTS, "should-stay")).isEqualTo("public-products");
        });

        transactionTemplate.executeWithoutResult(status -> {
            catalogCacheInvalidationService.invalidateCategoryCatalog("women");

            assertThat(get(CacheNames.ALL_CATEGORIES, allKey)).isEqualTo("all-categories");
            assertThat(get(CacheNames.COMMON_CATEGORIES, commonKey)).isEqualTo("common-categories");
            assertThat(get(CacheNames.CATEGORY_BY_SLUG, targetCategoryKey)).isEqualTo("women");
        });

        assertThat(get(CacheNames.ALL_CATEGORIES, allKey)).isNull();
        assertThat(get(CacheNames.COMMON_CATEGORIES, commonKey)).isNull();
        assertThat(get(CacheNames.CATEGORY_BY_SLUG, targetCategoryKey)).isNull();
        assertThat(get(CacheNames.CATEGORY_BY_SLUG, untouchedCategoryKey)).isEqualTo("men");
        assertThat(get(CacheNames.PUBLIC_PRODUCTS, "should-stay")).isEqualTo("public-products");
    }

    private void put(String cacheName, String key, Object value) {
        cache(cacheName).put(key, value);
    }

    private Object get(String cacheName, String key) {
        Cache.ValueWrapper valueWrapper = cache(cacheName).get(key);
        return valueWrapper != null ? valueWrapper.get() : null;
    }

    private Cache cache(String cacheName) {
        return cacheManager.getCache(cacheName);
    }

    private static final class AssertingTransactionManager extends AbstractPlatformTransactionManager {

        private Runnable beforeAfterCommitAssertion = () -> {
        };

        void beforeAfterCommit(Runnable assertion) {
            this.beforeAfterCommitAssertion = assertion;
        }

        @Override
        protected Object doGetTransaction() {
            return new Object();
        }

        @Override
        protected void doBegin(Object transaction, TransactionDefinition definition) {
        }

        @Override
        protected void doCommit(DefaultTransactionStatus status) {
            beforeAfterCommitAssertion.run();
            beforeAfterCommitAssertion = () -> {
            };
        }

        @Override
        protected void doRollback(DefaultTransactionStatus status) {
            beforeAfterCommitAssertion = () -> {
            };
        }
    }
}
