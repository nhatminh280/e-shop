# Deploying The Backend to DigitalOcean

This guide is for the setup where your frontend is already hosted elsewhere, such as Cloudflare Pages, and you only want to run the Spring Boot API on DigitalOcean.

Use `.do/backend-app.yaml` for a backend-only App Platform deployment.

## Recommended architecture

1. Keep the storefront and admin on Cloudflare.
2. Deploy the Spring Boot API to DigitalOcean App Platform using `.do/backend-app.yaml`.
3. Use DigitalOcean Managed PostgreSQL for the app database.
4. Use DigitalOcean Spaces for product media uploads.
5. Leave `RECOMMENDATION_ENABLED=false` until the Python recommender is deployed separately.

## Required cloud resources

### PostgreSQL

Recommended: use a DigitalOcean Managed PostgreSQL cluster in the same region as the API app.

For the current backend code, plain PostgreSQL is enough to boot and run Flyway migrations. `pgvector` is only needed if you later store vector embeddings in PostgreSQL for the recommender pipeline.

Create the cluster either in the control panel or with `doctl`:

```bash
doctl databases create eshop-db --engine pg --region nyc --size db-s-1vcpu-1gb --num-nodes 1
```

Then create the application database inside that cluster:

```bash
doctl databases list
doctl databases db create <cluster-id> eshop
```

Fetch the connection details:

```bash
doctl databases connection <cluster-id>
```

Use the values from that command to populate:

- `SPRING_DATASOURCE_URL=jdbc:postgresql://<host>:25060/eshop?sslmode=require`
- `SPRING_DATASOURCE_USERNAME=<user>`
- `SPRING_DATASOURCE_PASSWORD=<password>`

If you attach the database to the App Platform app in the DigitalOcean dashboard, add the app as a trusted source on the database cluster. If trusted sources are enabled, the app must be explicitly allowed to connect.

If you plan to use the recommender pipeline with PostgreSQL vector storage later, enable the `vector` extension after the database is created:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Then either import your existing schema/data or let Flyway migrate a fresh database on first boot.

Notes:

- DigitalOcean Managed PostgreSQL requires SSL in transit; keep `sslmode=require` in the JDBC URL.
- Flyway will create the backend tables automatically on first startup.
- The current backend migrations already create `pgcrypto` and `uuid-ossp` where needed; you do not need to create those manually.

### Spaces

Create a bucket such as `eshop-products` in the same region as the API if possible.

Required values:

- `STORAGE_MINIO_ENDPOINT=https://<region>.digitaloceanspaces.com`
- `STORAGE_MINIO_BUCKET=<bucket-name>`
- `STORAGE_MINIO_REGION=<region>`
- `STORAGE_MINIO_PUBLIC_URL=https://<region>.digitaloceanspaces.com`

Create the bucket in the DigitalOcean control panel first, then generate Spaces access keys and set:

- `STORAGE_MINIO_ACCESS_KEY=<spaces-access-key>`
- `STORAGE_MINIO_SECRET_KEY=<spaces-secret-key>`

Important:

- This backend uses the MinIO client against any S3-compatible object store. On DigitalOcean, that means Spaces, not a separate MinIO server.
- In the current code, `STORAGE_MINIO_PUBLIC_URL` is a base endpoint. The app appends `/<bucket>/<objectKey>` when building public image URLs.
- If you use a CDN or custom domain later, keep that URL format in mind.

## Backend env vars you need to set

These are the production values that matter most when the frontend lives on Cloudflare:

- `SPRING_DATASOURCE_URL=jdbc:postgresql://<host>:25060/<db>?sslmode=require`
- `SPRING_DATASOURCE_USERNAME=<db-user>`
- `SPRING_DATASOURCE_PASSWORD=<db-password>`
- `JWT_SECRET=<long-random-secret>`
- `APP_CORS_ALLOWED_ORIGIN_PATTERNS=https://<your-storefront-domain>,https://<your-admin-domain>`
- `APP_ACTIVATION_BASE_URL=https://<your-storefront-domain>/auth/activate`
- `VNPAY_RETURN_URL=https://<your-storefront-domain>/payment-result`
- `SPRING_MAIL_HOST`, `SPRING_MAIL_PORT`, `SPRING_MAIL_USERNAME`, `SPRING_MAIL_PASSWORD`
- `APP_MAIL_FROM=<sender you want in outgoing mail>`
- `STORAGE_MINIO_ENDPOINT`, `STORAGE_MINIO_ACCESS_KEY`, `STORAGE_MINIO_SECRET_KEY`
- `STORAGE_MINIO_BUCKET`, `STORAGE_MINIO_REGION`, `STORAGE_MINIO_PUBLIC_URL`
- `RECOMMENDATION_ENABLED=false`

Important:

- `APP_CORS_ALLOWED_ORIGIN_PATTERNS` must include every browser origin that will call the API or open `/ws`.
- `APP_ACTIVATION_BASE_URL` must point to the frontend route, not the backend route.
- `VNPAY_RETURN_URL` must also point to the frontend, because the browser is redirected back there after payment.

## App Platform setup

### 1. Push this repo to GitHub

The App Platform spec assumes DigitalOcean will build from GitHub. Update these fields in `.do/backend-app.yaml`:

- `github.repo`
- `github.branch`

### 2. Edit `.do/backend-app.yaml`

Replace the placeholder values for:

- database host, name, username, and password
- `JWT_SECRET`
- SMTP credentials
- `APP_CORS_ALLOWED_ORIGIN_PATTERNS`
- `APP_ACTIVATION_BASE_URL`
- Spaces access keys and bucket values
- `VNPAY_RETURN_URL` if you use VNPAY

Keep `RECOMMENDATION_ENABLED=false` unless you also deploy the Python recommender and set `RECOMMENDER_BASE_URL`.

### 3. Create the app

You can create the API from the DigitalOcean control panel or with `doctl`:

```bash
doctl apps create --spec .do/backend-app.yaml
```

### 4. Attach the API domain

A typical hostname is:

- `api.shop.example.com`

After the domain is active, update these frontend values in Cloudflare Pages:

- storefront `VITE_API_BASE_URL=https://api.shop.example.com`
- storefront `VITE_SOCKET_URL=https://api.shop.example.com/ws`
- admin `VITE_API_BASE_URL=https://api.shop.example.com`
- admin `VITE_SOCKET_URL=https://api.shop.example.com/ws`

Also make sure the backend `APP_CORS_ALLOWED_ORIGIN_PATTERNS` contains the final Cloudflare frontend origins.

## Verification checklist

After deployment, verify:

1. `https://<api-domain>/actuator/health` returns `UP`.
2. The storefront can register and log in against the DigitalOcean API.
3. Account activation emails send users to the Cloudflare frontend domain.
4. Product image uploads land in Spaces and public image URLs load correctly.
5. Support chat connects through `https://<api-domain>/ws`.
6. If VNPAY is enabled, payment returns land on the frontend domain, not the API domain.

## Notes

- The backend now honors `RECOMMENDATION_ENABLED`, so you can safely disable the recommender in production until that service has its own deployment.
