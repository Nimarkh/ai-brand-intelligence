"""Bounds and redaction for Ask Intelligence prompts. No second model call."""

from __future__ import annotations

import copy
import json
from typing import Any

from app.core.config import settings
from app.services.intelligence.models import (
    MAX_CONTEXT_CHARS,
    MAX_HISTORY_CONTENT_CHARS,
    MAX_HISTORY_MESSAGES,
    MAX_PROMPT_CHARS,
    HistoryTurn,
)

_LIST_PATHS = (
    ("seo", "findings"),
    ("queries", "items"),
    ("website", "pages"),
    ("recommendations", "items"),
)


def trim_history(history: list[HistoryTurn]) -> list[HistoryTurn]:
    """Keep the latest allowed turns. Drop anything that is not user or assistant."""
    kept: list[HistoryTurn] = []
    for turn in history:
        if turn.role not in {"user", "assistant"}:
            continue
        content = " ".join((turn.content or "").split())
        if not content:
            continue
        if len(content) > MAX_HISTORY_CONTENT_CHARS:
            content = content[: MAX_HISTORY_CONTENT_CHARS - 1] + "…"
        kept.append(HistoryTurn(role=turn.role, content=content))
    return kept[-MAX_HISTORY_MESSAGES:]


def bound_prompt_payload(payload: dict[str, Any], *, max_chars: int = MAX_CONTEXT_CHARS) -> dict[str, Any]:
    """Shrink a context dict deterministically until it fits the character budget."""
    data = copy.deepcopy(payload)
    if _length(data) <= max_chars:
        data["context_truncated"] = False
        return data

    data["context_truncated"] = True
    queries = data.get("queries")
    if isinstance(queries, dict):
        for item in queries.get("items") or []:
            if isinstance(item, dict):
                item["excerpt"] = None

    while _length(data) > max_chars:
        shrunk = False
        for path in _LIST_PATHS:
            items = _dig(data, path)
            if not isinstance(items, list) or not items:
                continue
            _set(data, path, items[: len(items) // 2] if len(items) > 1 else [])
            shrunk = True
            if _length(data) <= max_chars:
                break
        if not shrunk:
            data.pop("insights", None)
            break
    return data


def fit_history_lines(lines: list[str], *, reserved_chars: int) -> list[str]:
    """Drop oldest history lines until the remaining block fits beside the context."""
    budget = max(0, MAX_PROMPT_CHARS - reserved_chars)
    kept = list(lines)
    while kept and _joined_length(kept) > budget:
        kept.pop(0)
    return kept


def redact_sensitive(text: str) -> str:
    """Remove configured secrets if a model echoes them."""
    cleaned = text or ""
    for secret in _secrets_to_redact():
        if secret and secret in cleaned:
            cleaned = cleaned.replace(secret, "[redacted]")
    return cleaned.strip()


def _secrets_to_redact() -> list[str]:
    """Values that must never appear in client-facing AI answers."""
    secrets: list[str] = []
    for value in (
        settings.OPENAI_API_KEY,
        settings.JWT_SECRET,
    ):
        cleaned = (value or "").strip()
        if len(cleaned) >= 8:
            secrets.append(cleaned)
    try:
        from urllib.parse import urlsplit

        password = urlsplit(settings.DATABASE_URL).password
        if password and len(password) >= 4:
            secrets.append(password)
    except ValueError:
        pass
    return secrets


def _length(data: dict[str, Any]) -> int:
    return len(_dumps(data))


def _joined_length(lines: list[str]) -> int:
    return len("\n".join(lines))


def _dumps(data: Any) -> str:
    return json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def _dig(data: dict[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = data
    for key in path:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def _set(data: dict[str, Any], path: tuple[str, ...], value: Any) -> None:
    current = data
    for key in path[:-1]:
        current = current[key]
    current[path[-1]] = value
