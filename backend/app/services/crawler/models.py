from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class CrawlLimits:
    """Operator-configured bounds. Request payloads cannot change these."""

    max_pages: int
    max_depth: int
    timeout_seconds: float
    delay_seconds: float
    max_response_bytes: int
    user_agent: str
    max_redirects: int


@dataclass(frozen=True)
class ExtractedPage:
    title: str | None
    meta_description: str | None
    canonical_url: str | None
    word_count: int
    h1_count: int
    h2_count: int
    has_schema: bool
    schema_types: list[str]


@dataclass(frozen=True)
class CrawledPage:
    """One factual page observation. Scores and recommendations are out of scope."""

    url: str
    status_code: int | None
    title: str | None = None
    meta_description: str | None = None
    canonical_url: str | None = None
    word_count: int | None = None
    h1_count: int | None = None
    h2_count: int | None = None
    has_schema: bool | None = None
    schema_types: list[str] | None = None
    load_time_ms: int | None = None


@dataclass
class CrawlResult:
    pages: list[CrawledPage] = field(default_factory=list)


class CrawlStartError(Exception):
    """The start URL cannot be crawled. The message is for server logs only."""
