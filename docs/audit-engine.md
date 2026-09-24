# Audit Engine

Phase 09 adds a **deterministic Audit Engine**. It scores stored `WebsitePage` and `SeoFinding` data. It does not crawl, re-run SEO analysis, call an LLM, or use external APIs.

## Layer separation

| Layer | Question |
| ----- | -------- |
| Crawler | What exists? |
| SEO Analyzer | What issues exist? |
| Audit Engine | How do we measure the current state? |
| Recommendations / AI | Later phases |

## Score architecture

Component scores (0–100):

| Component | Inputs (finding categories) | Website Health weight |
| --------- | --------------------------- | --------------------- |
| Technical | `STATUS`, `PERFORMANCE`, `CRAWL` | 30% |
| SEO | `TITLE`, `META_DESCRIPTION`, `CANONICAL`, `HEADINGS` | 30% |
| Content | `CONTENT` | 20% |
| Structured Data | `STRUCTURED_DATA` | 20% |

**Website Health** =

`Technical×0.30 + SEO×0.30 + Content×0.20 + Structured Data×0.20`

**SEO score** (persisted as `Audit.seo_score`) is the SEO component score.

## Availability semantics

| Status | Meaning |
| ------ | ------- |
| `AVAILABLE` | Dimension calculated from enough data |
| `UNAVAILABLE` | Not calculable or not yet run — **score is null, never zero** |
| `PROVISIONAL` | Overall score using only currently available final dimensions |

**Unavailable ≠ zero.** An empty audit (0 pages) returns `UNAVAILABLE` with null scores. Zero would incorrectly imply a measured failing site.

Minimum analyzable audit: **≥ 1 `WebsitePage`**.

## Provisional overall score

Final design (future):

| Dimension | Weight |
| --------- | ------ |
| Website Health | 25% |
| SEO | 20% |
| AI Visibility | 35% |
| Entity Strength | 20% |

Phase 09 does **not** treat missing AI/Entity as zero. Available weights are renormalized:

```
available = 25 + 20 = 45
Overall = Website Health × (25/45) + SEO × (20/45)
```

Status is always **`PROVISIONAL`** until AI Visibility and Entity Strength exist.

Persisted columns:

- `website_score` ← Website Health
- `seo_score` ← SEO component
- `overall_score` ← provisional overall
- `ai_visibility_score`, `entity_score`, `semantic_score` ← remain **null**

## Penalty formula

For each rule (stable rule id), within one score component:

```
affected_page_rate = distinct_affected_pages / analyzable_pages
penalty_points = severity_weight × affected_page_rate × rule_weight
```

Audit-level findings (`page_id` is null) use `affected_page_rate = 1.0`.

Distinct page IDs are counted once per rule (same finding title on one page does not inflate pages).

Category score:

```
category_penalty = min(100, sum(penalty_points))
category_score = clamp(100 - category_penalty, 0, 100)
```

Each finding maps to **exactly one** component via `FINDING_CATEGORY_TO_COMPONENT` (no double-counting across categories).

## Severity weights

| Severity | Weight |
| -------- | ------ |
| HIGH | 15 |
| MEDIUM | 7 |
| LOW | 3 |
| INFO | 0 |

## Rule weights

Configured in `backend/app/services/audit_engine/weights.py` (examples): missing title `1.00`, missing meta `0.70`, 5xx `1.00`, 4xx `0.80`, duplicate title `0.55`, missing schema `0.35`, slow response `0.35`, empty audit `1.00`.

## Package layout

```
backend/app/services/audit_engine/
  weights.py      # all configuration
  models.py       # FindingInput, ComponentScore, AuditScoreResult
  penalties.py    # mapping + penalty math
  scoring.py      # ScoreCalculator
  engine.py       # AuditEngine
```

Persistence: `backend/app/services/score_service.py`

## API

### `POST /api/v1/audits/{audit_id}/calculate-score`

Owner-only. Loads pages + findings, scores in memory, replaces `website_score` / `seo_score` / `overall_score`. Does not change `AuditStatus`.

### `GET /api/v1/audits/{audit_id}/score`

Owner-only. Does **not** auto-calculate. Returns persisted scores or `UNAVAILABLE` with explainable counts when possible.

Response includes component breakdown, findings/affected page counts, and `ai_visibility` / `entity_strength` as `{ score: null, status: "UNAVAILABLE" }`.

## Idempotency

Re-running calculation overwrites the three score columns with a fresh deterministic snapshot for that audit.

## Future final score

When AI Visibility and Entity Strength are AVAILABLE, overall becomes:

`WH×0.25 + SEO×0.20 + AI×0.35 + Entity×0.20`

and status can move from `PROVISIONAL` to `AVAILABLE`.
