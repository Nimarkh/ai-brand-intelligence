# Entity Intelligence

Phase 13 evaluates how clearly and consistently a brand is represented as an entity using **only** evidence already stored in the platform.

```text
Website Pages + Structured Data + AI Responses
                    ↓
           Entity Intelligence
                    ↓
             Entity Strength
```

## Critical limitation

This is **not** external entity verification.

The engine does **not**:

- call Google Knowledge Graph
- call Wikidata or Wikipedia APIs
- call search engines
- scrape third-party directories
- claim knowledge-panel ownership
- assert that an entity exists externally

It only scores evidence from:

```text
WebsitePage (Phase 07)
AI responses (Phase 11)
```

## Package

```text
backend/app/services/entity/
├── weights.py
├── models.py
├── extraction.py   # brand normalization + helpers
├── metrics.py
├── scoring.py
└── engine.py
```

Persistence: `entity_service.py` → `audit.entity_score` only.

## Component weights

| Component | Weight |
| --- | --- |
| Entity Presence | 30% |
| Entity Consistency | 25% |
| Structured Identity | 25% |
| AI Entity Recognition | 20% |

Weights sum to `1.0`. Unavailable components are excluded and remaining weights renormalized (never treated as zero).

## Brand normalization

Matching uses a derived normalized form (Brand DB value is not modified):

1. Unicode NFKC
2. Casefold
3. Punctuation → spaces
4. Collapse whitespace
5. Strip trailing legal suffixes (`inc`, `ltd`, `llc`, `srl`, `spa`, …)

## Metric formulas

### Presence

Uses persisted title and meta description only (no body HTML):

```text
title_presence_rate = pages_with_brand_in_title / analyzable_pages
meta_presence_rate  = pages_with_brand_in_meta / analyzable_pages
Presence = average(available rates) × 100
```

No pages → `UNAVAILABLE`.

### Consistency

Equal-weight average of available:

- `title_consistency` (brand in title rate)
- `canonical_consistency` (same-origin canonical / pages with canonical)
- `schema_consistency` (pages with schema / analyzable)

### Structured Identity

Uses persisted `schema_types` only (no re-parse of JSON-LD):

```text
entity_schema_coverage = entity_schema_pages / analyzable_pages
schema_quality = best matching type weight (Organization/Corporation/… highest)
Structured Identity = average(coverage, quality) × 100
```

Type weights are centralized in `weights.py`.

### AI Entity Recognition

From successful Phase 11 responses (no new AI calls):

```text
mention_rate × 100
position_component = average(Phase 12 position mapping)
AI Recognition = average(mention_score, position_component)
```

No successful responses → `UNAVAILABLE`.

## Availability

| Condition | Status |
| --- | --- |
| No pages and no AI responses | `UNAVAILABLE` |
| Some components missing | `PROVISIONAL` |
| All four components available | `AVAILABLE` |

## Persistence

Writes `audit.entity_score` only.

Does **not** modify `overall_score`, `website_score`, `seo_score`, or `ai_visibility_score`.

## Freshness

| Event | Clears |
| --- | --- |
| Crawl re-run (Phase 07) | `entity_score` |
| AI query re-run (Phase 11) | `entity_score` (+ visibility/semantic from Phase 12) |

Does not auto-recalculate. User must run Calculate Entity again.

## API

| Method | Path |
| --- | --- |
| `POST` | `/api/v1/audits/{audit_id}/calculate-entity` |
| `GET` | `/api/v1/audits/{audit_id}/entity` |

Authenticated + owner isolation (404 cross-user).

## Frontend

`/audits/:id` **Entity Intelligence** section: score, status, components with effective weights, evidence counts, and the external-database limitation note.
