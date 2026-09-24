# Architecture

## Current stage

AI Brand Intelligence is a **modular monolith** spanning foundation through production-deployable packaging (Phases 01–22), with Phase 23 focused on portfolio/repository readiness.

Implemented product surface:

- Cookie-based authentication and ownership-isolated brand management
- Same-origin website crawler with robots handling and SSRF defenses
- Deterministic SEO analyzer and Audit Engine (Website Health, SEO, provisional overall)
- AI provider abstraction (Mock default, optional OpenAI)
- AI Query Engine, AI Visibility Engine, Entity Intelligence, Recommendations Engine
- Main Intelligence Dashboard, Query Explorer, Ask Intelligence, Audit Intelligence Reports
- Security hardening and production Docker / reverse-proxy layout

**Overall-score orchestration note:** AI Visibility and Entity Strength are calculated and stored separately. They do **not** yet update the Audit Engine `overall_score`, which remains a **provisional** Website Health + SEO composite. See [scoring.md](scoring.md).

Recommendations persist to the `recommendations` table and do not modify score columns. Query Explorer does not execute queries or recalculate scores. Ask Intelligence reads persisted audit data through the existing `AIProvider` (no chat tables, retrieval indexes, or web search). Reports render PDF/JSON snapshots from persisted data without rescoring or calling an AI provider.

Redis is provisioned in Compose and reserved for future queue/cache use; crawls, AI runs, and report generation currently execute in the API process.

## Modular monolith

The system is a **modular monolith**, not a set of microservices.

A single FastAPI backend owns HTTP APIs, SQLAlchemy models, authentication, domain services, and future workers. A single Angular frontend owns presentation. PostgreSQL and Redis run as supporting infrastructure processes, not as independently deployed product services.

This shape is intentional:

- One deployable backend keeps local development and operations simple
- Feature folders (`api`, `models`, `schemas`, `services`, `workers`) allow domain modules to grow without networked service splits
- Frontend feature folders isolate UI work the same way
- Shared PostgreSQL/Redis infrastructure avoids premature operational cost

Microservices would add network boundaries and duplicated configuration before the product needs independent scaling units.

## Runtime topology

### Development

```text
Browser
   │
   ▼
Angular (ng serve / Compose frontend)
   │  /api/v1  (dev proxy or published backend port)
   ▼
FastAPI
   ├── Authentication
   ├── Brand Management
   ├── Audit Engine
   ├── Crawler
   ├── SEO Analyzer
   ├── AI Provider
   ├── Entity Intelligence
   ├── Recommendations
   ├── Reports
   └── Intelligence Chat
   │
   ├──────────────┬───────────────┐
   ▼              ▼               ▼
PostgreSQL      Redis       Report Storage
```

### Production

```text
Browser
  ↓
HTTPS Reverse Proxy
  ↓
Angular static assets + FastAPI (/api/)
  ↓
PostgreSQL · Redis · report volume
  (DB/Redis ports not published)
```

| Component | Role |
| --- | --- |
| Frontend | Auth pages, shell, dashboard, brands, audits, query explorer, Ask Intelligence, reports |
| Backend | REST API under `/api/v1` for all product capabilities above |
| PostgreSQL | Application schema via Alembic |
| Redis | Available; unused for queues/cache in the current product path |
| Report storage | UUID-named files under `REPORTS_DIR` (Compose volume in production) |

See [deployment.md](deployment.md) for Compose files, nginx example, migrations, and operator responsibilities.

## Configuration

Backend settings load from the environment through `pydantic-settings`. Database, Redis, API prefix, JWT, cookie, CORS, crawler, SEO, AI, recommendations, and reports paths are not hard-coded in business logic.

Production (`ENVIRONMENT=production`) fails fast on weak `JWT_SECRET`, insecure cookies, and related misconfiguration. See [security.md](security.md) and [deployment.md](deployment.md).

## Authentication

- Passwords hashed with Argon2; never returned by the API
- Login issues an HS256 JWT in an **HttpOnly** cookie
- Angular uses `withCredentials` and never reads the JWT from JavaScript storage
- Protected routes use `authGuard`; unauthenticated users redirect to `/login`
- Brand and audit APIs scope all access by `owner_id` (foreign resources → 404)

Details: [security.md](security.md).

## Analysis pipeline

```text
Create brand
  → create audit
  → crawl website → website_pages
  → analyze SEO → seo_findings
  → calculate Website Health / SEO / provisional overall
  → run AI queries → ai_queries / ai_responses
  → calculate AI Visibility
  → calculate Entity Strength
  → generate recommendations
  → dashboard / query explorer / Ask Intelligence / PDF report
```

Each step is an explicit API action. There is no background job orchestrator yet.

## Scoring pipeline

Deterministic pure functions over stored evidence. Weights and limitations: [scoring.md](scoring.md). Component docs: [audit-engine.md](audit-engine.md), [ai-visibility.md](ai-visibility.md), [entity-intelligence.md](entity-intelligence.md).

## AI provider abstraction

`backend/app/services/ai/` defines `AIProvider`, Mock, and OpenAI implementations. Selection via `AI_PROVIDER`. No public raw-prompt endpoint. Ask Intelligence and the Query Engine build prompts server-side. See [ai-provider.md](ai-provider.md).

## Report generation

Synchronous PDF generation from a completed owned audit. Files land under `REPORTS_DIR` with UUID names; metadata and ownership live in PostgreSQL. See [reports.md](reports.md).

## Frontend layout

- `core` — auth, theme, interceptors, guards
- `shared/components` — reusable UI primitives
- `features` — product areas (dashboard, brands, audits, query explorer, intelligence-chat, reports, …)
- `layout` — shell, sidebar, topbar, profile menu

Theme tokens live in SCSS; light/dark preference is stored in `localStorage` (`abi.theme` only — not auth tokens).

## API conventions

REST over JSON. Public prefix `/api/v1`. FastAPI OpenAPI at `/docs` and `/openapi.json` unless disabled or protected by infrastructure.

## Related documentation

- [database.md](database.md) — schema and migrations
- [security.md](security.md) — threat model and controls
- [deployment.md](deployment.md) — production deploy
- [testing.md](testing.md) — test strategy and results
- Feature docs for crawler, SEO, AI, entity, recommendations, dashboard, query explorer, Ask Intelligence, and reports
