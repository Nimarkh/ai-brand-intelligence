# AI Query Engine

Phase 11 adds the first **AI intelligence pipeline**: deterministic brand query generation, execution through the Phase 10 `AIProvider`, and persistence of queries/responses.

Phase 12’s AI Visibility Engine consumes this data (see `docs/ai-visibility.md`). Phase 16 Query Explorer reads the same persisted rows for inspection (see `docs/query-explorer.md`) and does not execute queries.

```text
AI Provider
    ↓
AI Query Engine
    ↓
AI Queries + AI Responses
    ↓
AI Visibility Engine (see docs/ai-visibility.md)
```

## Architecture

```text
backend/app/services/ai/query_engine/
├── generator.py   # Deterministic templates → query list
├── executor.py    # One query → AIProvider.generate
├── extraction.py  # Basic mention / position / citation heuristics
├── service.py     # Orchestration + persistence
├── models.py      # Internal dataclasses
└── categories.py  # Stable AiQueryCategory order
```

The Query Engine depends only on `AIProvider`. It must **not** import `openai` / `OpenAI` / `AsyncOpenAI`.

## Categories

Uses the existing `AiQueryCategory` enum:

- `BRAND`
- `PRODUCT`
- `INDUSTRY`
- `COMPETITOR`
- `COMMERCIAL`
- `INFORMATIONAL`

## Deterministic query generation

Query lists are built from **fixed templates** filled with Brand fields (`name`, `industry`, `country`, `target_market`, etc.). No LLM is called during generation. No web scraping.

Default template set yields **18** queries (3 per category). Generation:

1. Substitute brand context
2. Normalize whitespace
3. Deduplicate case-insensitively
4. Truncate to `AI_QUERY_MAX_PER_AUDIT` with category round-robin diversity

### Limits

```text
AI_QUERY_MAX_PER_AUDIT=18   # default; allowed range 1–50
```

The service never silently creates unlimited queries. Values above the template count have no practical effect.

## Execution flow

For each generated query:

1. Persist `ai_queries` row
2. Call `AIProvider.generate` with a fixed system prompt and the query as the user prompt
3. On success: extract signals and persist `ai_responses`
4. On failure: keep the query row, **do not** invent a response, continue

`AuditStatus` is **unchanged** (crawl lifecycle from Phase 07).

## Response extraction (Phase 11 only)

| Field | Behavior |
| --- | --- |
| `brand_mentioned` | Case-insensitive brand name match (punctuation-tolerant) |
| `brand_position` | 1-based index of this brand among left-to-right unique Title Case / acronym candidates (plus brand spans). **Not** search ranking. `NULL` if not mentioned. |
| `citation_found` | Heuristic: `http(s)` URL, markdown link, or `[n]` marker. Not an authority claim. |
| `semantic_alignment` | Always `NULL` until Phase 12 |

## Partial failure

Example: 18 queries, 15 success, 3 failures → 18 query rows, 15 response rows. API returns `responses_succeeded` / `responses_failed`. Status remains `COMPLETED` for the run payload.

## Re-run behavior

`POST .../ai-queries/run` replaces the audit’s AI query snapshot:

1. Delete existing `ai_responses` for that audit’s queries
2. Delete existing `ai_queries` for that audit
3. Generate and execute a fresh deterministic set

Does **not** affect `WebsitePage`, `SeoFinding`, or audit scores.

## API endpoints

All authenticated; ownership via `get_owned_audit` (cross-user → 404).

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/audits/{audit_id}/ai-queries/run` | Generate + execute snapshot |
| `GET` | `/api/v1/audits/{audit_id}/ai-queries` | List queries (+ `has_response`) |
| `GET` | `/api/v1/audits/{audit_id}/ai-queries/{query_id}` | Query + response detail |

No arbitrary user-prompt endpoint. OpenAI keys are never exposed.

## Security

- Authenticated endpoints only
- Owner isolation (404 for other users)
- Controlled generator text only
- Full AI response bodies are not logged by default
- Provider credentials stay server-side

## Frontend

`/audits/:id` includes an **AI Query Analysis** section: run button, counts, category badges, expandable responses, mention/citation/position indicators, and semantic alignment shown as `—`. Explicit note that AI Visibility score is not calculated yet.

## Explicit non-goals (Phase 11)

- AI Visibility / mention / citation / position / semantic **scores**
- Entity Intelligence, Recommendations, Reports, Chat
- Embeddings, vector DB, RAG, web search, Celery, streaming, tool calling
