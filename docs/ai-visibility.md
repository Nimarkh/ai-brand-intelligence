# AI Visibility Engine

Phase 12 converts persisted AI Query Engine data into measurable **AI Visibility** metrics and a single deterministic score.

**No LLM is used for scoring.** Entity Intelligence, Recommendations, Reports, and Chat are out of scope.

```text
AI Queries + AI Responses
        ↓
AI Visibility Engine
        ↓
Mention Rate · Citation Rate · Position · Semantic Match
        ↓
AI Visibility Score
```

## Package

```text
backend/app/services/ai/visibility/
├── weights.py      # Centralized component weights (sum = 1.0)
├── models.py       # ResponseInput, metrics, component/overall results
├── extraction.py   # Lexical semantic-alignment heuristic
├── metrics.py      # Raw rates and aggregates
├── scoring.py      # 0–100 scores + weight renormalization
└── engine.py       # Pure entry point (no DB)
```

Persistence lives in `ai_visibility_service.py`.

## Component weights

| Component | Weight |
| --- | --- |
| Mention Rate | 30% |
| Citation Rate | 25% |
| Position | 25% |
| Semantic Match | 20% |

Defined once in `weights.py`. Weights sum to exactly `1.0`.

## Availability

| Condition | Status |
| --- | --- |
| Zero successful responses | `UNAVAILABLE` (`score = null`, not zero) |
| Some queries lack responses | `PROVISIONAL` (scored from successes only) |
| Every query has a response | `AVAILABLE` |

## Metric formulas

### Mention Rate

```text
mention_rate = responses_where_brand_mentioned / successful_responses
mention_score = mention_rate × 100
```

### Citation Rate

```text
citation_rate = responses_with_citation_found / successful_responses
citation_score = citation_rate × 100
```

Uses Phase 11 `citation_found` (URL / markdown link / `[n]`). URLs are not verified.

### Position Score

Phase 11 `brand_position` is the **ordinal mention position inside the response**, not search ranking.

Per response:

| Position | Score |
| --- | --- |
| 1 | 100 |
| 2 | 75 |
| 3 | 50 |
| 4 | 25 |
| ≥ 5 or not mentioned | 0 |

Aggregate = mean across successful responses.

### Semantic Match

Deterministic lexical overlap (no embeddings):

1. Tokenize query/response (lowercase, punctuation stripped)
2. Remove a small English stop-word list
3. `overlap = |query_content_tokens ∩ response_tokens| / |unique query content tokens|`
4. If brand mentioned: `min(1.0, overlap + 0.10)`
5. Stop-word-only query → `null`; empty response → `0`

Persisted onto `ai_responses.semantic_alignment`. Aggregate mean → `semantic_score = alignment × 100`.

## Final score

When components are available:

```text
AI Visibility =
  mention_score × 0.30
+ citation_score × 0.25
+ position_score × 0.25
+ semantic_score × 0.20
```

Bounded to 0–100, rounded to one decimal place.

### Missing components

Unavailable components are **excluded** and remaining weights are renormalized. Never treated as zero.

## Persistence

On calculate:

- `audit.ai_visibility_score`
- `audit.semantic_score`
- `ai_responses.semantic_alignment`

**Not** modified: `overall_score`, `website_score`, `seo_score` (Phase 09 owns those).

## Freshness

When Phase 11 re-runs and replaces the AI query snapshot:

```text
audit.ai_visibility_score = NULL
audit.semantic_score = NULL
```

This prevents stale visibility against a new response set. Website/SEO/overall scores are untouched.

## API

| Method | Path |
| --- | --- |
| `POST` | `/api/v1/audits/{audit_id}/calculate-ai-visibility` |
| `GET` | `/api/v1/audits/{audit_id}/ai-visibility` |

Authenticated + owner isolation (404 cross-user). GET returns `UNAVAILABLE` with null scores until calculate has persisted a score (or when there are no successful responses).

Recalculation is deterministic and idempotent for an unchanged snapshot.

## Frontend

`/audits/:id` **AI Visibility** section: overall score, status badge, metrics, coverage, explanations, Calculate button. Unavailable values render as `—`.

## Why overall Audit Engine score is unchanged

Phase 09’s provisional overall uses Website Health + SEO only. Folding AI Visibility into overall score requires a later orchestration phase once Entity Strength also exists. Phase 12 intentionally does not silently alter `overall_score`.

## Limitations

- Lexical semantic match is not true NLU
- Citation heuristic is not authority verification
- Position is not search ranking
- No embeddings, RAG, web search, or background workers
