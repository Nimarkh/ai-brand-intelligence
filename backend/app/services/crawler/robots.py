from __future__ import annotations

import logging
from urllib.robotparser import RobotFileParser

import httpx

logger = logging.getLogger("app.crawler")

# robots.txt is not a crawled page. Cap it separately so a huge file cannot
# consume the page body budget. A failed or oversized robots.txt allows the
# crawl to continue; it is not treated as a disallow-all.
ROBOTS_MAX_BYTES = 512_000


class RobotsPolicy:
    """Allow/disallow decisions for one origin. Missing or unreadable files allow URLs."""

    def __init__(self, parser: RobotFileParser, user_agent: str) -> None:
        self._parser = parser
        self._user_agent = user_agent

    def allows(self, url: str) -> bool:
        try:
            return bool(self._parser.can_fetch(self._user_agent, url))
        except Exception:
            logger.warning("robots_check_failed")
            return True


def empty_policy(user_agent: str) -> RobotsPolicy:
    parser = RobotFileParser()
    parser.parse([])
    return RobotsPolicy(parser, user_agent)


def fetch_robots(
    client: httpx.Client,
    origin: str,
    user_agent: str,
    *,
    throttle,
) -> RobotsPolicy:
    """Fetch ``/robots.txt``. 404, network errors, and unreadable bodies allow crawling.

    Disallow rules for this crawler's user-agent are honored. Sitemap directives
    and Crawl-delay are not applied.
    """
    robots_url = f"{origin}/robots.txt"
    try:
        throttle()
        with client.stream("GET", robots_url) as response:
            # Do not follow redirects. A redirect could escape the crawl origin
            # or SSRF boundary; treat redirects as unreadable robots.txt.
            if response.status_code in {301, 302, 303, 307, 308}:
                logger.warning("robots_redirect_ignored status_code=%s", response.status_code)
                return empty_policy(user_agent)
            if response.status_code == 404:
                logger.info("robots_missing")
                return empty_policy(user_agent)
            if response.status_code >= 400:
                logger.warning("robots_unreadable status_code=%s", response.status_code)
                return empty_policy(user_agent)
            body = _read_limited(response, ROBOTS_MAX_BYTES)
    except httpx.HTTPError:
        logger.warning("robots_fetch_failed")
        return empty_policy(user_agent)

    if body is None:
        logger.warning("robots_too_large")
        return empty_policy(user_agent)

    parser = RobotFileParser()
    parser.set_url(robots_url)
    parser.parse(body.decode("utf-8", errors="replace").splitlines())
    return RobotsPolicy(parser, user_agent)


def _read_limited(response: httpx.Response, limit: int) -> bytes | None:
    chunks: list[bytes] = []
    total = 0
    for chunk in response.iter_bytes():
        total += len(chunk)
        if total > limit:
            return None
        chunks.append(chunk)
    return b"".join(chunks)
