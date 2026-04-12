import http from 'k6/http';
import { check, fail } from 'k6';
import { sleep } from 'k6';

const BASE_URL = sanitizeBaseUrl(__ENV.BASE_URL);
const PRODUCT_SLUG = (__ENV.PRODUCT_SLUG || '').trim();
const VUS = parsePositiveInt(__ENV.VUS, 10);
const DURATION = (__ENV.DURATION || '2m').trim();
const PRIME_ROUNDS = parseNonNegativeInt(__ENV.PRIME_ROUNDS, 0);

export const options = {
  scenarios: {
    catalog_cache_benchmark: {
      executor: 'constant-vus',
      vus: VUS,
      duration: DURATION,
      gracefulStop: '10s',
    },
  },
  thresholds: {
    http_req_failed: ['rate<0.01'],
    checks: ['rate>0.99'],
    'http_req_duration{endpoint:categories}': ['p(95)<800', 'p(99)<1500'],
    'http_req_duration{endpoint:categories-common}': ['p(95)<800', 'p(99)<1500'],
    'http_req_duration{endpoint:products}': ['p(95)<1000', 'p(99)<2000'],
    'http_req_duration{endpoint:product-by-slug}': ['p(95)<900', 'p(99)<1800'],
  },
};

function sanitizeBaseUrl(value) {
  const baseUrl = (value || '').trim().replace(/\/+$/, '');
  if (!baseUrl) {
    fail('BASE_URL is required');
  }

  return baseUrl;
}

function parsePositiveInt(value, fallback) {
  const parsed = Number.parseInt(value || '', 10);
  if (Number.isInteger(parsed) && parsed > 0) {
    return parsed;
  }

  return fallback;
}

function parseNonNegativeInt(value, fallback) {
  const parsed = Number.parseInt(value || '', 10);
  if (Number.isInteger(parsed) && parsed >= 0) {
    return parsed;
  }

  return fallback;
}

function get(path, endpoint) {
  return http.get(`${BASE_URL}${path}`, {
    tags: {
      endpoint,
    },
  });
}

function verifyResponse(response, endpoint, assertion) {
  check(response, {
    [`${endpoint} returns 200`]: (r) => r.status === 200,
    [`${endpoint} body is valid`]: (r) => r.status === 200 && assertion(r),
  });
}

export function setup() {
  if (!PRODUCT_SLUG) {
    fail('PRODUCT_SLUG is required');
  }

  for (let round = 0; round < PRIME_ROUNDS; round += 1) {
    primeEndpoint(
      get('/api/catalog/categories', 'categories'),
      'categories',
      (body) => Array.isArray(body)
    );
    primeEndpoint(
      get('/api/catalog/categories/common', 'categories-common'),
      'categories-common',
      (body) => Array.isArray(body)
    );
    primeEndpoint(
      get('/api/catalog/products', 'products'),
      'products',
      (body) => body !== null && typeof body === 'object' && Array.isArray(body.content)
    );
    primeEndpoint(
      get(`/api/catalog/products/${encodeURIComponent(PRODUCT_SLUG)}`, 'product-by-slug'),
      'product-by-slug',
      (body) => body !== null && typeof body === 'object' && body.slug === PRODUCT_SLUG
    );
  }

  return {
    baseUrl: BASE_URL,
    productSlug: PRODUCT_SLUG,
  };
}

export default function () {
  const categories = get('/api/catalog/categories', 'categories');
  const commonCategories = get('/api/catalog/categories/common', 'categories-common');
  const products = get('/api/catalog/products', 'products');
  const product = get(`/api/catalog/products/${encodeURIComponent(PRODUCT_SLUG)}`, 'product-by-slug');

  verifyResponse(categories, 'categories', (r) => safeJson(r, (value) => Array.isArray(value)));
  verifyResponse(commonCategories, 'categories-common', (r) => safeJson(r, (value) => Array.isArray(value)));
  verifyResponse(products, 'products', (r) => {
    const body = safeJson(r);
    return body !== null && typeof body === 'object' && Array.isArray(body.content);
  });
  verifyResponse(product, 'product-by-slug', (r) => {
    const body = safeJson(r);
    return body !== null && typeof body === 'object' && body.slug === PRODUCT_SLUG;
  });

  sleep(1);
}

function safeJson(response, predicate) {
  try {
    const body = response.json();
    return predicate ? predicate(body) : body;
  } catch (_error) {
    return null;
  }
}

function primeEndpoint(response, endpoint, assertion) {
  if (response.status !== 200) {
    fail(`Priming ${endpoint} failed with status ${response.status}`);
  }

  const body = safeJson(response);
  if (!assertion(body)) {
    fail(`Priming ${endpoint} returned an unexpected body`);
  }
}
