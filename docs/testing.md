# Testing

Test strategy and verified results for AI Brand Intelligence.

Commands below match scripts actually present in the repository.

---

## Backend (`backend/`)

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements-dev.txt
pytest
```

Coverage (optional):

```bash
pytest --cov=app --cov-report=term-missing --cov-report=html
```

### What is covered

| Area | Examples |
| --- | --- |
| Unit | Crawler URL/parser helpers, SEO rules, scoring math, AI visibility/entity/recommendations engines |
| Integration / API | Auth, brands, audits, crawl, SEO, scores, AI query/visibility, entity, recommendations, dashboard, query explorer, Ask Intelligence, reports |
| Security | Cookies, production fail-fast settings, CSRF-oriented cases, SSRF-related URL checks, secret redaction in reports/AI answers |
| Ownership | Cross-tenant matrix (User A resources hidden from User B) |
| Scoring regression | Golden fixtures (`test_scoring_golden.py`) — formulas must not drift |
| Full workflow | Fixture-site audit pipeline via httpx `MockTransport` (no public crawl, no live OpenAI) |

Most API tests use in-memory SQLite. Unit tests do not require PostgreSQL.

### Skipped tests

An optional PostgreSQL integration check in `test_database.py` **skips** when Postgres is unreachable (for example, when Docker Compose is not running). That is expected on a machine without a live database.

---

## Frontend unit tests (`frontend/`)

```bash
cd frontend
npm install
npm test                 # interactive Karma
npm run test:ci          # headless Chrome, single run
npm run test:coverage    # headless + coverage under coverage/
```

Covers components/services including authentication flows and feature UI with mocked HTTP.

---

## Production build

```bash
cd frontend
npm run build
```

---

## E2E (Playwright)

```bash
cd frontend
npx playwright install chromium   # once
npm run e2e
```

- Starts the Angular dev server
- Mocks `/api/v1` responses (no OpenAI, no public crawl)
- Includes smoke/core workflow, responsive checks, and an accessibility smoke test
- Accessibility smoke disables the axe `color-contrast` rule for known design-token badge gaps; manual a11y review remains useful

---

## CI

`.github/workflows/ci.yml` runs:

1. Backend `pytest`
2. Frontend `npm run test:ci` and `npm run build`
3. Docker builds for backend and frontend production images

CI does **not** deploy.

---

## Verified results (Phase 23 packaging environment)

Captured on 2026-09-24 in this workspace:

| Suite | Result |
| --- | --- |
| Backend `pytest` | **433 passed**, **2 skipped** (PostgreSQL unavailable), exit 0 |
| Frontend `npm run test:ci` | **145 SUCCESS**, exit 0 |
| Frontend `npm run build` | **Succeeded**, exit 0 |
| Frontend `npm run e2e` | **6 passed**, exit 0 |

Docker CLI was **not** installed in this environment, so Compose-based live UI screenshots and local Docker image builds were not re-verified here. CI still defines Docker build jobs for environments that have Docker.

Do not treat these numbers as permanent SLAs; re-run the commands above after local changes.
