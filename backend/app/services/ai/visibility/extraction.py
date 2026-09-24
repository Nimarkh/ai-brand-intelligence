"""Deterministic lexical semantic-alignment heuristic. No LLM / embeddings."""

from __future__ import annotations

import re
from decimal import Decimal

from app.services.ai.visibility.weights import SEMANTIC_BRAND_BONUS

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# Small controlled English stop-word list (not an NLP library).
_STOP_WORDS = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "if",
        "then",
        "else",
        "when",
        "at",
        "by",
        "for",
        "with",
        "about",
        "against",
        "between",
        "into",
        "through",
        "during",
        "before",
        "after",
        "above",
        "below",
        "to",
        "from",
        "up",
        "down",
        "in",
        "out",
        "on",
        "off",
        "over",
        "under",
        "again",
        "further",
        "once",
        "here",
        "there",
        "all",
        "any",
        "both",
        "each",
        "few",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "nor",
        "not",
        "only",
        "own",
        "same",
        "so",
        "than",
        "too",
        "very",
        "can",
        "will",
        "just",
        "don",
        "should",
        "now",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "of",
        "as",
        "i",
        "me",
        "my",
        "we",
        "our",
        "you",
        "your",
        "he",
        "she",
        "it",
        "they",
        "them",
        "their",
        "this",
        "that",
        "these",
        "those",
        "what",
        "which",
        "who",
        "whom",
        "how",
        "why",
        "where",
        "should",
        "would",
        "could",
        "may",
        "might",
        "must",
        "shall",
    }
)


def tokenize_content(text: str) -> list[str]:
    """Lowercase, strip punctuation via token regex, drop stop words."""
    tokens = _TOKEN_RE.findall((text or "").lower())
    return [token for token in tokens if token not in _STOP_WORDS]


def semantic_alignment(
    query_text: str,
    response_text: str,
    *,
    brand_mentioned: bool,
) -> Decimal | None:
    """Lexical overlap of query content tokens found in the response.

    ``overlap = |query_tokens ∩ response_tokens| / |query_tokens|`` using
    unique query content tokens. If the brand is mentioned, add
    ``SEMANTIC_BRAND_BONUS`` (capped at 1.0).

    Returns:
        None when the query has no meaningful content tokens.
        Decimal('0') when the response is empty (and query has tokens).
        Otherwise a value in [0, 1].
    """
    query_tokens = tokenize_content(query_text)
    if not query_tokens:
        return None

    if not (response_text or "").strip():
        return Decimal("0")

    response_set = set(tokenize_content(response_text))
    unique_query = list(dict.fromkeys(query_tokens))  # stable unique
    if not unique_query:
        return None

    hits = sum(1 for token in unique_query if token in response_set)
    overlap = Decimal(hits) / Decimal(len(unique_query))

    if brand_mentioned:
        overlap = min(Decimal("1"), overlap + SEMANTIC_BRAND_BONUS)

    return _quantize_alignment(overlap)


def _quantize_alignment(value: Decimal) -> Decimal:
    return value.quantize(Decimal("0.0001"))
