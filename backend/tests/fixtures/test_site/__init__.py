"""Deterministic local website fixture for crawler and workflow tests."""

from __future__ import annotations

import time
from pathlib import Path

import httpx

from app.services.crawler import CrawlLimits, WebsiteCrawler

FIXTURE_HOST = "fixture.test"
FIXTURE_ORIGIN = f"https://{FIXTURE_HOST}"
PUBLIC_IP = ["93.184.216.34"]

_SITE_DIR = Path(__file__).resolve().parent

# Path → (status, body bytes or None for generated, content-type, delay_seconds)
_PAGE_MAP: dict[str, tuple[int, str | None, str, float]] = {
    "/": (200, "index.html", "text/html; charset=utf-8", 0.0),
    "/about": (200, "about.html", "text/html; charset=utf-8", 0.0),
    "/product": (200, "product.html", "text/html; charset=utf-8", 0.0),
    "/contact": (200, "contact.html", "text/html; charset=utf-8", 0.0),
    "/broken": (404, None, "text/html; charset=utf-8", 0.0),
    "/slow": (200, "contact.html", "text/html; charset=utf-8", 0.05),
    "/robots.txt": (200, "robots.txt", "text/plain; charset=utf-8", 0.0),
}


def fixture_root() -> Path:
    return _SITE_DIR


def _read_file(name: str) -> bytes:
    return (_SITE_DIR / name).read_bytes()


def fixture_handler(request: httpx.Request) -> httpx.Response:
    """Serve the deterministic fixture site over httpx MockTransport."""
    if request.url.host != FIXTURE_HOST:
        raise AssertionError(f"unexpected host {request.url.host}")

    path = request.url.path or "/"
    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    entry = _PAGE_MAP.get(path)
    if entry is None:
        return httpx.Response(404, text="<html><title>Missing</title></html>", headers={"content-type": "text/html"})

    status, filename, content_type, delay = entry
    if delay > 0:
        time.sleep(delay)

    if status == 404:
        return httpx.Response(
            404,
            text="<html><head><title>Not Found</title></head><body><h1>Not Found</h1></body></html>",
            headers={"content-type": content_type},
        )

    assert filename is not None
    return httpx.Response(status, content=_read_file(filename), headers={"content-type": content_type})


def build_fixture_crawler(**limit_overrides: object) -> WebsiteCrawler:
    """Build a WebsiteCrawler that only talks to the fixture site."""
    values: dict[str, object] = {
        "max_pages": 20,
        "max_depth": 3,
        "timeout_seconds": 5,
        "delay_seconds": 0,
        "max_response_bytes": 5_000_000,
        "user_agent": "AI-Brand-Intelligence-Crawler/1.0",
        "max_redirects": 5,
    }
    values.update(limit_overrides)
    limits = CrawlLimits(**values)  # type: ignore[arg-type]
    transport = httpx.MockTransport(fixture_handler)
    client = httpx.Client(transport=transport, follow_redirects=False)
    return WebsiteCrawler(limits, client, resolver=lambda _host: list(PUBLIC_IP))
