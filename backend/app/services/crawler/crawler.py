from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass
from urllib.parse import urljoin, urlsplit

import httpx

from app.services.crawler.models import CrawledPage, CrawlLimits, CrawlResult, CrawlStartError, ExtractedPage
from app.services.crawler.parser import extract_links, is_html_content_type, parse_html
from app.services.crawler.robots import fetch_robots
from app.services.crawler.url_utils import (
    Resolver,
    endpoint_is_allowed,
    is_ignorable_reference,
    normalize_url,
    origin_root,
    same_crawl_origin,
)

logger = logging.getLogger("app.crawler")

_REDIRECT_STATUSES = frozenset({301, 302, 303, 307, 308})
_SKIPPED_EXTENSIONS = frozenset(
    {
        ".png",
        ".jpg",
        ".jpeg",
        ".gif",
        ".webp",
        ".svg",
        ".ico",
        ".bmp",
        ".avif",
        ".pdf",
        ".css",
        ".js",
        ".mjs",
        ".map",
        ".woff",
        ".woff2",
        ".ttf",
        ".eot",
        ".otf",
        ".mp4",
        ".webm",
        ".mp3",
        ".wav",
        ".ogg",
        ".avi",
        ".mov",
        ".zip",
        ".gz",
        ".rar",
        ".7z",
    }
)


@dataclass(frozen=True)
class CrawlContext:
    audit_id: str
    brand_id: str


class WebsiteCrawler:
    """Bounded breadth-first crawler.

    The crawler does not touch the database and does not score pages. A worker
    can call ``crawl`` later without changing this class.
    """

    def __init__(
        self,
        limits: CrawlLimits,
        client: httpx.Client,
        resolver: Resolver | None = None,
    ) -> None:
        self.limits = limits
        self._client = client
        self.resolver = resolver
        self._request_count = 0
        self._closed = False

    def close(self) -> None:
        if not self._closed:
            self._client.close()
            self._closed = True

    def crawl(self, start_url: str, context: CrawlContext | None = None) -> CrawlResult:
        origin = normalize_url(start_url)
        if origin is None:
            raise CrawlStartError("Start URL is not a valid http(s) URL.")
        if not endpoint_is_allowed(origin, self.resolver):
            raise CrawlStartError("Start URL destination is not allowed.")

        audit_id = context.audit_id if context else "-"
        brand_id = context.brand_id if context else "-"
        logger.info("crawl_started audit_id=%s brand_id=%s", audit_id, brand_id)

        robots = fetch_robots(
            self._client,
            origin_root(origin),
            self.limits.user_agent,
            throttle=self._throttle,
        )
        pages: list[CrawledPage] = []
        visited: set[str] = set()
        fetched_urls: set[str] = set()
        queue: deque[tuple[str, int]] = deque()

        if robots.allows(origin):
            visited.add(origin)
            queue.append((origin, 0))
        else:
            logger.info("crawl_start_disallowed audit_id=%s", audit_id)

        fetches = 0
        while queue and fetches < self.limits.max_pages:
            url, depth = queue.popleft()
            if url in fetched_urls:
                continue
            fetched_urls.add(url)
            fetches += 1
            page, html = self._retrieve(url, audit_id)
            if page is not None:
                fetched_urls.add(page.url)
                pages.append(page)
            if html and page is not None and depth < self.limits.max_depth:
                self._enqueue_links(html, page.url, depth + 1, origin, robots.allows, visited, queue)

        logger.info(
            "crawl_fetched audit_id=%s brand_id=%s pages=%s",
            audit_id,
            brand_id,
            len(pages),
        )
        return CrawlResult(pages=pages)

    def _enqueue_links(
        self,
        html: str,
        page_url: str,
        depth: int,
        origin: str,
        allows,
        visited: set[str],
        queue: deque[tuple[str, int]],
    ) -> None:
        if depth > self.limits.max_depth:
            return
        for href in extract_links(html):
            if is_ignorable_reference(href):
                continue
            normalized = normalize_url(href, base=page_url)
            if normalized is None or normalized in visited:
                continue
            if not same_crawl_origin(normalized, origin):
                continue
            if _has_skipped_extension(normalized):
                continue
            if not allows(normalized):
                visited.add(normalized)
                continue
            if not endpoint_is_allowed(normalized, self.resolver):
                visited.add(normalized)
                logger.info("crawl_url_blocked")
                continue
            visited.add(normalized)
            queue.append((normalized, depth))

    def _retrieve(self, url: str, audit_id: str) -> tuple[CrawledPage | None, str | None]:
        started = time.perf_counter()
        current = url
        seen: set[str] = set()

        for hop in range(self.limits.max_redirects + 1):
            if current in seen:
                return _failure_page(url, None, started), None
            seen.add(current)
            try:
                self._throttle()
                with self._client.stream("GET", current) as response:
                    status_code = response.status_code
                    if status_code in _REDIRECT_STATUSES:
                        location = response.headers.get("location")
                        if not location or hop >= self.limits.max_redirects:
                            return _status_page(url, status_code, started), None
                        target = normalize_url(location, base=current)
                        if target is None or not same_crawl_origin(target, url):
                            return _status_page(url, status_code, started), None
                        if not endpoint_is_allowed(target, self.resolver):
                            return _status_page(url, status_code, started), None
                        current = _request_target(location, current, target)
                        continue

                    content_type = response.headers.get("content-type")
                    body = _read_limited(response, self.limits.max_response_bytes)
            except httpx.TimeoutException:
                logger.warning("page_failed audit_id=%s url=%s reason=timeout", audit_id, url)
                return _failure_page(url, None, started), None
            except httpx.HTTPError:
                logger.warning("page_failed audit_id=%s url=%s reason=connection", audit_id, url)
                return _failure_page(url, None, started), None

            if body is None:
                logger.warning("page_failed audit_id=%s url=%s reason=oversized", audit_id, url)
                return _status_page(url, status_code, started), None

            if not is_html_content_type(content_type):
                if status_code >= 400:
                    return _status_page(url, status_code, started), None
                return None, None

            html = _decode_body(body, content_type or "")
            try:
                extracted = parse_html(html, current)
            except Exception:
                logger.warning("page_failed audit_id=%s url=%s reason=parse", audit_id, url)
                return _status_page(current, status_code, started), None

            stored_url = normalize_url(current) or url
            return _parsed_page(stored_url, status_code, started, extracted), html

        logger.warning("page_failed audit_id=%s url=%s reason=redirect_loop", audit_id, url)
        return _failure_page(url, None, started), None

    def _throttle(self) -> None:
        if self._request_count > 0 and self.limits.delay_seconds > 0:
            time.sleep(self.limits.delay_seconds)
        self._request_count += 1


def build_client(limits: CrawlLimits, transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        transport=transport,
        timeout=httpx.Timeout(limits.timeout_seconds),
        follow_redirects=False,
        headers={"User-Agent": limits.user_agent},
    )


def _request_target(location: str, current: str, normalized_target: str) -> str:
    """Follow a same-origin redirect.

    When normalization collapses the target onto ``current`` (root slash or
    default port), request the redirect target once so the hop still moves.
    """
    if normalized_target != current:
        return normalized_target
    exact = urljoin(current, location.strip())
    return exact or normalized_target


def _has_skipped_extension(url: str) -> bool:
    path = urlsplit(url).path.lower()
    return any(path.endswith(extension) for extension in _SKIPPED_EXTENSIONS)


def _read_limited(response: httpx.Response, limit: int) -> bytes | None:
    declared = response.headers.get("content-length")
    if declared is not None:
        try:
            if int(declared) > limit:
                return None
        except ValueError:
            pass
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > limit:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def _decode_body(body: bytes, content_type: str) -> str:
    charset = "utf-8"
    lowered = content_type.lower()
    if "charset=" in lowered:
        charset = lowered.split("charset=", 1)[1].split(";", 1)[0].strip().strip('"')
    try:
        return body.decode(charset, errors="replace")
    except LookupError:
        return body.decode("utf-8", errors="replace")


def _elapsed_ms(started: float) -> int:
    return max(0, int((time.perf_counter() - started) * 1000))


def _failure_page(url: str, status_code: int | None, started: float) -> CrawledPage:
    return CrawledPage(url=url, status_code=status_code, load_time_ms=_elapsed_ms(started))


def _status_page(url: str, status_code: int, started: float) -> CrawledPage:
    return CrawledPage(url=url, status_code=status_code, load_time_ms=_elapsed_ms(started))


def _parsed_page(url: str, status_code: int, started: float, extracted: ExtractedPage) -> CrawledPage:
    return CrawledPage(
        url=url,
        status_code=status_code,
        title=extracted.title,
        meta_description=extracted.meta_description,
        canonical_url=extracted.canonical_url,
        word_count=extracted.word_count,
        h1_count=extracted.h1_count,
        h2_count=extracted.h2_count,
        has_schema=extracted.has_schema,
        schema_types=extracted.schema_types if extracted.has_schema else None,
        load_time_ms=_elapsed_ms(started),
    )
