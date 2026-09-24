"""Deterministic brand-name normalization and page/AI signal extraction."""

from __future__ import annotations

import re
import unicodedata
from urllib.parse import urlsplit

from app.services.entity.models import AiResponseInput, PageInput
from app.services.entity.weights import LEGAL_SUFFIXES

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)
_WS_RE = re.compile(r"\s+")


def normalize_brand_name(value: str) -> str:
    """Normalize a brand name for matching only (does not mutate Brand rows).

    Steps:
    1. Unicode NFKC
    2. lowercase
    3. strip punctuation (letters/digits/underscore/whitespace kept)
    4. collapse whitespace
    5. remove trailing common legal suffixes (inc, ltd, llc, …)
    """
    text = unicodedata.normalize("NFKC", value or "")
    text = text.casefold()
    text = _PUNCT_RE.sub(" ", text)
    text = _WS_RE.sub(" ", text).strip()
    if not text:
        return ""
    tokens = text.split(" ")
    while len(tokens) > 1 and tokens[-1] in LEGAL_SUFFIXES:
        tokens.pop()
    return " ".join(tokens)


def brand_appears_in_text(normalized_brand: str, text: str | None) -> bool:
    """True when normalized brand tokens appear as a contiguous subsequence."""
    if not normalized_brand or not text:
        return False
    haystack = normalize_brand_name(text)
    if not haystack:
        return False
    if normalized_brand == haystack:
        return True
    # Word-boundary-ish: surround with spaces after normalizing both sides.
    return f" {normalized_brand} " in f" {haystack} "


def origin_of(url: str | None) -> str | None:
    if not url:
        return None
    parts = urlsplit(url.strip())
    if not parts.scheme or not parts.netloc:
        return None
    return f"{parts.scheme.lower()}://{parts.netloc.lower()}"


def same_origin(left: str | None, right: str | None) -> bool:
    a = origin_of(left)
    b = origin_of(right)
    return bool(a and b and a == b)


def coerce_schema_types(raw: object) -> tuple[str, ...]:
    if raw is None:
        return ()
    if isinstance(raw, str):
        cleaned = raw.strip()
        return (cleaned,) if cleaned else ()
    if isinstance(raw, (list, tuple)):
        items: list[str] = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                items.append(item.strip())
        return tuple(items)
    return ()


def page_input_from_row(
    *,
    page_id,
    url: str,
    title: str | None,
    meta_description: str | None,
    canonical_url: str | None,
    has_schema: bool | None,
    schema_types: object,
) -> PageInput:
    return PageInput(
        id=page_id,
        url=url,
        title=title,
        meta_description=meta_description,
        canonical_url=canonical_url,
        has_schema=has_schema,
        schema_types=coerce_schema_types(schema_types),
    )


def ai_input_from_row(
    *,
    response_id,
    brand_mentioned: bool | None,
    brand_position: int | None,
) -> AiResponseInput:
    return AiResponseInput(
        response_id=response_id,
        brand_mentioned=bool(brand_mentioned),
        brand_position=brand_position,
    )
