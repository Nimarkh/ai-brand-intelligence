"""Deterministic brand-mention / citation extraction. No NLP libraries."""

from __future__ import annotations

import re

from app.services.ai.query_engine.models import ResponseExtractions

_URL_RE = re.compile(r"https?://[^\s<>\"']+", re.IGNORECASE)
_MARKDOWN_LINK_RE = re.compile(r"\[[^\]]+\]\([^)]+\)")
_CITATION_MARKER_RE = re.compile(r"\[\d{1,3}\]")
# Title-case / acronym candidates used only for relative position ordering.
_CANDIDATE_RE = re.compile(
    r"\b(?:[A-Z][a-z0-9]+(?:\s+[A-Z][a-z0-9]+)+|[A-Z]{2,}(?:\s+[A-Z]{2,})*)\b"
)


def extract_response_signals(response_text: str, brand_name: str) -> ResponseExtractions:
    """Populate brand_mentioned, brand_position, and citation_found.

    brand_mentioned:
        True when ``brand_name`` appears in the response (case-insensitive,
        punctuation-tolerant via word-boundary-ish matching).

    brand_position:
        1-based index of this brand among identifiable brand-like mentions
        encountered left-to-right in the response. Candidates are Title Case
        multi-word phrases / acronyms, plus the brand name itself wherever it
        appears. This is NOT a search-engine ranking. Null when not mentioned.

    citation_found:
        True when the text contains an http(s) URL, a markdown link, or a
        numeric citation marker like ``[1]``. Not an authority claim.
    """
    text = response_text or ""
    brand = (brand_name or "").strip()
    mentioned = _brand_mentioned(text, brand) if brand else False
    position = _brand_position(text, brand) if mentioned and brand else None
    citation = _citation_found(text)
    return ResponseExtractions(
        brand_mentioned=mentioned,
        brand_position=position,
        citation_found=citation,
    )


def _brand_mentioned(text: str, brand_name: str) -> bool:
    pattern = re.compile(rf"(?<!\w){re.escape(brand_name)}(?!\w)", re.IGNORECASE)
    return pattern.search(text) is not None


def _brand_position(text: str, brand_name: str) -> int | None:
    """Return 1-based order of the brand among unique candidate mentions."""
    brand_key = _normalize_key(brand_name)
    if not brand_key:
        return None

    ordered: list[str] = []
    seen: set[str] = set()

    # Scan leftover-to-right by finding all candidate spans and brand spans.
    events: list[tuple[int, str]] = []
    for match in _CANDIDATE_RE.finditer(text):
        events.append((match.start(), match.group(0)))
    brand_re = re.compile(rf"(?<!\w){re.escape(brand_name)}(?!\w)", re.IGNORECASE)
    for match in brand_re.finditer(text):
        events.append((match.start(), match.group(0)))

    events.sort(key=lambda item: (item[0], item[1].lower()))
    for _, raw in events:
        key = _normalize_key(raw)
        if not key or key in seen:
            continue
        seen.add(key)
        ordered.append(key)

    try:
        return ordered.index(brand_key) + 1
    except ValueError:
        return None


def _citation_found(text: str) -> bool:
    if _URL_RE.search(text):
        return True
    if _MARKDOWN_LINK_RE.search(text):
        return True
    if _CITATION_MARKER_RE.search(text):
        return True
    return False


def _normalize_key(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).casefold()
