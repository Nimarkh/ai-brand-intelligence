# Database Layer

## Status

The persistence layer uses SQLAlchemy 2.x models and Alembic migrations against PostgreSQL. Authentication, brand ownership, audits, website pages, SEO findings, AI queries/responses, recommendations, and reports all persist here. Later product phases reuse and extend this schema rather than introducing separate databases.

Schema history began in early foundation work; several product features (brands API requirements, crawler fields) reused existing columns without new migrations where the schema already fit.

## Stack

- SQLAlchemy 2.x typed declarative models
- Alembic migrations
- PostgreSQL 16 (Docker Compose)
- `psycopg` (v3) as the SQLAlchemy driver

`DATABASE_URL` is read from the environment through the existing pydantic-settings class. Credentials are not hard-coded in Python.

## Connection

`app/core/database.py` owns:

- SQLAlchemy engine
- session factory (`SessionLocal`)
- declarative `Base`
- FastAPI dependency `get_db()`

`postgresql://` and `postgres://` URLs are translated to `postgresql+psycopg://` so the same `DATABASE_URL` works in Docker and on the host.

Use host `postgres` from Compose services. Use host `localhost` when running Alembic or the backend on the host against the published Postgres port.

## Schema

UUID primary keys (`postgresql.UUID`) and timezone-aware timestamps are used throughout. Application tables also use `gen_random_uuid()` as a server default. `updated_at` is present on `users` and `brands`. Audit-related tables keep `created_at` (and explicit start/complete fields where listed).

```
User 1 --- N Brand 1 --- N Audit
                              |
                              +--- N WebsitePage 1 --- N SeoFinding
                              +--- N SeoFinding          (page_id nullable)
                              +--- N AiQuery 1 --- N AiResponse
                              +--- N Recommendation
                              +--- N Report
```

Tables created by the initial migration:

| Table             | Purpose                                      |
| ----------------- | -------------------------------------------- |
| `users`           | Authentication identity                      |
| `brands`          | Brand records owned by a user                |
| `audits`          | Audit runs and nullable scores               |
| `website_pages`   | Crawled page snapshots (`schema_types` JSONB)|
| `seo_findings`    | SEO issues, optional page scope              |
| `ai_queries`      | Prompt set for an audit                      |
| `ai_responses`    | Provider responses for a query               |
| `recommendations` | Action items derived from an audit           |
| `reports`         | Generated report artifacts                   |

Chat tables are intentionally omitted until the Intelligence Chat phase.

## Migrations

From `backend/`, with `DATABASE_URL` pointing at a reachable PostgreSQL instance:

```bash
alembic upgrade head
alembic current
alembic downgrade -1
alembic upgrade head
```

The backend container runs `alembic upgrade head` before Uvicorn so Compose starts with the current schema.

## Session dependency

`get_db()` yields a SQLAlchemy `Session` and closes it after the request. Auth and brand endpoints use it through `get_current_user()` and the route handlers.

## Brand deletion

Phase 05 does not change the `brands` schema and does not add a migration. `website_url`, `industry`, `country`, and `target_market` stay nullable in the database; the brand API requires them on create.

`audits.brand_id` references `brands.id` with `ON DELETE CASCADE`. The ORM relationship uses `passive_deletes="all"` so deleting a brand does not load audit rows or set `brand_id` to null. With no audit rows, deletion removes only the brand. Once audits exist, the database will also remove those audits and, through each audit's own cascades, their pages, findings, AI queries and responses, recommendations, and reports.

That cascade is the current database behavior, not a new product rule. Before audit data is stored, decide whether deleting a brand should remain cascading or should be refused while audits exist.
