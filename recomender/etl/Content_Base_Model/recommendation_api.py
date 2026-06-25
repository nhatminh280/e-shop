from __future__ import annotations

import json
import logging
import os
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any

import redis
from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, field_validator

from .qdrant_vector_store import QdrantConfig, QdrantVectorStore
from .scheduler_api import get_scheduler_monitor

from functools import lru_cache


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class Config:
    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB = int(os.getenv("REDIS_DB", "0"))
    REDIS_CACHE_TTL = int(os.getenv("REDIS_CACHE_TTL", "3600"))
    USE_REDIS = os.getenv("USE_REDIS", "true").lower() == "true"

    DEFAULT_K = int(os.getenv("DEFAULT_RECOMMENDATION_K", "10"))
    MAX_K = int(os.getenv("MAX_RECOMMENDATION_K", "100"))
    API_VERSION = "1.1.0"
    VECTOR_BACKEND = "qdrant"


class RecommendationItem(BaseModel):
    variant_id: str
    similarity_score: float
    product_name: str | None = None
    category_name: str | None = None
    price: float | None = None
    image_path: str | None = None


class RecommendationResponse(BaseModel):
    query_variant_id: str
    recommendations: list[RecommendationItem]
    response_time_ms: float
    from_cache: bool = False
    total_results: int


class TextSearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=512)
    k: int = Field(default=10, ge=1, le=50)
    min_similarity: float = Field(default=0.0, ge=0.0, le=1.0)

    @field_validator("query")
    @classmethod
    def strip_query(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("query cannot be blank")
        return stripped


class TextSearchResponse(BaseModel):
    query: str
    recommendations: list[RecommendationItem]
    response_time_ms: float
    total_results: int


@lru_cache(maxsize=1)
def _clip_text_encoder():
    """Lazy CLIP loader — only pays the model-load cost on first text search.

    The recommender Docker image copies `etl/` into `/app/`, so
    `clip_embedding_pipeline` lives at the top of the import path (not inside
    a package). Use absolute import to handle that layout.
    """
    try:
        from clip_embedding_pipeline import CLIPEmbedder  # type: ignore[import-not-found]
    except ImportError:
        # Fallback when run from a Python checkout where `etl/` is still the
        # package root.
        from etl.clip_embedding_pipeline import CLIPEmbedder  # type: ignore[import-not-found]

    model_name = os.getenv("CLIP_TEXT_MODEL", "ViT-B/32").strip()
    return CLIPEmbedder(model_name=model_name)


class BatchRecommendationRequest(BaseModel):
    product_ids: list[str] = Field(..., max_length=50)
    k: int = Field(10, ge=1, le=100)

    @field_validator("product_ids")
    @classmethod
    def validate_product_ids(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("product_ids cannot be empty")
        return value


class HealthResponse(BaseModel):
    status: str
    timestamp: str
    vector_backend: str
    qdrant_collection: str
    qdrant_collection_size: int
    faiss_index_size: int
    redis_connected: bool
    version: str
    embedding_dimension: int


class RedisCacheManager:
    def __init__(self, config: type[Config]):
        self.config = config
        self.redis_client: redis.Redis | None = None

        if not config.USE_REDIS:
            return

        try:
            self.redis_client = redis.Redis(
                host=config.REDIS_HOST,
                port=config.REDIS_PORT,
                db=config.REDIS_DB,
                decode_responses=True,
            )
            self.redis_client.ping()
            logger.info("Redis connected")
        except Exception as exc:
            logger.warning("Redis connection failed: %s", exc)
            self.redis_client = None

    def get(self, variant_id: str, k: int) -> dict[str, Any] | None:
        if not self.redis_client:
            return None

        key = self._key(variant_id, k)
        try:
            cached = self.redis_client.get(key)
            return json.loads(cached) if cached else None
        except Exception as exc:
            logger.error("Redis get error for %s: %s", key, exc)
            return None

    def set(self, variant_id: str, k: int, data: dict[str, Any]) -> None:
        if not self.redis_client:
            return

        key = self._key(variant_id, k)
        try:
            self.redis_client.setex(key, self.config.REDIS_CACHE_TTL, json.dumps(data))
        except Exception as exc:
            logger.error("Redis set error for %s: %s", key, exc)

    def is_connected(self) -> bool:
        if not self.redis_client:
            return False
        try:
            self.redis_client.ping()
            return True
        except Exception:
            return False

    @staticmethod
    def _key(variant_id: str, k: int) -> str:
        return f"rec:qdrant:{QdrantConfig.COLLECTION}:{variant_id}:{k}"


vector_store: QdrantVectorStore | None = None
cache_manager: RedisCacheManager | None = None


@asynccontextmanager
async def lifespan(_: FastAPI):
    global vector_store, cache_manager

    logger.info("Starting Qdrant recommendation API")

    vector_store = QdrantVectorStore()
    vector_store.ensure_collection(recreate=False)
    cache_manager = RedisCacheManager(Config)

    logger.info("Recommendation API ready")
    yield
    logger.info("Recommendation API shutting down")


eshop = FastAPI(
    title="Hybrid Recommendation API",
    description="Product recommendations using Qdrant and hybrid embeddings",
    version=Config.API_VERSION,
    lifespan=lifespan,
)

eshop.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@eshop.middleware("http")
async def add_process_time_header(request: Request, call_next):
    start_time = time.time()
    response = await call_next(request)
    response.headers["X-Process-Time-Ms"] = str(round((time.time() - start_time) * 1000, 2))
    return response


def _store() -> QdrantVectorStore:
    if vector_store is None:
        raise HTTPException(status_code=503, detail="Vector store is not initialized")
    return vector_store


def _cache() -> RedisCacheManager:
    if cache_manager is None:
        raise HTTPException(status_code=503, detail="Cache manager is not initialized")
    return cache_manager


def _recommendation_item(variant_id: str, score: float, metadata: dict[str, Any]) -> RecommendationItem:
    image_path = metadata.get("image_path") or metadata.get("primary_image_url")
    return RecommendationItem(
        variant_id=variant_id,
        similarity_score=score,
        product_name=metadata.get("product_name"),
        category_name=metadata.get("category_name"),
        price=metadata.get("price"),
        image_path=image_path,
    )


def _select_best_variant_per_product(
    candidates: list[tuple[str, float, dict[str, Any]]],
    query_product_id: str | None,
) -> list[tuple[str, float, dict[str, Any]]]:
    grouped: dict[str, list[tuple[str, float, dict[str, Any]]]] = {}

    for variant_id, score, metadata in candidates:
        product_id = metadata.get("product_id")
        if not product_id or product_id == query_product_id:
            continue
        grouped.setdefault(str(product_id), []).append((variant_id, score, metadata))

    best_variants: list[tuple[str, float, dict[str, Any]]] = []
    for variants in grouped.values():
        best_variants.append(
            max(
                variants,
                key=lambda item: (
                    item[2].get("popularity_score_normalized") or 0,
                    item[1],
                ),
            )
        )

    return best_variants


@eshop.get("/", response_model=dict[str, str])
async def root():
    return {
        "message": "Hybrid Recommendation API",
        "vector_backend": Config.VECTOR_BACKEND,
        "docs": "/docs",
    }


@eshop.get("/health", response_model=HealthResponse)
async def health_check():
    store = _store()
    collection_size = store.collection_size()
    return HealthResponse(
        status="healthy" if collection_size > 0 else "degraded",
        timestamp=datetime.utcnow().isoformat(),
        vector_backend=Config.VECTOR_BACKEND,
        qdrant_collection=QdrantConfig.COLLECTION,
        qdrant_collection_size=collection_size,
        faiss_index_size=collection_size,
        redis_connected=_cache().is_connected(),
        version=Config.API_VERSION,
        embedding_dimension=QdrantConfig.EMBEDDING_DIM,
    )


@eshop.get("/recommend/{variant_id}", response_model=RecommendationResponse)
async def get_recommendations(
    variant_id: str,
    k: int = Query(default=Config.DEFAULT_K, ge=1, le=Config.MAX_K),
    min_similarity: float = Query(default=0.0, ge=0.0, le=1.0),
):
    start_time = time.time()
    store = _store()
    cache = _cache()

    cached = cache.get(variant_id, k)
    if cached:
        cached["response_time_ms"] = (time.time() - start_time) * 1000
        cached["from_cache"] = True
        return RecommendationResponse(**cached)

    query_metadata = store.product_metadata.get(variant_id, {})
    query_gender = query_metadata.get("gender")
    query_product_id = query_metadata.get("product_id")

    try:
        rec_ids, rec_scores = store.search(variant_id, k * 10)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"Product not found: {exc}") from exc
    except Exception as exc:
        logger.exception("Qdrant search error")
        raise HTTPException(status_code=500, detail="Search engine error") from exc

    candidates: list[tuple[str, float, dict[str, Any]]] = []
    for rec_id, score in zip(rec_ids, rec_scores):
        if score < min_similarity:
            continue
        metadata = store.product_metadata.get(rec_id, {})
        if metadata:
            candidates.append((rec_id, score, metadata))

    best_variants = _select_best_variant_per_product(candidates, query_product_id)

    recommendation_pairs = [
        (_recommendation_item(candidate_id, score, metadata), metadata)
        for candidate_id, score, metadata in best_variants
    ]

    if query_gender:
        same_gender = [item for item, metadata in recommendation_pairs if metadata.get("gender") == query_gender]
        diff_gender = [item for item, metadata in recommendation_pairs if metadata.get("gender") != query_gender]
        final_recommendations = same_gender[:k]
        if len(final_recommendations) < k:
            final_recommendations.extend(diff_gender[: k - len(final_recommendations)])
    else:
        final_recommendations = [item for item, _ in recommendation_pairs[:k]]

    response_data = {
        "query_variant_id": variant_id,
        "recommendations": [item.model_dump() for item in final_recommendations],
        "response_time_ms": (time.time() - start_time) * 1000,
        "from_cache": False,
        "total_results": len(final_recommendations),
    }

    cache.set(variant_id, k, response_data)
    return RecommendationResponse(**response_data)


@eshop.post("/recommend/by-text", response_model=TextSearchResponse)
async def get_recommendations_by_text(request: TextSearchRequest):
    """Semantic product search for descriptor-heavy queries with no anchor product.
    Encodes the query with CLIP's text head and searches the variant Qdrant collection.
    """
    start_time = time.time()
    store = _store()

    try:
        encoder = _clip_text_encoder()
    except Exception as exc:
        logger.exception("Failed to load CLIP text encoder")
        raise HTTPException(status_code=503, detail="text_encoder_unavailable") from exc

    vector = encoder.encode_text(request.query)
    if vector is None:
        raise HTTPException(status_code=503, detail="text_encoding_failed")

    try:
        rec_ids, rec_scores = store.search_by_vector(list(vector), request.k * 3)
    except Exception:
        logger.exception("Qdrant search-by-vector failed")
        raise HTTPException(status_code=500, detail="search_engine_error")

    seen_products: set[str] = set()
    items: list[RecommendationItem] = []
    for variant_id, score in zip(rec_ids, rec_scores):
        if score < request.min_similarity:
            continue
        metadata = store.product_metadata.get(variant_id, {})
        product_id = str(metadata.get("product_id") or variant_id)
        if product_id in seen_products:
            # Collapse variants of the same product so we do not return five
            # color variants of the same jacket.
            continue
        seen_products.add(product_id)
        items.append(_recommendation_item(variant_id, score, metadata))
        if len(items) >= request.k:
            break

    return TextSearchResponse(
        query=request.query,
        recommendations=items,
        response_time_ms=round((time.time() - start_time) * 1000, 2),
        total_results=len(items),
    )


@eshop.post("/recommend/batch", response_model=dict[str, Any])
async def get_batch_recommendations(request: BatchRecommendationRequest):
    start_time = time.time()
    store = _store()

    try:
        results = store.batch_search(request.product_ids, request.k)
    except Exception as exc:
        logger.exception("Batch Qdrant search error")
        raise HTTPException(status_code=500, detail="Batch search failed") from exc

    formatted_results: dict[str, Any] = {}
    for product_id, (rec_ids, rec_scores) in results.items():
        recommendations = []
        for rec_id, score in zip(rec_ids, rec_scores):
            metadata = store.product_metadata.get(rec_id, {})
            recommendations.append(_recommendation_item(rec_id, score, metadata).model_dump())

        formatted_results[product_id] = {
            "recommendations": recommendations,
            "total_results": len(recommendations),
        }

    return {
        "results": formatted_results,
        "response_time_ms": (time.time() - start_time) * 1000,
        "total_queries": len(request.product_ids),
        "successful_queries": len(results),
    }


@eshop.get("/stats", response_model=dict[str, Any])
async def get_stats():
    store = _store()
    return {
        "total_products": store.collection_size(),
        "index_type": "Qdrant/COSINE",
        "vector_backend": Config.VECTOR_BACKEND,
        "qdrant_collection": QdrantConfig.COLLECTION,
        "embedding_dimension": QdrantConfig.EMBEDDING_DIM,
        "redis_enabled": Config.USE_REDIS,
        "cache_ttl_seconds": Config.REDIS_CACHE_TTL,
        "max_k": Config.MAX_K,
    }


@eshop.get("/scheduler/summary", response_model=dict[str, Any])
async def scheduler_summary():
    try:
        monitor = get_scheduler_monitor()
        return {"status": "success", "data": monitor.get_scheduler_summary()}
    except Exception as exc:
        logger.error("Error getting scheduler summary: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@eshop.get("/scheduler/history", response_model=dict[str, Any])
async def scheduler_run_history(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    task: str | None = Query(None),
    status: str | None = Query(None),
):
    try:
        monitor = get_scheduler_monitor()
        history = monitor.get_run_history(
            page=page,
            page_size=page_size,
            task_filter=task,
            status_filter=status,
        )
        return {"status": "success", "data": history}
    except Exception as exc:
        logger.error("Error getting run history: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@eshop.get("/scheduler/logs", response_model=dict[str, Any])
async def scheduler_logs(
    lines: int = Query(default=100, ge=10, le=1000),
    minutes: int | None = Query(None, ge=1, le=1440),
):
    try:
        monitor = get_scheduler_monitor()
        return {"status": "success", "data": monitor.get_latest_logs(lines=lines, minutes=minutes)}
    except Exception as exc:
        logger.error("Error getting scheduler logs: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@eshop.get("/scheduler/task/{task_name}", response_model=dict[str, Any])
async def scheduler_task_status(task_name: str):
    try:
        monitor = get_scheduler_monitor()
        return {"status": "success", "data": monitor.get_task_status(task_name)}
    except Exception as exc:
        logger.error("Error getting task status: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@eshop.get("/scheduler/stats", response_model=dict[str, Any])
async def scheduler_statistics():
    try:
        monitor = get_scheduler_monitor()
        return {"status": "success", "data": monitor.get_scheduler_stats()}
    except Exception as exc:
        logger.error("Error getting scheduler stats: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@eshop.get("/dashboard/overview", response_model=dict[str, Any])
async def dashboard_overview():
    try:
        store = _store()
        monitor = get_scheduler_monitor()
        return {
            "status": "success",
            "data": {
                "timestamp": datetime.utcnow().isoformat(),
                "scheduler_summary": monitor.get_scheduler_summary(),
                "recent_history": monitor.get_run_history(page=1, page_size=5)["items"],
                "system_stats": monitor.get_scheduler_stats(),
                "api_health": {
                    "status": "healthy",
                    "vector_backend": Config.VECTOR_BACKEND,
                    "qdrant_collection_size": store.collection_size(),
                    "redis_connected": _cache().is_connected(),
                    "api_version": Config.API_VERSION,
                },
            },
        }
    except Exception as exc:
        logger.error("Error getting dashboard overview: %s", exc)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "Content_Base_Model.recommendation_api:eshop",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
