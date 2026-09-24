# Ask Intelligence

Phase 17 adds an analyst-style question interface for one owned audit. The assistant explains data the platform already stored. It is not a general-purpose chatbot.

```text
Angular (/intelligence-chat)
        ↓
POST /api/v1/intelligence/ask
        ↓
Intelligence service
        ↓
Context builder (deterministic, bounded)
        ↓
AIProvider  (MockAIProvider or OpenAIProvider)
        ↓
Answer + evidence references
```

The language model never receives a database session, SQL, or a tool that can query the application. The frontend never calls OpenAI and never sees `OPENAI_API_KEY`.

## Route

`/intelligence-chat` is the existing shell route. It stays behind `authGuard`. The sidebar label remains **Ask Intelligence**.

Preferred selection:

```text
/intelligence-chat?audit_id=UUID
```

The selected audit is not stored in `localStorage`.

## Audit selection

`GET /api/v1/intelligence/audits` lists audits owned by the signed-in user. Order:

1. Completed audits first
2. Newest completion date
3. Newest creation date

If `audit_id` is present, it must belong to the user. A missing or foreign id returns **404** with the same not-found response used elsewhere. The response does not reveal that another user's audit exists.

If `audit_id` is omitted:

1. Latest completed owned audit
2. Otherwise the latest owned audit
3. Otherwise an empty workspace

The same rule is used by `POST /api/v1/intelligence/ask`. When the user has no audits, the ask endpoint returns an empty application response and does not call the provider.

Changing the audit updates `?audit_id=`, clears the on-screen conversation, and reloads the audit list. It does not write audit data.

## Ask endpoint

`POST /api/v1/intelligence/ask`

```json
{
  "audit_id": "UUID",
  "question": "Why is my AI visibility score low?",
  "history": [
    { "role": "user", "content": "..." },
    { "role": "assistant", "content": "..." }
  ]
}
```

| Rule | Limit |
| ---- | ----- |
| Question | 1–2000 characters, not blank |
| History messages | 10 |
| History content | 4000 characters each |
| Roles | `user` or `assistant` only |

`system` is rejected. The server writes the system prompt. Extra fields are rejected.

Success:

```json
{
  "audit_id": "...",
  "answer": "...",
  "context": {
    "brand_name": "Acme",
    "audit_date": "2026-09-23T12:00:00Z",
    "overall_score": 72.0,
    "overall_status": "PROVISIONAL"
  },
  "sources": [
    { "type": "seo_finding", "id": "...", "label": "Missing meta description — 7 pages" }
  ],
  "empty": false,
  "message": null
}
```

`overall_status` is `PROVISIONAL` when a stored overall score exists but AI visibility or entity score is still null. Ask Intelligence does not recalculate Phase 09, 12, 13, or 14 scores.

Provider failures return HTTP 503:

- `AI analysis is temporarily unavailable. Please try again.`
- `The analysis timed out. Please try again.`

Those bodies do not include stack traces, API keys, or provider payloads.

## Context retrieval

`backend/app/services/intelligence/` loads rows for the selected audit and builds a typed context object:

| Area | What is included |
| ---- | ---------------- |
| Brand | Name, website, industry, country, target market, description |
| Audit | Status, dates, persisted scores |
| Website | Page counts, status distribution, average load time, structured-data coverage, a bounded page sample |
| SEO | Counts by severity and category, common titles, a bounded finding sample |
| AI visibility | Query and response counts, mention and citation rates when the visibility snapshot has them, component status |
| Entity | Presence, consistency, structured identity, and AI recognition when the entity snapshot has them |
| Recommendations | Highest-priority stored recommendations |
| Insights | The existing dashboard insight sentences, when the snapshot has the counts they need |

Visibility and entity snapshots are read through the existing load functions. Those calls do not persist new scores.

### Limits

| Slice | Maximum |
| ----- | ------- |
| SEO findings | 20 |
| Recommendations | 20 |
| AI queries | 30 |
| AI response excerpts | 20 |
| Website pages | 20 |
| Serialized context | 14,000 characters |
| Provider prompt | 24,000 characters |
| History sent to the provider | last 10 messages |

Records are chosen deterministically (severity, priority, mention state, then stable ids). If the serialized context is still too large, lists are shortened in a fixed order. A second model is not used to summarize.

## Intents

A keyword router picks one category. The first match wins.

| Intent | Examples |
| ------ | -------- |
| `QUERIES` | Which AI queries don't mention my brand? |
| `AI_VISIBILITY` | Why is AI visibility low? How often is my brand mentioned? |
| `ENTITY` | How strong is my entity? How consistent is my brand identity? |
| `SEO` | What SEO problems do I have? |
| `WEBSITE` | How healthy is my website? Are my pages slow? |
| `RECOMMENDATIONS` | What should I fix first? What are the biggest opportunities? |
| `SCORES` | Why is my score low? Why is the overall score provisional? |
| `OVERVIEW` | Give me an overview. How is my brand doing? |
| `GENERAL` | Anything else, including questions outside the audit |

`GENERAL` sends the full bounded context. The system prompt tells the model to stay on this audit and to say when the context is not enough. Unrelated questions, such as general knowledge or jokes, are out of scope.

## Evidence

Evidence is chosen in the backend from the question intent and the retrieved rows. The model is not asked to invent source ids.

Each source has `type`, `id`, and `label`. Types include `seo_finding`, `recommendation`, `ai_query`, `ai_response`, `website_page`, `audit_score`, `ai_visibility_metric`, and `entity_metric`. Every id comes from the selected audit (or is that audit's id for score and metric summaries).

The page shows the cards under the answer. If a response has no sources, the UI says that no direct evidence was available.

## Provider

Ask Intelligence uses `get_ai_provider()`:

- `AI_PROVIDER=mock` (the default) uses `MockAIProvider`. No API key is required. Intelligence prompts receive a deterministic analyst-style reply derived from the question, intent, and brand name.
- `AI_PROVIDER=openai` uses the existing `OpenAIProvider`, `OPENAI_MODEL`, and `OPENAI_TIMEOUT_SECONDS`.

There is no streaming, tool calling, embeddings, or retry layer beyond what the provider already does.

## Conversation lifetime

Messages live in component memory for the current page view:

```text
id, role, content, createdAt
```

They are not written to PostgreSQL and not stored in `localStorage`. Reload clears them. **Clear conversation** clears them and keeps the audit. Only the last 10 completed messages are sent back as `history`, plus a fresh context object.

## Security

- The route and both endpoints require the session cookie.
- Audit ownership is enforced in SQL. Foreign ids return 404.
- The client cannot supply a system message.
- Question and history sizes are capped.
- Responses are redacted if they contain the configured `OPENAI_API_KEY`.
- Assistant text is rendered as plain text. The page does not assign it to `innerHTML`.

## Limitations

- No persistent chat history.
- No web search.
- No external knowledge retrieval.
- No embeddings.
- No RAG.
- No streaming.
- No tool calling.
- Answers depend on the selected audit.
- AI responses are generated from bounded persisted context.
- `MockAIProvider` is deterministic and intended for development and testing.
- AI-generated explanations are interpretations of stored data, not new measurements.
- Reports are not part of this phase.
- Query Explorer is unchanged.
