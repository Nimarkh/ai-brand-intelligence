# Scoring Methodology

Deterministic scoring architecture for AI Brand Intelligence.

Scores are **engineering metrics** computed from stored crawl, SEO, AI response, and entity evidence. They are **not** authoritative industry benchmarks, search-engine rankings, or proprietary AI-search rankings.

This document describes formulas as implemented. It does not change them.

---

## Overall score design

```text
Overall
├── Website Health   25%
├── SEO              20%
├── AI Visibility    35%
└── Entity Strength  20%
```

Defined in `backend/app/services/audit_engine/weights.py` as `FINAL_OVERALL_WEIGHTS`.

### Current overall persistence behavior

The Audit Engine (`POST /api/v1/audits/{id}/calculate-score`) persists:

| Column | Source |
| --- | --- |
| `website_score` | Website Health |
| `seo_score` | SEO component |
| `overall_score` | **Provisional** overall from Website Health + SEO only |

AI Visibility (`ai_visibility_score`) and Entity Strength (`entity_score`) are calculated by separate engines and stored on the audit. They are **not** folded into `overall_score` yet.

Provisional overall renormalizes the available final weights:

```text
available = 0.25 + 0.20 = 0.45
overall = website_health × (0.25/0.45) + seo × (0.20/0.45)
```

Status is **`PROVISIONAL`** when overall exists but AI Visibility or Entity Strength is still missing. The dashboard and Ask Intelligence surface that label explicitly.

Null means **unavailable**, never coerced to zero.

---

## Score range and determinism

| Property | Behavior |
| --- | --- |
| Range | 0–100 (clamped) |
| Precision | Typically quantized to two decimal places for persistence |
| Determinism | Identical stored inputs → identical outputs |
| LLM role | Core metrics do **not** depend on LLM judgment |

---

## Website Health (25% of designed overall)

Composite of four components:

| Component | Weight | Finding categories |
| --- | --- | --- |
| Technical | 30% | `STATUS`, `PERFORMANCE`, `CRAWL` |
| SEO | 30% | `TITLE`, `META_DESCRIPTION`, `CANONICAL`, `HEADINGS` |
| Content | 20% | `CONTENT` |
| Structured data | 20% | `STRUCTURED_DATA` |

```text
Website Health =
  technical × 0.30
+ seo       × 0.30
+ content   × 0.20
+ structured_data × 0.20
```

Requires at least one analyzable `WebsitePage`. Empty audits return unavailable (null), not zero.

---

## SEO score (20% of designed overall)

Persisted `seo_score` is the **SEO component** score (not the Website Health composite).

---

## Penalty model (Website Health / SEO components)

For each rule within a component:

```text
affected_page_rate = distinct_affected_pages / analyzable_pages
penalty_points = severity_weight × affected_page_rate × rule_weight
```

Audit-level findings (`page_id` null) use `affected_page_rate = 1.0`.

```text
category_penalty = min(100, sum(penalty_points))
category_score = clamp(100 - category_penalty, 0, 100)
```

Each finding maps to exactly one component (no double-counting).

### Severity weights

| Severity | Weight |
| --- | --- |
| HIGH | 15 |
| MEDIUM | 7 |
| LOW | 3 |
| INFO | 0 |

Rule weights live in `backend/app/services/audit_engine/weights.py` (for example: missing title `1.00`, missing meta `0.70`, 5xx `1.00`, duplicate title `0.55`).

Details: [audit-engine.md](audit-engine.md).

---

## AI Visibility (35% of designed overall)

Calculated only from persisted AI queries/responses. Does not call a provider at score time.

| Component | Weight |
| --- | --- |
| Mention | 30% |
| Citation | 25% |
| Position | 25% |
| Semantic | 20% |

Unavailable components are excluded and remaining weights are renormalized (never treated as zero).

### Important limitations

- **Position** is mention order **within the AI response text**, not SERP / search ranking.
- **Citation detection** is heuristic (URL / markdown link / `[n]` patterns); destinations are not verified.
- **Semantic alignment** is **lexical** token overlap with a small stop-word list — not embeddings or NLU.

Details: [ai-visibility.md](ai-visibility.md).

---

## Entity Strength (20% of designed overall)

Calculated from stored website pages and AI responses. No external knowledge graph.

| Component | Weight |
| --- | --- |
| Presence | 30% |
| Consistency | 25% |
| Structured identity | 25% |
| AI recognition | 20% |

Details: [entity-intelligence.md](entity-intelligence.md).

---

## Recommendations priority (related, not a brand score)

Recommendations use a separate deterministic ranking:

```text
priority_score = impact × 0.70 + (100 - effort) × 0.30
```

This does not modify score columns. See [recommendations.md](recommendations.md).

---

## Unavailable and provisional summary

| Status | Meaning |
| --- | --- |
| `AVAILABLE` | Dimension calculated from enough data |
| `UNAVAILABLE` | Not calculable or not yet run — score is **null** |
| `PROVISIONAL` | Overall exists using only currently available final dimensions (Website Health + SEO) |

---

## What scores are not

- Not Google / Bing rankings
- Not access to proprietary AI-answer ranking systems
- Not customer or market-share metrics
- Not claims about real-world production traffic or brand popularity
- Not industry certification or SEO agency “grade” standards

They are reproducible product metrics derived from the evidence this platform collects.
