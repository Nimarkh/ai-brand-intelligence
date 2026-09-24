# Recommendations Engine

Phase 14 converts existing audit evidence into a deterministic, prioritized list of actionable recommendations.

```text
SEO Findings + Website Health + AI Visibility + Entity Intelligence
                              ↓
                   Recommendations Engine
                              ↓
                 recommendations table snapshot
```

## Scope

- Rule-based only (no LLM for primary recommendation text)
- Uses the existing Phase 02 `recommendations` table
- Does **not** modify Phase 09 / 12 / 13 scoring formulas
- Does **not** update `website_score`, `seo_score`, `ai_visibility_score`, `entity_score`, or `overall_score`

## Package

```text
backend/app/services/recommendations/
├── __init__.py
├── categories.py   # controlled category + source enums
├── constants.py    # priority, impact, effort, thresholds
├── models.py       # typed evidence + candidate models
├── scoring.py      # impact / priority helpers
├── rules.py        # deterministic rules
└── engine.py       # evaluate → dedupe → rank → limit
```

Persistence orchestration: `recommendation_service.py`.

## Categories

Controlled values stored as strings on `recommendations.category`:

| Category | Use |
| --- | --- |
| `TECHNICAL` | Website health technical gaps |
| `SEO` | On-page SEO findings |
| `CONTENT` | Thin content / headings |
| `STRUCTURED_DATA` | Schema / structured identity |
| `AI_VISIBILITY` | Mention / citation / position / semantic |
| `ENTITY` | Presence / consistency / recognition |
| `PERFORMANCE` | Response time / related performance |

Arbitrary frontend category strings are not accepted by the engine.

## Impact and effort (0–100)

| Field | Meaning |
| --- | --- |
| `impact_score` | Higher = more beneficial if fixed |
| `effort_score` | Higher = more implementation work (not a probability) |

### Severity → base impact

| Severity | Base impact |
| --- | --- |
| HIGH | 90 |
| MEDIUM | 65 |
| LOW | 40 |
| INFO | 15 |

Coverage adjustment:

```text
coverage = affected_pages / analyzable_pages
impact   = base_impact × (0.50 + 0.50 × coverage)
```

Bounded to 0–100.

### Effort bands (examples)

| Band | Typical score | Examples |
| --- | --- | --- |
| Low | 25–35 | missing title/meta/H1, short metadata, duplicates |
| Medium | 40–65 | canonicals, structured data, content expansion |
| High | 70–90 | 5xx, broad performance, large restructuring |

## Priority formula

```text
priority_score = impact_score × 0.70 + (100 − effort_score) × 0.30
```

Mapped to the existing DB enum (no `priority_score` column):

| Priority | Threshold |
| --- | --- |
| HIGH | `priority_score >= 75` |
| MEDIUM | `50 <= priority_score < 75` |
| LOW | `priority_score < 50` |

## Deduplication and ranking

- Stable rule key per logical recommendation (`category + rule_type`)
- Many pages with the same SEO finding → **one** aggregated recommendation
- Sort: priority (HIGH → MEDIUM → LOW), impact desc, effort asc, stable title/rule key
- Cap: `RECOMMENDATIONS_MAX_PER_AUDIT` (default `20`, valid `1–100`)

## Evidence and sources

Evidence is written into `description` (no schema change). Internal sources include:

```text
SEO_FINDING
WEBSITE_SCORE
AI_VISIBILITY
ENTITY_INTELLIGENCE
STRUCTURED_DATA
```

## Snapshot persistence

On calculate:

1. Delete existing recommendations for the audit
2. Evaluate current evidence
3. Insert the new snapshot
4. Commit

## Freshness / invalidation

Recommendations are **cleared** (not auto-recalculated) when:

- Website crawl reruns
- SEO analysis reruns
- AI Query reruns
- AI Visibility recalculates
- Entity Intelligence recalculates

The user must explicitly call Calculate Recommendations again.

## API

| Method | Path | Behavior |
| --- | --- | --- |
| `POST` | `/api/v1/audits/{audit_id}/calculate-recommendations` | Auth + ownership; replace snapshot; return counts |
| `GET` | `/api/v1/audits/{audit_id}/recommendations` | Auth + ownership; prioritized list |

Cross-user access returns **404**.

## UI language

Use:

- High / Medium / Low priority
- Estimated impact / Estimated effort
- Based on analyzed evidence

Avoid:

- “best recommendation”
- “guaranteed impact”
- “will improve ranking”
