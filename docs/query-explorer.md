# Query Explorer

Phase 16 adds a read-only page for inspecting the AI queries and responses already stored by the Phase 11 AI Query Engine.

The page answers: what did we ask the AI, what did it answer, and how did the brand appear in that answer?

```text
Persisted AI queries + responses
              ↓
       Query Explorer
              ↓
       Search / filter / inspect
```

`/query-explorer` stays behind `authGuard`. The page calls `GET /api/v1/query-explorer` through `QueryExplorerService`. It does not run AI queries, call a provider, recalculate visibility, entity, or recommendation scores, or write explorer state to the database.

## Data source

The explorer reads existing rows only:

| Table | Use |
| ----- | --- |
| `audits` | Selected audit and the audit selector |
| `brands` | Ownership and brand name |
| `ai_queries` | Query text, category, timestamp |
| `ai_responses` | Response text and stored mention, position, citation, alignment, and latency |

No Query Explorer table is added. Responses are not copied into another table. Alembic is unchanged. Existing indexes on `ai_queries.audit_id`, `ai_queries.category`, and `ai_responses.query_id` are used. No new index was added.

## Endpoint

`GET /api/v1/query-explorer` requires the session cookie. Unauthenticated calls return 401.

| Parameter | Meaning |
| --------- | ------- |
| `audit_id` | Optional owned audit. A missing or foreign id returns 404. |
| `category` | One of `BRAND`, `PRODUCT`, `INDUSTRY`, `COMPETITOR`, `COMMERCIAL`, `INFORMATIONAL`. Anything else is a validation error. |
| `search` | Case-insensitive partial match on `query_text` only. Trimmed. `%` and `_` are matched literally. Maximum length 200. |
| `has_response` | `true` or `false`. |
| `brand_mentioned` | `true` or `false`, applied to the earliest response for the query. Queries with no response do not match. |
| `citation_found` | `true` or `false`, same earliest-response rule. |
| `page` | 1-based. Default 1. Maximum 10000. |
| `page_size` | One of `10`, `20`, `50`, `100`. Default 20. |

There is no free-form filter language and no client-controlled sort field.

## Response

Top-level fields:

| Field | Meaning |
| ----- | ------- |
| `audit` | Selected owned audit, or `null` when the user has no audits. |
| `audits` | Owned audits for the selector. Completed audits come first, then newer completion or creation time. |
| `summary` | Audit-wide counts. `null` when no audit is selected. Filters do not change this object. |
| `items` | The current page of queries. |
| `pagination` | `page`, `page_size`, `total`, `pages`. `total` is the filtered count. |

A query with no response is `has_response: false` and `response: null`. That is normal, not an error. When several responses exist for one query, the list shows the earliest (`created_at`, then `id`). Summary counts every `ai_responses` row.

The response body is returned in full. The API does not truncate it.

## Audit selection

Selection matches the Phase 15 rule and is scoped to `current_user.id`:

1. If `audit_id` is present, that audit is used only when its brand is owned by the session user. Otherwise the API returns 404 with the same body as a missing id.
2. If `audit_id` is omitted, the most recently completed owned audit is used (`completed_at` descending, then `created_at`, then `id`).
3. If none are completed, the newest owned audit is used (`created_at` descending, then `id`).
4. If the user has no audits, `audit` and `summary` are `null`.

The selected audit is reflected in the `audit_id` query parameter. It is not stored in `localStorage`. Changing the audit reloads the page, resets filters, and returns to page 1.

## Filtering and ordering

Filters and pagination run in SQL with bound parameters. The service does not load every query for the audit into Python and then filter it.

Default order, which is stable and not random:

```text
created_at ASC, category ASC, query_text ASC, id ASC
```

Phase 11 inserts queries in generator order. When those inserts share one timestamp, category, text, and id keep the page stable.

## Summary metrics

Calculated from persisted rows for the selected audit. They are not Phase 12 scores and they do not write `ai_visibility_score`.

| Metric | Calculation |
| ------ | ----------- |
| Queries | Count of `ai_queries` |
| Responses | Count of `ai_responses` |
| Failed | `total_queries - responses` |
| Mention rate | Responses with `brand_mentioned = true` / responses |
| Citation rate | Responses with `citation_found = true` / responses |

Mention rate and citation rate are `null` when the audit has no responses. They are not returned as `0`. The UI shows `—` for null.

A null `brand_mentioned` or `citation_found` does not count as true.

## Security and ownership

Every query joins audit to brand and filters `brands.owner_id` to the authenticated user.

```text
User → Brand → Audit → AI query → AI response
```

A user cannot read another user's audit, query, response, or brand name through this endpoint. A foreign `audit_id` returns 404 and does not include that audit's data.

## Response rendering

AI responses are plain text. The Angular page interpolates them into a `<pre>` element, so the browser escapes HTML and does not execute embedded markup. Line breaks are preserved with `white-space: pre-wrap`. Long responses stay in the DOM and scroll inside the detail panel. URLs are shown as text and are not turned into links.

The page does not use `[innerHTML]` for response text and does not render Markdown.

## Empty states

| Situation | UI |
| --------- | -- |
| No owned audits | “No audits to explore yet” with links to add or open a brand |
| Audit exists, no queries | “No AI queries have been run for this audit yet.” with a link to the audit |
| Queries exist, no responses | “Queries were generated, but no AI responses were recorded.” and the query list |
| Filters match nothing | “No queries match your filters.” Clear filters stays available |

## Limitations

- The explorer never starts an AI query run. Execution remains `POST /api/v1/audits/{audit_id}/ai-queries/run`.
- Summary rates describe stored response flags. They are not the Phase 12 AI Visibility score.
- The list displays the earliest response when a query has more than one. The summary still counts every response row, so `failed` can be negative in that unusual case.
- Search does not look at response text.
- The audit selector loads every owned audit's metadata. It does not page that list.
- Changing audits resets filters.
- Reports, chat, embeddings, RAG, web search, and background workers are out of scope.
