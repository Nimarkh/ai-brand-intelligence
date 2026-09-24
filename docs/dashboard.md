# Dashboard

The Main Intelligence Dashboard answers five questions from persisted data only:

1. How healthy is my website?
2. How strong is my SEO?
3. How visible is my brand to AI systems?
4. How clearly is my brand represented as an entity?
5. What should I work on next?

`/dashboard` stays behind `authGuard`. The page calls `GET /api/v1/dashboard/overview` through `DashboardService`. There is no mock dashboard API. The dashboard does not crawl, score, call AI providers, or invent values.

## Endpoint

`GET /api/v1/dashboard/overview` requires the session cookie. Unauthenticated calls return 401.

Optional query parameter:

| Parameter | Meaning |
| --------- | ------- |
| `brand_id` | When present and owned by the session user, audit selection and workspace counts are narrowed to that brand. Unknown or foreign brand IDs are ignored (no leak, no 404). |

## Response structure

Top-level `DashboardOverview` fields:

| Field | Meaning |
| ----- | ------- |
| `workspace` | `brand_count`, `audit_count`, `completed_audit_count` for the authenticated user (optionally brand-filtered). |
| `selected_audit` | Deterministically chosen audit context, or `null`. |
| `scores` | `overall`, `website`, `seo`, `ai_visibility`, `entity` score cards. |
| `snapshot` | Secondary metrics that exist for the selected audit. |
| `insights` | 0–4 deterministic factual insights. |
| `recommendations` | Up to 5 Phase 14 recommendations in engine ranking order. |
| `freshness` | Accurate timestamps when related rows exist. |
| `brands` | Owned brands for the selector (`id`, `name`), ordered by name then id. |
| `selection_rule` | Human-readable description of audit selection. |

Responses never include `owner_id`, passwords, or ORM objects. A `user_id` / foreign `brand_id` query parameter cannot switch the owner.

## Audit selection strategy

Selection is deterministic and ownership-scoped:

1. Most recently **completed** owned audit (`completed_at` DESC, then `created_at` DESC, then `id` DESC).
2. If none completed, most recent owned audit of any status (`created_at` DESC, `id` DESC).
3. If the user has no audits, `selected_audit` is `null` (empty / onboarding states).

Optional `brand_id` applies the same rule within that owned brand only.

## Score ownership

The dashboard is a presentation/orchestration layer. It does **not** recalculate scores.

| Dashboard field | Source column / phase |
| --------------- | --------------------- |
| Website Health | `audit.website_score` (Phase 09) |
| SEO | `audit.seo_score` (Phase 09) |
| AI Visibility | `audit.ai_visibility_score` (Phase 12) |
| Entity Strength | `audit.entity_score` (Phase 13) |
| Overall | `audit.overall_score` (Phase 09 provisional overall) |

Phase 09–14 formulas are unchanged.

## Overall status

`scores.overall.status`:

| Status | When |
| ------ | ---- |
| `UNAVAILABLE` | `overall_score` is null |
| `PROVISIONAL` | `overall_score` exists and AI Visibility **or** Entity Strength is unavailable |
| `AVAILABLE` | `overall_score` exists and both AI Visibility and Entity Strength scores exist |

`AVAILABLE` does **not** mean the stored overall includes AI/Entity. Phase 09 still stores a website+SEO provisional overall. The UI labels provisional clearly:

> Based on currently available website and SEO signals. AI Visibility and Entity Strength are not yet included in the overall score.

The stored `overall_score` is never rewritten by the dashboard.

## Unavailable scores

Layer cards use:

- `score: null`
- `status: UNAVAILABLE`
- explanation `Not calculated yet`

The UI renders `—`. Null is never coerced to `0`.

## Snapshot metrics

Only metrics that can be derived from persisted rows are returned. Examples:

- pages crawled (`website_pages` count)
- SEO findings / high-severity findings
- AI queries, successful first-responses, response coverage, mention rate
- structured identity coverage (`has_schema` / pages)
- recommendation totals by priority

Missing layers omit related snapshot fields (`null`) instead of inventing zeros.

## Key insights

`app/services/dashboard/insights.py` builds 2–4 (max 4) deterministic insights from the snapshot. No LLM. Sources are labeled (`SEO_FINDINGS`, `AI_VISIBILITY`, `ENTITY`, `RECOMMENDATIONS`, `WEBSITE`). Insights are factual and traceable to counts.

## Recommendation preview

Uses `recommendation_service.list_recommendations` ranking (HIGH → MEDIUM → LOW, then impact desc, effort asc). The dashboard takes the first **5** items and does not re-rank. Empty list means recommendations were not calculated yet.

The UI links “View all recommendations” to `/audits/{selected_audit.id}` where the full Phase 14 list already lives. The standalone `/recommendations` route remains a future-phase placeholder.

## Freshness

Timestamps are max(`created_at`) from related tables when present:

- last website crawl → `website_pages`
- last SEO analysis → `seo_findings`
- last AI analysis → `ai_responses`
- last recommendations calculation → `recommendations`

Entity analysis has no dedicated timestamp column; the dashboard does not invent one.

## Ownership / security

Every query filters `Brand.owner_id = current_user.id`. Cross-user brands and audits never appear. Ignoring an unowned `brand_id` keeps the response scoped to the session user.

## Frontend

`/dashboard` shows:

1. Overall Intelligence card (radial score + provisional/unavailable label)
2. Four core score cards (Website, SEO, AI Visibility, Entity)
3. Intelligence snapshot
4. Key insights
5. Recommendations preview
6. Recent audit context + freshness
7. Empty / partial / loading / error states

Multi-brand users get a brand selector persisted as `?brand_id=`. Selection does not use `localStorage` for brand data.

Dark mode uses existing theme tokens. Layout stacks to one column on small viewports.

## Empty and partial states

| Situation | UI |
| --------- | -- |
| 0 brands, 0 audits | Onboarding: “Build your first brand intelligence profile” + Add Brand |
| Brands, no audits | Workspace counts + CTA to open brands; no fake scores |
| Crawl/SEO without AI/Entity | Available layers render; others show `—` / Not calculated yet; overall provisional when overall exists |
| All layers present | All four cards + overall status `AVAILABLE` (stored Phase 09 overall unchanged) |

## Limitations

- Overall score is still Phase 09’s website+SEO provisional value; a future orchestration phase may incorporate AI/Entity into a true product overall.
- Brand selector filters the selected audit; it is not a multi-brand comparison board.
- Entity freshness is omitted (no dedicated timestamp).
- Standalone Recommendations / AI Visibility / Entity nav pages remain placeholders; deep analysis stays on audit detail.
- Query inspection lives on `/query-explorer`. See [query-explorer.md](query-explorer.md). Chat, Reports, workers, and external APIs are not part of the dashboard.

## Schema

This phase does not change the database. Alembic head is unchanged. The dashboard only reads existing tables.
