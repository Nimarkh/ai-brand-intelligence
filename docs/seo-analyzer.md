# SEO Analyzer

Phase 08 adds a **deterministic SEO analyzer**. It consumes stored `WebsitePage` rows from the crawler and writes `SeoFinding` rows. It does not crawl again, call an LLM, or calculate any score.

## Layer separation

| Layer | Question | Phase |
| ----- | -------- | ----- |
| Crawler | What exists on the website? | 07 |
| SEO Analyzer | What SEO-related issues can be objectively detected? | 08 |
| Audit Engine | How good is the website overall? | later |
| Recommendations | What should the user do? | later |

`SeoFinding.recommendation` in this phase is a short deterministic action statement only. It is not the Recommendation Engine.

## Architecture

```
WebsitePage rows (stored)
        │
        v
SEOAnalyzer (pure rules) ──► FindingResult[]
        │
        v
seo_analysis_service ──► delete old SeoFinding for audit
                      ──► insert new SeoFinding rows
```

- Pure analyzer: `backend/app/services/seo_analyzer/`
  - `models.py` — `PageSnapshot`, `FindingResult`, `AnalyzerThresholds`
  - `rules.py` — page and audit-level checks
  - `seo_analyzer.py` — `SEOAnalyzer.analyze()`
- Persistence: `backend/app/services/seo_analysis_service.py`
- API: `POST /api/v1/audits/{id}/analyze-seo`, `GET /api/v1/audits/{id}/seo-findings`

The analyzer does not depend on a SQLAlchemy session. Unit tests run without a database.

## Idempotency

Before writing findings for an audit, the service deletes existing `SeoFinding` rows for **that audit only**, then inserts the new deterministic snapshot. Re-running analysis does not duplicate rows. Other audits are untouched.

`Audit.status` is **not** changed. `COMPLETED` still means the crawl finished, not that SEO analysis ran.

## Categories

String values stored in `SeoFinding.category`:

`TITLE`, `META_DESCRIPTION`, `CANONICAL`, `HEADINGS`, `CONTENT`, `STRUCTURED_DATA`, `STATUS`, `PERFORMANCE`, `CRAWL`

## Rules (summary)

| Finding | Condition | Severity |
| ------- | --------- | -------- |
| Missing page title | title null/blank | HIGH |
| Page title is very short | length &lt; min | LOW |
| Page title is long | length &gt; max | MEDIUM |
| Missing meta description | null/blank | MEDIUM |
| Meta description very short / long | below/above thresholds | LOW |
| Canonical missing | null/blank | MEDIUM |
| Canonical outside site | different host / non-equivalent port | MEDIUM |
| Missing / multiple H1 | h1_count 0 / &gt; 1 | MEDIUM |
| Very little textual content | word_count &lt; threshold | LOW |
| No structured data | has_schema == false | LOW |
| Client error status (4xx) | status_code 400–499 | MEDIUM |
| Server error status (5xx) | status_code ≥ 500 | HIGH |
| Slow page response | load_time_ms &gt; threshold | MEDIUM |
| Duplicate page title | shared non-empty title | MEDIUM |
| Duplicate meta description | shared non-empty meta | MEDIUM |
| No pages crawled | zero WebsitePage rows | HIGH |

Missing title/meta take precedence over length findings for the same field. Null `status_code` is not flagged as an SEO status issue.

## Thresholds

Configured via settings / `.env` (not exposed in the API):

| Variable | Default |
| -------- | ------- |
| `SEO_TITLE_MAX_LENGTH` | 60 |
| `SEO_TITLE_MIN_LENGTH` | 10 |
| `SEO_META_DESCRIPTION_MAX_LENGTH` | 160 |
| `SEO_META_DESCRIPTION_MIN_LENGTH` | 50 |
| `SEO_LOW_WORD_COUNT` | 300 |
| `SEO_SLOW_RESPONSE_MS` | 2000 |

Length and word-count rules are **practical heuristics**, not strict search-engine requirements. Wording in findings reflects that.

## Severity policy

Uses existing `FindingSeverity`: `HIGH`, `MEDIUM`, `LOW`, `INFO`.

Chosen severities for ambiguous cases:

- Title too long → **MEDIUM**
- Duplicate meta description → **MEDIUM**
- Slow response → **MEDIUM**

Severity reflects the practical significance of one issue, not an overall website score.

## Canonical policy

Crawl origin comes from the brand `website_url` (normalized origin).

A canonical is **on-site** when:

1. Hostname matches (case-insensitive). Subdomains do not match (`www.example.com` ≠ `example.com`).
2. Effective ports are equal, **or** both sides use a default web port (80 or 443), so **http ↔ https** for the same host is allowed.

The canonical URL does not need to equal the page URL.

## Duplicate detection

For non-empty titles and meta descriptions, each affected page receives **one** finding. Empty/null values are handled only by the missing-* rules.

## Findings vs scoring

This phase writes findings only. These columns remain unchanged / null:

`overall_score`, `website_score`, `seo_score`, `ai_visibility_score`, `entity_score`, `semantic_score`

## API

### `POST /api/v1/audits/{audit_id}/analyze-seo`

Authenticated, owner-only (else 404). Response:

```json
{ "audit_id": "...", "findings_count": 14, "status": "COMPLETED" }
```

`status` here is the analysis run result, not `AuditStatus`.

### `GET /api/v1/audits/{audit_id}/seo-findings`

Authenticated, owner-only. Ordered by severity (`HIGH` → `INFO`), then `page_id`, `category`, `created_at`.

```json
{ "items": [ ... ], "total": 14 }
```

Each item may include `page: { id, url, status_code }` when linked to a page.

## Frontend

- `/audits/:id` — crawl summary, **Analyze SEO**, findings list
- Brand detail links to the audit when crawl status is `COMPLETED`
- No SEO score is shown
