# Deploying E-Shop to DigitalOcean

This repository is set up for a practical DigitalOcean App Platform deployment using two apps:

- `storefront-app.yaml` for the public storefront and Spring Boot API
- `admin-app.yaml` for the admin dashboard on its own hostname

The admin app is split out intentionally because its router currently assumes it runs at the domain root, not under a `/admin` subpath.

## What changed in the repo

- Frontend API and WebSocket endpoints are now environment-driven via `VITE_API_BASE_URL` and `VITE_SOCKET_URL`.
- Backend HTTP/WebSocket allowed origins now come from `APP_CORS_ALLOWED_ORIGIN_PATTERNS`.
- App Platform specs live in `.do/`.

## Recommended architecture

1. Create a managed PostgreSQL cluster on DigitalOcean and use it for the Spring Boot API.
2. Create a Spaces bucket for product media and point the backend’s MinIO-compatible storage settings at it.
3. Deploy the public storefront and API as one App Platform app using `.do/storefront-app.yaml`.
4. Deploy the admin dashboard as a second App Platform app using `.do/admin-app.yaml`.
5. Leave `RECOMMENDATION_ENABLED=false` until you deploy the Python recommender separately.

## Required cloud resources

### PostgreSQL

This app uses `pgvector`, so enable the extension after the database is created:

```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

Then import your schema or let Flyway migrate a fresh database.

### Spaces

Create a bucket such as `eshop-products` in the same region as your apps if possible. Use:

- `STORAGE_MINIO_ENDPOINT=https://<region>.digitaloceanspaces.com`
- `STORAGE_MINIO_BUCKET=<bucket-name>`
- `STORAGE_MINIO_REGION=<region>`
- `STORAGE_MINIO_PUBLIC_URL=https://<bucket-name>.<region>.digitaloceanspaces.com`

If you enable the Spaces CDN, set `STORAGE_MINIO_PUBLIC_URL` to the CDN hostname instead.

## App Platform setup

### 1. Push this repo to GitHub

Both app specs assume DigitalOcean will build from a GitHub repository. Update:

- `github.repo`
- `github.branch`

inside both files in `.do/`.

### 2. Edit `.do/storefront-app.yaml`

Replace the placeholder values for:

- database host, database name, username, and password
- `JWT_SECRET`
- SMTP credentials
- `APP_CORS_ALLOWED_ORIGIN_PATTERNS`
- `APP_ACTIVATION_BASE_URL`
- Spaces access keys and bucket values
- `VNPAY_RETURN_URL` if you use VNPAY

Keep `RECOMMENDATION_ENABLED=false` unless you also deploy the Python API and set `RECOMMENDER_BASE_URL`.

### 3. Edit `.do/admin-app.yaml`

Set:

- `VITE_API_BASE_URL=https://<your-storefront-domain>`
- `VITE_SOCKET_URL=https://<your-storefront-domain>/ws`

### 4. Create the apps

You can create both apps from the DigitalOcean control panel or with `doctl`:

```bash
doctl apps create --spec .do/storefront-app.yaml
doctl apps create --spec .do/admin-app.yaml
```

### 5. Attach domains

Recommended hostnames:

- `eshop.example.com` or `www.example.com` for the storefront app
- `admin.eshop.example.com` for the admin app

After the domains are active, update:

- `APP_CORS_ALLOWED_ORIGIN_PATTERNS`
- `APP_ACTIVATION_BASE_URL`
- `VNPAY_RETURN_URL`
- admin `VITE_API_BASE_URL`
- admin `VITE_SOCKET_URL`

to use the final production URLs.

## Verification checklist

After deployment, verify:

1. `https://<storefront-domain>/actuator/health` returns `UP`.
2. Storefront login, registration, and account activation emails work.
3. Admin login works from the admin hostname.
4. Product image uploads land in Spaces and public image URLs load correctly.
5. Support chat connects through `/ws`.
6. Payment return URLs point back to the storefront domain.

## Optional next step: recommender service

The Python recommender is not included in the App Platform specs yet. Its dependency stack is much heavier than the Java and Vite apps, so the safest first production cut is to ship without it and re-enable recommendations after the service has its own deployment target and health checks.
