from __future__ import annotations

import json
import logging
from typing import Any

from bs4 import BeautifulSoup

from app.services.crawler.models import ExtractedPage
from app.services.crawler.url_utils import normalize_url

logger = logging.getLogger("app.crawler")

TITLE_MAX_LENGTH = 512
META_DESCRIPTION_MAX_LENGTH = 2000
SCHEMA_TYPE_MAX_LENGTH = 200
SCHEMA_NODE_LIMIT = 500
_SKIPPED_TEXT_TAGS = ("script", "style", "noscript")


def parse_html(html: str, page_url: str) -> ExtractedPage:
    """Extract factual page fields. Malformed markup or JSON-LD does not raise."""
    soup = BeautifulSoup(html or "", "html.parser")
    schema_types, has_schema = _schema_types(soup)
    title = _title(soup)
    description = _meta_description(soup)
    canonical = _canonical(soup, page_url)
    h1_count = len(soup.find_all("h1"))
    h2_count = len(soup.find_all("h2"))
    word_count = _word_count(soup)
    return ExtractedPage(
        title=title,
        meta_description=description,
        canonical_url=canonical,
        word_count=word_count,
        h1_count=h1_count,
        h2_count=h2_count,
        has_schema=has_schema,
        schema_types=sorted(schema_types),
    )


def extract_links(html: str) -> list[str]:
    soup = BeautifulSoup(html or "", "html.parser")
    links: list[str] = []
    for tag in soup.find_all("a"):
        href = tag.get("href")
        if isinstance(href, str):
            links.append(href)
    return links


def is_html_content_type(content_type: str | None) -> bool:
    if not content_type:
        return False
    media = content_type.split(";", 1)[0].strip().lower()
    return media in {"text/html", "application/xhtml+xml"}


def _title(soup: BeautifulSoup) -> str | None:
    tag = soup.find("title")
    if tag is None:
        return None
    return _clean_text(tag.get_text(" ", strip=True), TITLE_MAX_LENGTH)


def _meta_description(soup: BeautifulSoup) -> str | None:
    for tag in soup.find_all("meta"):
        name = tag.get("name")
        if not isinstance(name, str) or name.strip().lower() != "description":
            continue
        content = tag.get("content")
        if isinstance(content, str):
            return _clean_text(content, META_DESCRIPTION_MAX_LENGTH)
    return None


def _canonical(soup: BeautifulSoup, page_url: str) -> str | None:
    for tag in soup.find_all("link"):
        if not _rel_contains(tag.get("rel"), "canonical"):
            continue
        href = tag.get("href")
        if not isinstance(href, str) or not href.strip():
            return None
        return normalize_url(href.strip(), base=page_url)
    return None


def _word_count(soup: BeautifulSoup) -> int:
    root = soup.body if soup.body is not None else soup
    for tag in root.find_all(_SKIPPED_TEXT_TAGS):
        tag.decompose()
    text = root.get_text(" ", strip=True)
    if not text:
        return 0
    return len(text.split())


def _schema_types(soup: BeautifulSoup) -> tuple[set[str], bool]:
    found: set[str] = set()
    parsed_any = False
    for tag in soup.find_all("script"):
        script_type = tag.get("type")
        if not isinstance(script_type, str):
            continue
        if script_type.split(";", 1)[0].strip().lower() != "application/ld+json":
            continue
        raw = tag.string if tag.string is not None else tag.get_text()
        if not isinstance(raw, str) or not raw.strip():
            continue
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            logger.info("json_ld_malformed")
            continue
        if not isinstance(payload, (dict, list)):
            continue
        parsed_any = True
        found.update(_collect_types(payload))
    return found, parsed_any


def _collect_types(payload: Any) -> set[str]:
    types: set[str] = set()
    stack: list[Any] = [payload]
    seen = 0
    while stack and seen < SCHEMA_NODE_LIMIT:
        node = stack.pop()
        seen += 1
        if isinstance(node, dict):
            raw_type = node.get("@type")
            values = raw_type if isinstance(raw_type, list) else [raw_type]
            for item in values:
                if isinstance(item, str):
                    cleaned = item.strip()
                    if cleaned and len(cleaned) <= SCHEMA_TYPE_MAX_LENGTH:
                        types.add(cleaned)
            for value in node.values():
                if isinstance(value, (dict, list)):
                    stack.append(value)
        elif isinstance(node, list):
            for item in node:
                if isinstance(item, (dict, list)):
                    stack.append(item)
    return types


def _rel_contains(rel: Any, expected: str) -> bool:
    if isinstance(rel, str):
        return expected in rel.lower().split()
    if isinstance(rel, list):
        return any(isinstance(item, str) and item.lower() == expected for item in rel)
    return False


def _clean_text(value: str, limit: int) -> str | None:
    cleaned = " ".join(value.split())
    if not cleaned:
        return None
    return cleaned[:limit]
