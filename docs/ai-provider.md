# AI Provider Abstraction

Phase 10 adds a **provider-agnostic AI layer**. It does **not** implement AI Visibility scoring, entity intelligence, recommendations, reports, or chat. Phase 11’s AI Query Engine consumes this abstraction (see `docs/ai-query-engine.md`).

## Purpose

Future phases call LLMs through a common interface so business logic never depends on the OpenAI SDK (or any other vendor SDK) directly.

```
Future feature code
        │
        ▼
   AIProvider.generate(AIRequest) → AIResponse
        │
   ┌────┴────┐
   ▼         ▼
 MockAI   OpenAIProvider
Provider  (SDK isolated here)
```

## Package

```
backend/app/services/ai/
  models.py           # AIRequest, AIResponse, errors
  provider.py         # AIProvider Protocol
  factory.py          # get_ai_provider()
  mock_provider.py    # deterministic local provider
  openai_provider.py  # OpenAI SDK adapter only
```

## Interface

```python
from app.services.ai import AIRequest, get_ai_provider

provider = get_ai_provider()
response = await provider.generate(
    AIRequest(prompt="...", system_prompt="...", temperature=0.0, max_tokens=512)
)
```

`AIRequest` / `AIResponse` are provider-neutral. OpenAI request/response objects never leave `openai_provider.py`.

## Providers

| Provider | `AI_PROVIDER` | Network | Notes |
| -------- | ------------- | ------- | ----- |
| Mock | `mock` (default) | No | Deterministic text + usage metadata |
| OpenAI | `openai` | Yes | Requires `OPENAI_API_KEY` |

## Configuration

| Variable | Default | Description |
| -------- | ------- | ----------- |
| `AI_PROVIDER` | `mock` | `mock` or `openai` |
| `OPENAI_API_KEY` | empty | Required only for `openai` |
| `OPENAI_MODEL` | `gpt-4o-mini` | Default chat model |
| `OPENAI_TIMEOUT_SECONDS` | `30` | SDK timeout |

Local development and tests work **without** an OpenAI API key when `AI_PROVIDER=mock`.

Unsupported `AI_PROVIDER` values raise `AIConfigurationError`.

## Factory and DI

- Prefer `get_ai_provider(config=None)` over constructing providers in feature code.
- FastAPI can depend on `get_configured_ai_provider` from `app.api.deps` in later phases.
- No process-wide singleton: each call builds a provider from settings (tests can pass a custom `Settings` or override the dependency).

## Errors

| Error | Meaning |
| ----- | ------- |
| `AIConfigurationError` | Bad/missing config (key, provider name, auth) |
| `AIRequestError` | Invalid request or provider rejection |
| `AIProviderError` | Timeouts, connectivity, other API failures |

Raw OpenAI SDK exceptions are mapped inside `openai_provider.py` and are not leaked as the public error type.

## Security

- API keys live only in backend environment configuration.
- Keys are never stored in the database or sent to the frontend.
- Phase 10 does **not** expose `POST /api/v1/ai/generate` or any arbitrary prompt endpoint.
- Logs may include provider, model, and latency — not API keys, Authorization headers, or full prompts by default.

## What this phase does **not** do

- No AI Visibility score
- No Entity / semantic intelligence
- No AI Query Engine persistence into `ai_queries` / `ai_responses`
- No crawler / SEO analyzer / Audit Engine AI calls
- No streaming, embeddings, tool calling, or retries

## How future phases should consume this

1. Obtain `AIProvider` via `get_ai_provider()` or FastAPI `Depends(get_configured_ai_provider)`.
2. Build an `AIRequest` with product-specific prompts.
3. Call `await provider.generate(request)`.
4. Persist or score using the returned `AIResponse.text` / metadata — never import `openai` in feature modules.
