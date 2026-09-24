# Live Interview Demo

This is the local demo for a real interview. It uses the existing application: development Compose, PostgreSQL, Mock AI, and localhost HTTP.

There is no separate demo mode, no seeded brands, and no invented website. You supply a real account and a real public website during the rehearsal.

The crawler only fetches a website that is publicly reachable and compatible with the existing crawler: `http`/`https`, same origin as the brand URL (no automatic `www` or subdomain expansion), `robots.txt` allow rules for `AI-Brand-Intelligence-Crawler/1.0`, and HTML that is present in the response (JavaScript-only pages are not executed). Private, loopback, and non-public addresses are rejected.

---

## Prerequisites

- Docker and Docker Compose
- Ports free on the host: `4200` (frontend), `8000` (API), `5432` (PostgreSQL), `6379` (Redis)
- A public website you are allowed to crawl, entered at demo time

Redis starts with Compose and stays unused by the application. Do not add application Redis usage for the demo.

---

## Environment variables

From the repository root:

```bash
cp .env.example .env
```

Set these in `.env` before the first start. Do not commit `.env`.

| Variable | Demo value |
| --- | --- |
| `ENVIRONMENT` | `development` |
| `AI_PROVIDER` | `mock` |
| `JWT_SECRET` | A unique secret of at least 32 characters. Do not keep `change-me-in-development-only!!!` for a shared rehearsal. Production still rejects known defaults and short secrets. |
| `COOKIE_SECURE` | `false` (required for this localhost HTTP demo) |
| `COOKIE_SAMESITE` | `lax` |
| `CORS_ORIGINS` | `http://localhost:4200,http://127.0.0.1:4200` |
| `DATABASE_URL` | `postgresql://postgres:postgres@postgres:5432/brand_intelligence` |
| `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_DB` | `postgres` / `postgres` / `brand_intelligence` |
| `REDIS_URL` | `redis://redis:6379/0` (service only; the API does not call Redis) |

`REPORTS_DIR=./data/reports` in `.env` applies only when you run Uvicorn on the host. Compose always stores PDFs on the `reports_data` volume at `/data/reports` inside the backend container.

Leave `OPENAI_API_KEY` empty while `AI_PROVIDER=mock`.

These values do not relax production checks. `ENVIRONMENT=production` still requires a strong `JWT_SECRET`, `COOKIE_SECURE=true`, explicit CORS, and PostgreSQL.

---

## Start the application

```bash
docker compose up --build
```

What starts:

1. PostgreSQL and Redis (health checks)
2. Backend on port 8000, then `alembic upgrade head` (`RUN_MIGRATIONS_ON_START=true`)
3. Frontend on port 4200 after the API health check passes

The frontend dev server proxies `/api` to `http://backend:8000`. Open the UI at `http://localhost:4200` (or `http://127.0.0.1:4200`).

---

## Verify backend health

```bash
curl -fsS http://localhost:8000/api/v1/health
```

Expect:

```json
{"status":"ok"}
```

The same check is available through the UI origin: `http://localhost:4200/api/v1/health`.

---

## Register and log in

1. Open `http://localhost:4200/register`.
2. Create an account (email and password).
3. You are signed in with the HttpOnly cookie `ai_brand_access_token`.
4. To sign in again later, use `http://localhost:4200/login`.

---

## Create a brand

1. Open **Brands**, then add a brand (`/brands/new`).
2. Fill **Brand name**, **Website URL**, **Industry**, **Country**, and **Target market**.
3. Use a public `http` or `https` URL you choose at demo time. Description is optional.
4. Submit **Create brand**.

---

## Start a crawl

1. Open the brand.
2. Click **Start website crawl**.
3. Wait until the status is completed and a page count is shown.

If the crawl fails, the usual causes are: the host is not publicly reachable from the backend container, DNS resolves to a private address, `robots.txt` disallows the crawler, or the URL is not `http`/`https`. Change the target you type in; do not change crawler rules for the demo.

---

## Run the audit pipeline

Open the completed crawl with **Open audit / Analyze SEO**, then use the audit page buttons in this order:

1. **Analyze SEO**
2. **Calculate score**
3. **Run AI Analysis** (Mock AI provider; no OpenAI key)
4. **Calculate AI Visibility**
5. **Calculate Entity**
6. **Calculate Recommendations**

Each step persists its own result. Scores stay unavailable until that step has been run.

---

## Generate a report

1. Open **Reports**.
2. Click **Generate Report** and choose the completed audit.
3. Open the report and click **Download PDF**.

The PDF is written under `/data/reports` on the `reports_data` volume.

---

## Reset the demo database

This deletes local Postgres data and stored PDFs for this Compose project.

```bash
docker compose down -v
docker compose up --build
```

Register again after a reset. Brands, audits, and reports are not restored.

If report generation fails because `/data/reports` is not writable:

```bash
docker compose run --rm --user root backend chown -R app:app /data/reports
```

---

## Demo checklist

- [ ] Backend healthy
- [ ] Frontend accessible
- [ ] PostgreSQL connected
- [ ] Registration works
- [ ] Login works
- [ ] Brand creation works
- [ ] Crawl can start
- [ ] Audit can be completed
- [ ] SEO analysis works
- [ ] Score calculation works
- [ ] AI analysis works with MockAIProvider
- [ ] AI Visibility calculation works
- [ ] Entity calculation works
- [ ] Recommendations calculation works
- [ ] Report generation works
- [ ] Report download works
- [ ] Dashboard reflects the completed audit
- [ ] Query Explorer reflects AI queries
- [ ] Ask Intelligence works
- [ ] Logout works

After AI analysis, open **Query Explorer**. Ask Intelligence is **Ask Intelligence** in the sidebar. Sign out is **Sign out** in the profile menu.
