# e-shop

Full-stack reference implementation of an e-commerce platform. It includes a Spring Boot API, public storefront and admin dashboards written in React, PostgreSQL + pgvector for persistence, MinIO for object storage, and a Python ETL pipeline for recommendation features.

## Repository layout

- `backend/e-shop/` — Spring Boot 3.5 service (Java 21, Maven, Flyway, JWT security, MinIO client, SpringDoc).
- `client/` — customer-facing React 19 + Vite + Tailwind application.
- `admin/` — staff/admin React 19 + Vite dashboard.
- `recomender/` — Python ETL utilities for analytics and recommendation experiments.
- `db/` — database assets (e.g., initialization scripts).
- `backend/e-shop/src/main/resources/db/migration/` — Flyway migrations.
- `backend/e-shop/src/main/resources/data/` — runtime data assets (Patagonia seed download lives here).
- `scripts/` — helper scripts (e.g., Patagonia catalog seeding).
- `docker-compose*.yml` — local orchestration for development (`docker-compose.yml`) and isolated test database (`docker-compose.test.yml`).

## Prerequisites

- Java 21+
- Maven 3.9+
- Node.js 20+ and npm (or pnpm) for the React apps
- Python 3.11+ for the recommender utilities
- Docker Desktop (compose v2) for the default local stack

## Quick start (Docker)

```bash
docker compose up --build
```

The compose stack provisions the following services:

- PostgreSQL 17 + pgvector on `localhost:5433` (user `app`, password `secret`, database `eshop`)
- Spring Boot API on `http://localhost:8080`
- MinIO on `http://localhost:9000` (console `http://localhost:9090`, credentials `admin` / `admin123`)

Shut everything down when finished:

```bash
docker compose down
```

### Environment configuration

Mail delivery (account activation, password reset) requires SMTP credentials. Two setups are supported:

- **Docker Compose / containers** – populate the repository-level `.env` file (already read by Docker Compose) with values such as `SPRING_MAIL_HOST`, `SPRING_MAIL_USERNAME`, `SPRING_MAIL_PASSWORD`, and `APP_MAIL_FROM`.
- **Running Spring Boot directly** – copy those same variables into `backend/e-shop/.env` (or `.env.properties`). Spring imports this file automatically and exposes the credentials to the mail sender.

## Manual setup

### Backend API

```bash
cd backend/e-shop
cp ../.env .env  # optional: reuse root .env for mail settings
./mvnw spring-boot:run
```

Configuration defaults live in `application.yml`. Override secrets via environment variables or a `.env.properties` file (Spring Boot will auto-load it).

Default credentials created on startup:

- Admin — `admin@gmail.com` / `123456`
- Demo customer (email already verified) — `demo.customer@eshop.local` / `123456`

Swagger UI is available at `http://localhost:8080/swagger-ui.html` once the service is running.

### Storefront (`client`)

```bash
cd client
npm install
npm run dev
```

The Vite dev server runs on `http://localhost:5173` and proxies API calls to the backend (`/api/` by default). Adjust environment values using Vite’s standard `.env` files.

### Admin dashboard

```bash
cd admin
npm install
npm run dev
```

The admin UI also runs on Vite (default port `http://localhost:5174` if available). Both front-ends expect the API at `http://localhost:8080`.

### Recommendation ETL

```bash
cd recomender
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python etl/run_etl.py
```

The ETL pipeline pulls interaction data, computes embeddings (CLIP optional), and writes processed datasets to `recomender/etl/data/processed`. Configure connection details via environment variables in `.env` (see `Config` in `etl/config.py` for defaults).

## Backend Docker image

The API image defined in `backend/e-shop/Dockerfile` uses a multi-stage build:

1. Builds the Spring Boot jar with Maven (tests skipped) inside the official Maven + Temurin 21 image.
2. Copies the jar into a lightweight Temurin 21 JRE base image and exposes port 8080.

Build and run it manually if you are not using Compose:

```bash
docker build -t e-shop-api backend/e-shop
docker run --rm -p 8080:8080 \
  -e SPRING_DATASOURCE_URL=jdbc:postgresql://host.docker.internal:5433/eshop \
  -e SPRING_DATASOURCE_USERNAME=app \
  -e SPRING_DATASOURCE_PASSWORD=secret \
  --env-file ./.env \
  e-shop-api
```

The `--env-file` flag reuses mail settings from the project root `.env`. Adjust database connectivity for your environment (e.g., production secrets, cloud Postgres).

## Database and migrations

- Flyway automatically applies migrations from `backend/e-shop/src/main/resources/db/migration` on startup.
- Use the generated schema overview in `backend/e-shop/src/main/resources/db/migration/dbdiagram.md` with tools like dbdiagram.io if you need diagrams.

### Sample data

For deterministic demos the repository ships a helper script that prepares the catalog and loads the Patagonia dataset distributed through GitHub Releases.

```bash
chmod +x scripts/load_patagonia_seed.sh
./scripts/load_patagonia_seed.sh
```

What the script does:

1. Verifies that `backend/e-shop/target/classes/db/clean_catalog.sql` exists (run `./mvnw package` once if it does not).
2. Downloads `patagonia_seed_2025-10-05.sql` from [GitHub Releases](https://github.com/finnzxje/e-shop/releases/tag/seed-2025-10-05) into `backend/e-shop/src/main/resources/data` (skipped when already present).
3. Runs the cleanup SQL to clear catalog tables.
4. Loads the Patagonia seed into the target database (`postgres://app:secret@localhost:5433/eshop` by default). Override the connection with `DATABASE_URL=postgres://... ./scripts/load_patagonia_seed.sh`.

## Testing

Spin up an isolated PostgreSQL instance for integration tests:

```bash
docker compose -f docker-compose.test.yml up -d
```

Run the backend tests:

```bash
cd backend/e-shop
./mvnw test
```

React apps rely on unit/component tests you add (Jest, Vitest, etc.); configure them under each package.

Stop the test database when done:

```bash
docker compose -f docker-compose.test.yml down
```

# e-shop

## Development

Run the API with its development database:

```
docker compose up --build
```

Stop the stack when you are done:

```
docker compose down
```

## Testing

Start the isolated PostgreSQL instance for integration tests:

```
docker compose -f docker-compose.test.yml up -d
```

Tear it down after tests complete:

```
docker compose -f docker-compose.test.yml down
```

# RECOMMENDATION SYSTEM

## 1. Introduction

This Recommendation System (RS) is designed to provide personalized suggestions for products, content, or services based on item features and user interactions. The project leverages modern techniques such as:

- **Content-based filtering**: Recommends items similar to the ones the user has interacted with, based on item features.
- **Collaborative filtering**: Suggests items based on user behavior and interaction patterns.
- **Hybrid approaches**: Combines content-based and collaborative filtering to improve recommendation accuracy.

Use cases include:

- E-commerce (product recommendations)
- Media platforms (video, article, music suggestions)
- Social applications (friend or content suggestions)

---

## 2. System Architecture

    Product Data
    │
    ├─── Images + Text ────→ CLIP ────→ 512D embedding
    │
    └─── Metadata ─────────→ BERT ────→ 512D embedding
         (category, color,
          price, rating)
                    │
                    ↓
        Hybrid = α × CLIP + (1-α) × BERT
                    │
                    ↓ (L2 normalize)
                    │
        ┌───────────┴───────────┐
        ↓                       ↓
    FAISS Index          PostgreSQL (backup)
        ↓
    FastAPI Server ← Redis Cache
        ↓
    REST API Endpoints

- **Feature Extraction**:

  - `CLIP` is used to generate embeddings from images and textual descriptions.
  - `BERT` is used to extract embeddings from textual product descriptions.

- **Vector Indexing**:

  - FAISS is used to store and quickly search through vector embeddings.

- **Recommendation Logic**:

  - Returns items with the closest vector distances in the embedding space.
  - Can be extended to Hybrid Filtering when user interaction data is available.

- **Caching**:
  - Redis is used for caching recommendation results to improve response time.

---

## 3. Installation

### 3.1 Requirements

- Python >= 3.10
- CUDA (if using GPU for FAISS)
- Python libraries:

```bash
pip install -r requirements.txt
```

### 3.2 Environment Setup

- Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

- Install dependencies:

```bash
pip install -r requirements.txt
```

## 4. Usage

### Step 1: Run ETL pipeline

```bash
cd recomender/etl
python3 run_etl.py
```

### Step 2: Run Clip Embedding (embedding item feature in database to np file)

```bash
python3 clip_embedding_pipeline.py
```

### Step 3: Run Bert embedding and test recommender system

```bash
cd Content_Base_Model
python3 workFlow.py
```

### Step 4: Run build Faiss Index and API

```bash
python3 build_faiss_index.py
python3 faiss_api.py
# or
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

### Step 5: Test API

```bash
python3 testAPI.py
```

---

## 5. Hybrid Recommendation API Documentation

### Base URL

```
http://localhost:8000
```

### Overview

The API is built with FastAPI and powered by CLIP and BERT hybrid embeddings, using FAISS for vector similarity search and Redis for caching. It supports both single and batch recommendation requests, along with system monitoring endpoints.

#### Key Features

- **Hybrid embeddings** using CLIP (visual) and BERT (textual)
- **Fast similarity search** with FAISS indexing
- **Caching layer** with Redis for improved performance
- **Batch processing** for multiple recommendations
- **Health monitoring** and statistics endpoints

---

## 6. API Endpoints

### 6.1 Root Endpoint

**`GET /`**

Simple endpoint to verify that the API is running.

**Example Request:**

```bash
curl -X GET http://localhost:8000/
```

**Response:**

```json
{
  "message": "Hybrid Recommendation API",
  "version": "1.0.0",
  "docs": "/docs"
}
```

---

### 6.2 Health Check

**`GET /health`**

Returns current system status, FAISS index size, Redis connection status, and embedding dimension.

**Example Request:**

```bash
curl -X GET http://localhost:8000/health
```

**Response:**

```json
{
  "status": "healthy",
  "timestamp": "2025-11-06T09:33:20.123Z",
  "faiss_index_size": 19350,
  "redis_connected": true,
  "version": "1.0.0",
  "embedding_dimension": 512
}
```

---

### 6.3 Single Product Recommendation

**`GET /recommend/{product_id}`**

Returns a list of similar products for a given product ID.

**Path Parameters:**

| Name         | Type   | Description                                     |
| ------------ | ------ | ----------------------------------------------- |
| `product_id` | string | UUID of the product to find recommendations for |

**Query Parameters:**

| Name | Type | Default | Description                       |
| ---- | ---- | ------- | --------------------------------- |
| `k`  | int  | `5`     | Number of similar items to return |

**Example Request:**

```bash
curl -X GET "http://localhost:8000/recommend/2b6ae79d-4169-415e-8b53-d9e87c832240?k=5"
```

**Response:**

```json
{
  "query_product_id": "2b6ae79d-4169-415e-8b53-d9e87c832240",
  "recommendations": [
    {
      "product_id": "7614d53a-2ea1-4da4-b0b2-3bc196f1a804",
      "similarity_score": 0.9896,
      "product_name": "Áo thun thể thao",
      "category_name": "Thời trang nam",
      "price": 199000,
      "image_path": "/images/men_sport_tee.jpg"
    }
  ],
  "response_time_ms": 22.45,
  "from_cache": false,
  "total_results": 5
}
```

**Use Case:**

> Use this endpoint to recommend similar products when a user views a product detail page. The response can be directly consumed by frontend applications or backend services (e.g., Spring Boot).

---

### 6.4 Batch Recommendation

**`POST /recommend/batch`**

Get recommendations for multiple product IDs in a single request, optimizing performance for batch operations.

**Request Body:**

```json
{
  "product_ids": [
    "2b6ae79d-4169-415e-8b53-d9e87c832240",
    "7614d53a-2ea1-4da4-b0b2-3bc196f1a804"
  ],
  "k": 5
}
```

**Example Request:**

```bash
curl -X POST http://localhost:8000/recommend/batch \
  -H "Content-Type: application/json" \
  -d '{
    "product_ids": [
      "2b6ae79d-4169-415e-8b53-d9e87c832240",
      "7614d53a-2ea1-4da4-b0b2-3bc196f1a804"
    ],
    "k": 5
  }'
```

**Response:**

```json
{
  "results": {
    "2b6ae79d-4169-415e-8b53-d9e87c832240": {
      "recommendations": [
        {
          "product_id": "7614d53a-2ea1-4da4-b0b2-3bc196f1a804",
          "similarity_score": 0.98
        }
      ],
      "total_results": 5
    }
  },
  "response_time_ms": 44.21,
  "total_queries": 2
}
```

---

### 6.5 FAISS Statistics

**`GET /stats`**

Retrieve system and FAISS configuration details including index size, cache settings, and technical parameters.

**Example Request:**

```bash
curl -X GET http://localhost:8000/stats
```

**Response:**

```json
{
  "total_products": 19350,
  "index_type": "Flat",
  "embedding_dimension": 512,
  "redis_enabled": true,
  "cache_ttl_seconds": 3600,
  "max_k": 100
}
```

**Response Fields:**

| Field                 | Description                                         |
| --------------------- | --------------------------------------------------- |
| `total_products`      | Total number of products indexed in FAISS           |
| `index_type`          | FAISS index type (e.g., "Flat")                     |
| `embedding_dimension` | Dimension of embedding vectors (512)                |
| `redis_enabled`       | Whether Redis caching is active                     |
| `cache_ttl_seconds`   | Cache time-to-live in seconds                       |
| `max_k`               | Maximum number of recommendations allowed per query |

---

## 7. Technical Details

### 7.1 Architecture Overview

The API uses a hybrid approach combining:

1. **CLIP embeddings** - For visual similarity based on product images
2. **BERT embeddings** - For textual similarity based on descriptions
3. **FAISS indexing** - For efficient nearest neighbor search
4. **Redis caching** - For improved response times on repeated queries

### 7.2 Performance Characteristics

- **Average response time**: ~20-50ms for single queries
- **Cache hit benefit**: ~5-10x faster response
- **Batch efficiency**: Process multiple queries with minimal overhead
- **Scalability**: Handles 19,350+ products with sub-second response times

### 7.3 Best Practices

> **Recommendations:**
>
> - Use batch endpoints when requesting recommendations for multiple products
> - Monitor the `/health` endpoint for system status
> - Consider implementing client-side caching for frequently accessed products
> - Set appropriate `k` values based on your UI requirements (default: 5)
> - Handle timeout scenarios gracefully in production environments

### 7.4 Error Handling

The API returns standard HTTP status codes:

| Status Code | Description                                         |
| ----------- | --------------------------------------------------- |
| 200         | Successful request                                  |
| 400         | Bad request (invalid parameters)                    |
| 404         | Product not found                                   |
| 500         | Internal server error                               |
| 503         | Service unavailable (FAISS/Redis connection issues) |

---

## License

[Your License Here]

## Contributors

[Your Contributors Here]
