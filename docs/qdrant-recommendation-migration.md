# Qdrant Recommendation Migration

Ngay tao: 2026-05-01

## Muc Tieu

Chuyen runtime vector search cua recommendation service tu FAISS sang Qdrant, trong khi Postgres van la source of truth cho catalog/order/cart.

FAISS duoc giu lai nhu legacy benchmark/rollback path, khong con la runtime mac dinh cua API.

## Data Flow

```text
Postgres catalog/order data
  -> ETL export item_features.csv
  -> CLIP/BERT hybrid embeddings
  -> hybrid_embeddings.npy + hybrid_variant_ids.npy
  -> build_qdrant_index.py
  -> Qdrant collection product_variants_v1
```

Runtime:

```text
Spring Boot API
  -> Recommendation API /recommend/{variant_id}
  -> Qdrant vector search
  -> response keeps variant_id + metadata for backend enrichment
```

## Files Chinh

- `recomender/etl/Content_Base_Model/qdrant_vector_store.py`: Qdrant client, collection rebuild, vector upsert, search.
- `recomender/etl/Content_Base_Model/build_qdrant_index.py`: CLI rebuild collection tu hybrid embeddings.
- `recomender/etl/Content_Base_Model/recommendation_api.py`: FastAPI runtime moi, giu endpoint recommendation cu.
- `recomender/Docker/docker-compose.yml`: them service `qdrant`, doi API sang `recommendation_api`.
- `recomender/Docker/entrypoint.sh`: them command `build-qdrant`, API check source data Qdrant.
- `recomender/Docker/smart_pipeline.sh`: smart pipeline build Qdrant collection sau hybrid workflow.
- `recomender/etl/scheduler.py`: scheduler task sau BERT/hybrid doi sang `qdrant_index`.

## Commands

```bash
cd recomender/Docker
docker compose up -d qdrant redis postgres
docker compose --profile build-index up build-qdrant
docker compose up -d api
```

Hoac dung Makefile:

```bash
cd recomender
make build-index
make api
```

## API Compatibility

Endpoint giu nguyen:

- `GET /health`
- `GET /recommend/{variant_id}?k=10`
- `POST /recommend/batch`
- `GET /stats`

`/health` co them field Qdrant:

```json
{
  "vector_backend": "qdrant",
  "qdrant_collection": "product_variants_v1",
  "qdrant_collection_size": 19350
}
```

`faiss_index_size` tam thoi van duoc tra ve bang collection size de khong lam hong client/test cu nao dang doc field nay.

## Review Notes

- Qdrant point id la UUID5 tu `variant_id`; `variant_id` goc nam trong payload. Cach nay tranh loi neu ID san pham khong phai UUID hop le cua Qdrant.
- Qdrant payload chi dung cho filter/ranking so bo. Gia, ton kho, permission va mutation van nen validate lai tu Postgres/Spring Boot.
- Redis cache key da them prefix `rec:qdrant:{collection}` de khong dung lai cache FAISS cu.
- FAISS builder cu van giu qua profile `legacy-faiss` de benchmark/rollback.
