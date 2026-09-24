# Production Deployment

Phase 22 — making AI Brand Intelligence **production-deployable**.

This document describes the intended production architecture, how to run a local production simulation with Docker Compose, and what remains an **operator responsibility** (TLS certificates, backups, managed databases, platform choice).

**This repository does not claim that a live production deployment was performed.** Deploy and verify on your infrastructure.

---

## Architecture

### Production topology

```text
                    ┌───────────────┐
                    │    Browser    │
                    └───────┬───────┘
                            │ HTTPS
                            ▼
                  ┌───────────────────┐
                  │ Reverse Proxy /   │
                  │ TLS Termination   │
                  └───────┬───────────┘
                          │
             ┌────────────┴────────────┐
             │                         │
             ▼                         ▼
     Angular static assets       FastAPI API
                                      │
                         ┌────────────┼────────────┐
                         ▼            ▼            ▼
                    PostgreSQL      Redis      Reports storage
```

| Path | Handled by |
| --- | --- |
| `/` and SPA routes | Angular static assets (nginx) |
| `/api/` | FastAPI |
| PostgreSQL / Redis | Private Docker network only |

Browser → same origin `/api/v1` → reverse proxy → backend. The Angular bundle uses `apiBaseUrl: '/api/v1'` and never embeds backend secrets or internal hostnames.

### Local development vs production

| Concern | Local development (`docker-compose.yml`) | Production (`docker-compose.prod.yml`) |
| --- | --- | --- |
| Frontend | `ng serve` (Dockerfile target `development`) | Static nginx (target `production`) |
| Backend | Uvicorn, auto-migrate on start | Uvicorn workers, migrations explicit by default |
| PostgreSQL ports | Published `5432:5432` | **Not published** |
| Redis ports | Published `6379:6379` | **Not published** |
| Cookies | `COOKIE_SECURE=false` allowed | `COOKIE_SECURE=true` required |
| JWT | Dev placeholder allowed | Strong unique secret required |
| CORS | localhost origins | Explicit production origin(s) only |
| Source mounts | None (image build) | None (image build) |
| Reports | Volume `reports_data` | Volume `reports_data` (persistent) |

Redis is reserved for future queue/cache use. The API does **not** require Redis at startup for core product behavior.

---

## Requirements

- Docker and Docker Compose
- PostgreSQL 16 (Compose service or managed)
- Redis 7 (optional for current product features; keep private)
- Reverse proxy capable of TLS termination (nginx, Caddy, cloud LB, etc.)
- HTTPS in production (assumed for secure cookies)

---

## Environment variables

Placeholders only — never commit real secrets. Full development template: `.env.example`.

| Name | Purpose | Required? | Example placeholder | Secret? |
| --- | --- | --- | --- | --- |
| `ENVIRONMENT` | Runtime mode; `production` enables fail-fast security checks | Yes (prod) | `production` | No |
| `JWT_SECRET` | Signs auth JWTs (≥32 chars, not a known default) | Yes | `replace-with-a-long-random-secret-at-least-32-chars` | **Yes** |
| `COOKIE_SECURE` | Sets `Secure` on auth cookie | Yes (prod=`true`) | `true` | No |
| `COOKIE_SAMESITE` | Cookie SameSite (`lax` recommended) | Yes | `lax` | No |
| `COOKIE_NAME` | Auth cookie name | No | `ai_brand_access_token` | No |
| `DATABASE_URL` | PostgreSQL SQLAlchemy URL | Yes | `postgresql://brand_app:CHANGE_ME_DB_PASSWORD@postgres:5432/brand_intelligence` | **Yes** |
| `POSTGRES_USER` | DB role for Compose Postgres | Yes (Compose) | `brand_app` | No |
| `POSTGRES_PASSWORD` | DB password | Yes (Compose) | `CHANGE_ME_DB_PASSWORD` | **Yes** |
| `POSTGRES_DB` | Database name | Yes (Compose) | `brand_intelligence` | No |
| `CORS_ORIGINS` | Comma-separated explicit browser origins (no `*`) | Yes | `https://app.example.com` | No |
| `REDIS_URL` | Redis URL (future use) | No | `redis://redis:6379/0` | Optional |
| `REPORTS_DIR` | PDF report storage directory | Yes | `/data/reports` | No |
| `AI_PROVIDER` | `mock` or `openai` | No | `openai` | No |
| `OPENAI_API_KEY` | Provider API key | If OpenAI | `sk-replace-me` | **Yes** |
| `OPENAI_MODEL` | Model name | No | `gpt-4o-mini` | No |
| `OPENAI_TIMEOUT_SECONDS` | Provider timeout | No | `30` | No |
| `API_PREFIX` | API path prefix | No | `/api/v1` | No |
| `RUN_MIGRATIONS_ON_START` | Auto `alembic upgrade head` on container start | No | `false` | No |
| `WEB_CONCURRENCY` | Uvicorn worker count | No | `2` | No |
| `PORT` | Backend listen port | No | `8000` | No |
| `FRONTEND_PUBLISH_PORT` | Host port for frontend in prod compose | No | `8080` | No |
| Crawler / SEO vars | See `.env.example` | No | (defaults) | No |

**Never** put `OPENAI_API_KEY`, `JWT_SECRET`, or `DATABASE_URL` into Angular environment files.

### Database credentials (production)

Prefer a dedicated application role (not the `postgres` superuser):

| Item | Placeholder |
| --- | --- |
| Database name | `brand_intelligence` |
| Application user | `brand_app` |
| Password | supplied via secret / env (never committed) |
| Connection string | `postgresql://brand_app:CHANGE_ME_DB_PASSWORD@postgres:5432/brand_intelligence` |

---

## HTTPS / cookies

Production assumes HTTPS terminated at the reverse proxy (see `deploy/nginx.conf`).

Application cookie settings:

- `COOKIE_SECURE=true`
- `SameSite=Lax` (`COOKIE_SAMESITE=lax`)
- `HttpOnly=true` (always set by the API)

Do not generate or manage TLS certificates inside application containers.

---

## CORS

Configure explicit origins, for example:

```text
CORS_ORIGINS=https://app.example.com
```

For local production simulation with the Compose frontend on port 8080:

```text
CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
```

Wildcard `*` is rejected. Credentials remain enabled for the cookie session.

---

## Local production simulation

Exact commands (from the repository root):

```bash
# 1. Create a production env file (do not commit)
cp .env.example .env.prod
# Edit .env.prod:
#   ENVIRONMENT=production
#   JWT_SECRET=<strong unique secret ≥32 chars>
#   COOKIE_SECURE=true
#   COOKIE_SAMESITE=lax
#   POSTGRES_USER=brand_app
#   POSTGRES_PASSWORD=<strong password>
#   POSTGRES_DB=brand_intelligence
#   DATABASE_URL=postgresql://brand_app:<strong password>@postgres:5432/brand_intelligence
#   CORS_ORIGINS=http://localhost:8080,http://127.0.0.1:8080
#   REPORTS_DIR=/data/reports
#   RUN_MIGRATIONS_ON_START=false

# 2. Build
docker compose -f docker-compose.prod.yml --env-file .env.prod build

# 3. Migrate (explicit — preferred)
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm backend alembic upgrade head

# 4. Start
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# 5. Health
curl -fsS http://localhost:8080/api/v1/health
# Expect: {"status":"ok"}

# Frontend: http://localhost:8080
# Deep routes (SPA fallback): /login /dashboard /brands /reports ...
```

Note: production requires `COOKIE_SECURE=true`. Chromium treats `http://localhost` as a secure context for cookies, so local auth smoke tests usually work on localhost without TLS. Other browsers or non-localhost hosts need real HTTPS.


Development stack (unchanged):

```bash
docker compose up --build
```

---

## Database migrations

Safe forward migration only:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm backend alembic upgrade head
```

- Does **not** recreate tables or drop data.
- Prefer this **explicit** step in production.
- Optional: set `RUN_MIGRATIONS_ON_START=true` so the entrypoint runs `alembic upgrade head` before Uvicorn.

**Tradeoff of automatic startup migration:** simpler deploys, but couples schema changes to every container start and can surprise multi-replica rollouts. Prefer explicit migrate-then-start when practical.

Never run destructive downgrades automatically.

---

## Build / start / health / logs

```bash
# Build
docker compose -f docker-compose.prod.yml --env-file .env.prod build

# Start
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d

# Health (via frontend same-origin proxy)
curl -fsS http://localhost:8080/api/v1/health

# Logs
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f backend
docker compose -f docker-compose.prod.yml --env-file .env.prod logs -f frontend
```

Health endpoint: `GET /api/v1/health` → `{"status":"ok"}` (liveness only; does not fail when optional AI providers are down; does not expose secrets).

---

## Persistent storage

| Volume | Mount | Purpose |
| --- | --- | --- |
| `postgres_data` | Postgres data dir | Survives container restart/recreation |
| `reports_data` | `/data/reports` (`REPORTS_DIR`) | PDF reports survive recreation |

Reports are **not** stored in the image layer. Database backups alone do **not** restore report PDFs if report storage is separate — back up both.

The backend container runs as UID/GID `1000` (`app`). If a fresh volume is not writable, fix ownership once:

```bash
docker compose -f docker-compose.prod.yml --env-file .env.prod run --rm --user root backend \
  chown -R app:app /data/reports
```

---

## Reverse proxy

Example configuration: [`deploy/nginx.conf`](../deploy/nginx.conf).

It documents:

- TLS termination (certificates on the proxy/host, not in app images)
- `/` → frontend
- `/api/` → backend
- `client_max_body_size 1m` (aligned with backend 1 MiB body limit)
- Security headers
- No public caching of API responses
- Long cache for hashed static assets; short/no-cache for `index.html` (configured in `frontend/nginx.conf`)

Platforms with a built-in load balancer may use equivalent settings instead of bundling this file.

---

## Resource starting points (guidance)

| Resource | Starting point |
| --- | --- |
| Backend CPU | 0.5–1 vCPU |
| Backend memory | 512 MiB–1 GiB |
| Frontend CPU/memory | 0.25 vCPU / 128–256 MiB |
| PostgreSQL storage | 10+ GiB (grows with audits) |
| Report storage | 5+ GiB (grows with PDF exports) |
| Uvicorn workers | `WEB_CONCURRENCY=2` |

Tune for traffic; do not treat these as hard limits.

---

## Observability

Lightweight only:

- Structured-ish application logs to stdout (method, path, status — no cookies/JWTs/API keys)
- Startup log includes environment and `cookie_secure`, not secrets
- Container logs via `docker compose logs`
- `GET /api/v1/health`

Do not log passwords, cookies, JWTs, API keys, or DB credentials.

---

## Graceful shutdown

Uvicorn handles `SIGTERM`. On shutdown the app lifespan disposes the SQLAlchemy engine. Synchronously generated reports either complete or fail cleanly within the request; they are not left in a half-written DB row without a matching file when generation fails (existing Phase 18 behavior).

---

## Rollback

### Application rollback

Redeploy the previous known-good image/tag and restart Compose (or your platform’s previous revision).

### Database rollback

Prefer **forward-compatible** migrations. Do **not** automatically `alembic downgrade`. If a migration must be reversed, plan a new forward migration after backup restore testing.

### Reports

Existing PDF files under `REPORTS_DIR` should remain readable across app rollbacks when the storage layout is unchanged.

---

## Backup / recovery (recommendations)

| Asset | Recommendation |
| --- | --- |
| PostgreSQL | Scheduled `pg_dump` or managed automated backups; test restore periodically |
| Report files | Snapshot/sync the reports volume or object storage |
| Restore testing | Restore DB + reports together into a staging environment |

Database backups alone do not restore report PDFs when report storage is separate.

---

## Security checklist

See also [security.md](security.md) (Phase 21).

| Item | Owner |
| --- | --- |
| [ ] HTTPS | **Infrastructure** |
| [ ] strong `JWT_SECRET` | **Operator** (validated by app in production) |
| [ ] `COOKIE_SECURE=true` | **Operator** (validated by app) |
| [ ] restricted CORS | **Operator** (validated by app) |
| [ ] private PostgreSQL | **Repository** (`docker-compose.prod.yml`) |
| [ ] private Redis | **Repository** (`docker-compose.prod.yml`) |
| [ ] persistent PostgreSQL volume | **Repository** |
| [ ] persistent report storage | **Repository** |
| [ ] migrations | **Operator** (commands documented; optional auto-start) |
| [ ] non-root containers | **Repository** (backend `app` user; frontend unprivileged nginx) |
| [ ] production frontend server | **Repository** (nginx, not `ng serve`) |
| [ ] reverse proxy | **Infrastructure** (example in `deploy/nginx.conf`) |
| [ ] health checks | **Repository** |
| [ ] request limits (1 MiB) | **Repository** (+ proxy example) |
| [ ] no secrets in images | **Repository** (`.dockerignore`, no `.env` COPY) |
| [ ] no debug / reload | **Repository** |
| [ ] logs reviewed | **Operator** |
| [ ] backups configured | **Infrastructure / Operator** |

---

## CI

Minimal GitHub Actions workflow: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml)

- Backend pytest
- Frontend unit tests + production build
- Docker image builds (backend + frontend production target)

CI does **not** deploy to production.

---

## Deployment platforms (guidance only — not verified here)

### VPS

Install Docker, copy the repo, configure `.env.prod`, put nginx/Caddy in front with TLS (Let’s Encrypt), run Compose prod commands above.

### Managed container platform

Build/push images from `backend/Dockerfile` and `frontend` production target. Attach managed PostgreSQL (`DATABASE_URL`), persistent volume for reports, private network, and platform ingress for HTTPS. Keep Redis private if provisioned.

### Managed PostgreSQL

Point `DATABASE_URL` at the managed instance. Run `alembic upgrade head` as a release job. Do not expose the database to the public internet.

---

## Production configuration validation

On `ENVIRONMENT=production`, the app **fails fast** (Phase 21 rules, extended for DB) when:

- JWT secret is weak, short, or a known default
- `COOKIE_SECURE=false`
- CORS is empty or contains `*`
- `DATABASE_URL` is missing, SQLite, or not PostgreSQL

Repeatable tests: `backend/tests/test_production_config.py`.

---

## Remaining manual deployment steps

1. Provision a host or managed container platform with Docker (or equivalent).
2. Create secrets (`JWT_SECRET`, DB password, optional `OPENAI_API_KEY`).
3. Configure TLS on a reverse proxy / load balancer.
4. Set `CORS_ORIGINS` to the real public HTTPS origin.
5. Build and start using `docker-compose.prod.yml` (or platform equivalent).
6. Run `alembic upgrade head`.
7. Verify `GET /api/v1/health`, login, protected routes, and report download.
8. Configure PostgreSQL and report-volume backups.
