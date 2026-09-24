# Security

Security model for the AI Brand Intelligence platform (hardening delivered in Phase 21; still accurate after production packaging).

This document distinguishes **Implemented** controls (code and tests in this repository) from **Recommended for production** (deployment-layer practice that this application cannot fully own).

Portfolio entry point: [../README.md](../README.md). Deployment companion: [deployment.md](deployment.md).

---

## Threat model

### Assets

| Asset | Why it matters |
| --- | --- |
| User accounts | Account takeover enables full tenant access |
| Authentication session (JWT cookie) | Bearer of identity for every protected API |
| Brand data | Tenant-owned business metadata |
| Audit / crawl / SEO data | Tenant-owned analysis artifacts |
| AI query and response data | Tenant-owned provider outputs |
| Recommendations | Tenant-owned guidance |
| Generated reports (PDF/JSON) | Downloadable exports of tenant data |
| API credentials (`OPENAI_API_KEY`) | Billable provider access |
| Database credentials / `DATABASE_URL` | Full data-store access |
| `JWT_SECRET` | Ability to forge sessions |

### Threat actors

- Unauthenticated internet user
- Authenticated malicious user
- Authenticated user attempting cross-tenant (IDOR) access
- Malicious website URL supplied to the crawler
- Malicious HTML/content returned by a crawled site
- Malicious or manipulated AI response text
- Malicious report download or path-traversal attempt

### Trust boundaries

```text
Browser
  ↓  HTTPS (recommended) + credentialed cookies
FastAPI API
  ↓  parameterized SQLAlchemy
Database
  ↓  outbound HTTP (SSRF-filtered)
Crawler / external websites
  ↓  provider SDK
AI provider
  ↓  UUID-named files under REPORTS_DIR
Filesystem / generated reports
```

### Assumptions and limitations

- The SPA and API are separate origins configured via `CORS_ORIGINS`.
- Development may use HTTP and `COOKIE_SECURE=false`.
- Single-process rate limiting is not shared across workers or hosts.
- DNS rebinding remains a residual crawler risk (see SSRF).
- `/docs`, `/redoc`, and `/openapi.json` remain available unless the deployment disables them.
- Password reset and email verification are intentionally out of scope.

---

## Authentication

### Implemented

- Passwords are hashed with **Argon2** (`argon2-cffi`). Plaintext passwords are never stored.
- Login issues an **HS256 JWT** stored in an **HttpOnly** cookie (`COOKIE_NAME`).
- JWT `exp` is enforced; missing, malformed, expired, and wrongly signed tokens return `401`.
- Subject (`sub`) must be a UUID; inactive users cannot authenticate or call protected APIs.
- API responses use `UserPublic` and never include `password` or `password_hash`.
- Registration requires password length 8–128. Duplicate email returns a generic conflict message.
- Auth request schemas use `extra="forbid"` so clients cannot set `is_active`, `password_hash`, or `id`.

### Recommended for production

- Rotate `JWT_SECRET` with a documented procedure.
- Put the API behind HTTPS only.
- Consider account lockout / CAPTCHA after repeated failures at the edge (beyond the in-process limiter).

---

## Session cookies

### Implemented

| Attribute | Behavior |
| --- | --- |
| HttpOnly | Always `true` |
| Secure | From `COOKIE_SECURE` (must be `true` in production) |
| SameSite | `lax` or `strict` (default `lax`); `none` requires Secure |
| Path | `/` |
| Max-Age | `JWT_EXPIRE_MINUTES * 60` |
| Logout | Clears the cookie with matching attributes |

Production configuration **fails fast** when `COOKIE_SECURE` is false.

### Recommended for production

- Terminate TLS at a reverse proxy and set `COOKIE_SECURE=true`.
- Prefer `SameSite=lax` (or `strict` if the SPA never needs cross-site top-level GET with cookies).

---

## Authorization

### Implemented

- Protected routes depend on `get_current_user`.
- Brand, audit, crawl, SEO, scores, AI queries, visibility, entity, recommendations, dashboard, query explorer, Ask Intelligence, and reports are scoped to `current_user.id` through ownership joins.
- Cross-tenant access returns **404** with a generic detail (`Not found.` / `Brand not found.`) so existence is not leaked.
- Phase 20 ownership matrix tests remain the baseline; Phase 21 adds further IDOR/mass-assignment coverage.

### Recommended for production

- Periodically re-audit new endpoints for ownership checks on every path parameter (`brand_id`, `audit_id`, `report_id`, `query_id`).

---

## CSRF

### Threat

Cookie-authenticated `POST` / `PATCH` / `DELETE` can be targeted by a malicious site if the browser attaches the session cookie.

### Mitigation (Implemented)

Defense in depth:

1. **SameSite=Lax** (default) prevents the cookie on most cross-site state-changing requests.
2. **CORS** allowlist with credentials (no `*`).
3. **Origin / Referer validation** middleware on unsafe methods:
   - If `Origin` is present, it must be in `CORS_ORIGINS`.
   - Else if `Referer` is present, its origin must be in `CORS_ORIGINS`.
   - If both are absent (non-browser clients, TestClient), the request is allowed.

### Limitations

- Non-browser clients that omit Origin/Referer are not CSRF-checked.
- This is not a synchronizer-token framework; it matches the SPA + allowlisted-origin architecture.

---

## CORS

### Implemented

- Origins come only from `CORS_ORIGINS` (comma-separated, explicit URLs).
- `*` is rejected at settings validation.
- `allow_credentials=True`.
- Methods are limited to `GET`, `POST`, `PATCH`, `PUT`, `DELETE`, `OPTIONS`.

### Recommended for production

- Set `CORS_ORIGINS` to the exact frontend HTTPS origin(s). Never use wildcards.

---

## SSRF (crawler)

### Implemented

- Only `http` / `https` URLs; credentials, fragments (stripped), and dangerous schemes rejected.
- Destinations resolved and blocked when local, private, link-local, loopback, multicast, unspecified, integer/hex IP forms, or IPv4-mapped IPv6 private/loopback.
- Same-origin crawl boundary: scheme + hostname + port.
- Redirects are followed manually with revalidation (same origin, public endpoint, credentials rejected via normalize).
- Redirects to private/localhost targets are rejected.
- `robots.txt` redirects are **not followed** (treated as missing robots).
- Response size, page count, depth, timeout, delay, and redirect hop limits apply.

### Ports

Arbitrary public ports remain allowed intentionally so legitimate sites on non-default ports still crawl. Private/loopback destinations are blocked regardless of port.

### Known limitation — DNS rebinding

The crawler resolves DNS before the request; `httpx` may resolve again when connecting. Those lookups are not pinned. A hostname that flips from public to private between checks could theoretically bypass the pre-request check.

**Recommended for production:** egress firewall / proxy that blocks RFC1918 and link-local destinations from the crawler network namespace.

---

## AI security

### Implemented

- Ask Intelligence builds context only from owned audit rows and approved fields.
- System prompt and context builder never receive `JWT_SECRET`, `OPENAI_API_KEY`, `DATABASE_URL`, env dumps, or filesystem secrets.
- Prompt/history/context sizes are bounded.
- Model answers are redacted for configured API keys, JWT secret, and database password if echoed.
- AI text is treated as untrusted in the UI (Angular interpolation; no Markdown HTML rendering).

### Limitations

- Prompt injection can still influence wording inside the supplied context; the control is **containment**, not perfect instruction immunity.
- Provider-side logging is outside this application.

---

## XSS

### Implemented

- Angular templates prefer interpolation.
- Ask Intelligence and Query Explorer treat AI text as text (XSS regression specs assert escaped `<script>`).
- Icon `innerHTML` uses a fixed SVG path map, not user content.
- Crawled HTML is parsed server-side for metadata and never returned as raw HTML for browser execution.

### Recommended for production

- Keep CSP on the frontend hosting layer (this API sets a restrictive CSP on API responses only).

---

## File / report security

### Implemented

- Report files are named `{uuid}.pdf` / `{uuid}.json` under `REPORTS_DIR`.
- Paths are validated; traversal and non-UUID names raise `UnsafeReportPath`.
- Downloads require ownership and `READY` status.
- Client-supplied `file_path` is ignored for location resolution.
- Snapshot/PDF generation redacts known secrets from brand description content.
- Filesystem paths and stack traces are not returned on generation failure.

---

## Secrets

### Implemented

- `.env` is gitignored; `.env.example` has placeholders only.
- Production requires a strong `JWT_SECRET` (≥ 32 characters, not a known development default) and `COOKIE_SECURE=true`.
- OpenAPI documents do not embed runtime secret values.

### Recommended for production

- Inject secrets from a vault / orchestrator secret store.
- Never bake `.env` into container images.
- Restrict who can read production environment configuration.

---

## Security headers

### Implemented (API responses)

| Header | Value |
| --- | --- |
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `strict-origin-when-cross-origin` |
| `Permissions-Policy` | geolocation/microphone/camera disabled |
| `Content-Security-Policy` | `default-src 'none'; ...` on API routes (not forced on `/docs`) |
| `Strict-Transport-Security` | Set when `COOKIE_SECURE` or `ENVIRONMENT=production` |

### Recommended for production

- Prefer HSTS at the reverse proxy when HTTPS is guaranteed end-to-end.
- Apply a frontend CSP appropriate for the Angular assets.

---

## Error handling and logging

### Implemented

- SQLAlchemy and unexpected errors return `{"detail": "An internal error occurred."}` without stack traces, SQL, or paths.
- Crawler and security logs avoid passwords, JWTs, cookies, and API keys.
- Full crawled HTML and full AI responses are not written to application logs by default.

### Recommended for production

- Ship structured logs to a SIEM; scrub secrets at the collector.
- Disable verbose provider SDK debug logging.

---

## Rate limiting / abuse

### Implemented

- In-process per-IP limiter on `POST /auth/login` and `POST /auth/register` (not shared across workers).

### Abuse-sensitive endpoints (identify + harden at the edge)

| Endpoint class | Risk |
| --- | --- |
| Register / login | Credential stuffing |
| Crawl | SSRF / bandwidth / time |
| AI query run / Ask Intelligence | Provider cost |
| Report generation | CPU / disk |

### Recommended for production

- Enforce request rate limits and bot protection at the reverse proxy or API gateway.
- Cap concurrent crawls and AI jobs per tenant.

---

## API documentation exposure

### Implemented

- `/docs`, `/redoc`, `/openapi.json` remain available for development.

### Recommended for production

- Disable or authenticate docs behind the reverse proxy if the API is internet-facing.

---

## Dependencies

### Approach

- Python: pinned `requirements.txt`; audit with `pip-audit`.
- Frontend: `package-lock.json`; audit with `npm audit`.
- Do not blindly bump major versions; upgrade only compatible fixes.

### Phase 21 audit results

**Python (`pip-audit`)**

| Package | Notes | Action |
| --- | --- | --- |
| PyJWT | Multiple advisories on 2.10.1 | **Upgraded to 2.13.0** (compatible 2.x) |
| starlette (via FastAPI) | Advisories; fix versions often require Starlette 0.49+ / 1.x | **Not upgraded** — would force a FastAPI major/minor bump; re-evaluate with FastAPI upgrade |
| pytest | Advisories; test-only dependency | Lives in `requirements-dev.txt` only — **not** installed in production images |

**npm (`npm audit`)**

| Area | Notes | Action |
| --- | --- | --- |
| `@angular/*` ≤19.2.25 | High: XSS sanitization / cache issues; `npm audit fix --force` jumps to Angular 21 | **Not upgraded** — major framework jump out of scope; schedule Angular patch/minor when a 19.x fix exists |

Re-run audits regularly in CI.

---

## Docker / runtime

### Implemented

- Backend image runs as non-root user `app` (uid 1000).
- Frontend Docker command no longer passes `--disable-host-check`.
- Images do not `COPY` a real `.env`.

### Recommended for production

- Do not publish PostgreSQL (`5432`) or Redis (`6379`) to the public internet; keep them on a private network.
- The development `docker-compose.yml` exposes those ports for local convenience only.
- Mount report storage with least privilege; back up and encrypt at rest if required.
- Run the API behind HTTPS termination; set production env vars explicitly.
- Drop unused capabilities; consider read-only root filesystem where practical.

---

## Database

### Implemented

- Application queries use SQLAlchemy bound parameters.
- Query Explorer search escapes `LIKE` wildcards and binds the pattern.
- Tenant isolation is enforced in application queries via `owner_id`.

### Recommended for production

- Unique strong DB password; least-privilege DB role for the app.
- No public `5432`; TLS to the database when supported by the hoster.
- Regular backups and migration review.

---

## Input limits

### Implemented (representative)

| Input | Limit |
| --- | --- |
| Password | 8–128 |
| Ask question | 2000 chars |
| Ask history | 10 messages |
| Brand description | 5000 chars |
| Website URL | 2048 chars |
| Query Explorer search | 200 chars |
| Report list page size | 1–100 |
| HTTP body (Content-Length) | 1 MiB |

---

## Regression tests

Primary suites:

- `backend/tests/test_security.py` — Phase 21 controls
- `backend/tests/test_auth.py` — authentication / cookies
- `backend/tests/test_ownership_matrix.py` — cross-tenant isolation
- `backend/tests/test_url_utils.py` / `test_crawler.py` — SSRF / redirects / robots
- `backend/tests/test_reports.py` — path / ownership / redaction
- `backend/tests/test_intelligence.py` — AI answer redaction
- Frontend specs for XSS escaping on Ask Intelligence and Query Explorer

---

## Production checklist

1. `ENVIRONMENT=production`
2. Strong unique `JWT_SECRET` (≥ 32 characters)
3. `COOKIE_SECURE=true`, `COOKIE_SAMESITE=lax` or `strict`
4. Explicit HTTPS `CORS_ORIGINS`
5. TLS at the edge; HSTS at proxy or app
6. Private DB/Redis network; no public DB port
7. Secret injection without baking into images
8. Edge rate limits for auth, crawl, AI, reports
9. Disable or protect `/docs` if exposed
10. Egress controls for crawler SSRF defense-in-depth
11. Dependency audits in CI
12. Non-root containers and least-privilege volumes
