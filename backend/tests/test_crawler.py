import httpx
import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.audit import Audit
from app.models.brand import Brand
from app.models.enums import AuditStatus
from app.models.user import User
from app.models.website import WebsitePage
from app.services.crawl_service import CrawlFailedError, run_crawl
from app.services.crawler import CrawlLimits, WebsiteCrawler
from app.services.crawler.models import CrawlStartError

PUBLIC_IP = ["93.184.216.34"]
HOME = "<html><head><title>Home</title></head><body><h1>Welcome</h1><p>Hello world</p>{links}</body></html>"


def _limits(**overrides: object) -> CrawlLimits:
    values: dict[str, object] = {
        "max_pages": 20,
        "max_depth": 3,
        "timeout_seconds": 5,
        "delay_seconds": 0,
        "max_response_bytes": 5_000_000,
        "user_agent": "AI-Brand-Intelligence-Crawler/1.0",
        "max_redirects": 5,
    }
    values.update(overrides)
    return CrawlLimits(**values)  # type: ignore[arg-type]


def _crawler(handler, **overrides: object) -> WebsiteCrawler:
    transport = httpx.MockTransport(handler)
    client = httpx.Client(transport=transport, follow_redirects=False)
    return WebsiteCrawler(_limits(**overrides), client, resolver=lambda _host: list(PUBLIC_IP))


def _path(url: httpx.URL) -> str:
    path = url.path or "/"
    return path


def _html(body: str, status: int = 200, content_type: str = "text/html; charset=utf-8") -> httpx.Response:
    return httpx.Response(status, text=body, headers={"content-type": content_type})


def _site(pages: dict[str, httpx.Response], robots: httpx.Response | None = None, hosts: set[str] | None = None):
    seen: list[tuple[str, str]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append((request.url.host, _path(request.url)))
        if hosts is not None and request.url.host not in hosts:
            raise AssertionError(f"unexpected host {request.url.host}")
        if _path(request.url) == "/robots.txt":
            return robots or httpx.Response(404, text="missing")
        page = pages.get(_path(request.url))
        if page is None:
            return _html("<html><title>Missing</title></html>", status=404)
        return page

    return handler, seen


def _page(title: str, links: str = "") -> str:
    return HOME.format(links=links)


def test_one_page_site() -> None:
    handler, seen = _site({"/": _html(_page("Home"))})
    crawler = _crawler(handler)
    try:
        result = crawler.crawl("https://example.com")
    finally:
        crawler.close()

    assert len(result.pages) == 1
    page = result.pages[0]
    assert page.url == "https://example.com"
    assert page.status_code == 200
    assert page.title == "Home"
    assert page.h1_count == 1
    assert page.word_count == 3
    assert page.load_time_ms is not None and page.load_time_ms >= 0
    assert ("example.com", "/robots.txt") in seen


def test_multi_page_relative_and_duplicate_links() -> None:
    html = _page("Home", '<a href="../about">About</a><a href="/about">Again</a><a href="/about#team">Frag</a>')
    about = "<html><head><title>About</title></head><body><p>About page</p></body></html>"
    handler, _seen = _site({"/docs/guide": _html(html), "/about": _html(about)})
    crawler = _crawler(handler)
    try:
        result = crawler.crawl("https://example.com/docs/guide")
    finally:
        crawler.close()

    urls = [page.url for page in result.pages]
    assert urls == ["https://example.com/docs/guide", "https://example.com/about"]
    assert result.pages[1].title == "About"


def test_depth_and_page_limits() -> None:
    home = _page("Home", '<a href="/a">A</a>')
    page_a = "<html><title>A</title><body><a href=\"/b\">B</a></body></html>"
    page_b = "<html><title>B</title></html>"
    handler, seen = _site({"/": _html(home), "/a": _html(page_a), "/b": _html(page_b)})
    crawler = _crawler(handler, max_depth=1)
    try:
        result = crawler.crawl("https://example.com")
    finally:
        crawler.close()

    assert [page.url for page in result.pages] == ["https://example.com", "https://example.com/a"]
    assert ("example.com", "/b") not in seen

    wide = _page("Home", '<a href="/a">A</a><a href="/b">B</a><a href="/c">C</a>')
    handler, seen = _site(
        {
            "/": _html(wide),
            "/a": _html("<html><title>A</title></html>"),
            "/b": _html("<html><title>B</title></html>"),
            "/c": _html("<html><title>C</title></html>"),
        }
    )
    crawler = _crawler(handler, max_pages=2, max_depth=2)
    try:
        result = crawler.crawl("https://example.com")
    finally:
        crawler.close()
    assert len(result.pages) == 2
    assert ("example.com", "/c") not in seen


def test_external_subdomain_and_static_links_are_ignored() -> None:
    html = _page(
        "Home",
        """
        <a href="https://other-site.com/">Out</a>
        <a href="https://blog.example.com/post">Blog</a>
        <a href="/logo.png">Logo</a>
        <a href="/about">About</a>
        """,
    )
    handler, seen = _site(
        {
            "/": _html(html),
            "/about": _html("<html><title>About</title></html>"),
        }
    )
    crawler = _crawler(handler)
    try:
        result = crawler.crawl("https://example.com")
    finally:
        crawler.close()

    hosts = {host for host, _path in seen}
    assert hosts == {"example.com"}
    assert ("example.com", "/logo.png") not in seen
    assert [page.url for page in result.pages] == ["https://example.com", "https://example.com/about"]


def test_robots_disallow_is_respected() -> None:
    robots = httpx.Response(
        200,
        text="User-agent: *\nDisallow: /secret\n",
        headers={"content-type": "text/plain"},
    )
    html = _page("Home", '<a href="/secret">Secret</a><a href="/public">Public</a>')
    handler, seen = _site(
        {
            "/": _html(html),
            "/public": _html("<html><title>Public</title></html>"),
            "/secret": _html("<html><title>Secret</title></html>"),
        },
        robots=robots,
    )
    crawler = _crawler(handler)
    try:
        result = crawler.crawl("https://example.com")
    finally:
        crawler.close()

    assert ("example.com", "/secret") not in seen
    assert [page.url for page in result.pages] == ["https://example.com", "https://example.com/public"]


def test_robots_redirect_is_ignored_and_does_not_escape_origin() -> None:
    """robots.txt redirects must not be followed (SSRF / origin escape)."""
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(f"{request.url.host}{_path(request.url)}")
        path = _path(request.url)
        if path == "/robots.txt":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/robots.txt"})
        if path == "/":
            return _html("<html><title>Home</title><p>ok</p></html>")
        raise AssertionError(path)

    crawler = _crawler(handler)
    try:
        result = crawler.crawl("https://example.com")
    finally:
        crawler.close()

    assert result.pages[0].title == "Home"
    assert not any("127.0.0.1" in entry for entry in seen)
    assert any(entry.endswith("/") or entry.endswith("example.com/") for entry in seen)


def test_redirect_to_private_address_is_rejected() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = _path(request.url)
        if path == "/robots.txt":
            return httpx.Response(404, text="missing")
        if path == "/":
            return httpx.Response(302, headers={"location": "http://127.0.0.1/admin"})
        raise AssertionError(path)

    crawler = _crawler(handler)
    try:
        result = crawler.crawl("https://example.com")
    finally:
        crawler.close()

    assert result.pages[0].status_code == 302
    assert result.pages[0].title is None


def test_http_errors_timeout_and_malformed_content_do_not_stop_the_crawl() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        path = _path(request.url)
        if path == "/robots.txt":
            return httpx.Response(404, text="missing")
        if path == "/missing":
            return _html("<html><title>Missing</title><a href=\"/ok\">Ok</a></html>", status=404)
        if path == "/boom":
            return _html("<html><title>Boom</title></html>", status=500)
        if path == "/slow":
            raise httpx.ReadTimeout("timed out")
        if path == "/odd":
            return _html("<html><head><title>Odd</title><script type=\"application/ld+json\">{nope</script></head></html>")
        if path == "/ok":
            return _html("<html><title>Ok</title></html>")
        return _html(
            _page(
                "Home",
                '<a href="/missing">M</a><a href="/boom">B</a><a href="/slow">S</a><a href="/odd">O</a><a href="/ok">K</a>',
            )
        )

    crawler = _crawler(handler)
    try:
        result = crawler.crawl("https://example.com")
    finally:
        crawler.close()

    by_url = {page.url: page for page in result.pages}
    assert by_url["https://example.com/missing"].status_code == 404
    assert by_url["https://example.com/boom"].status_code == 500
    assert by_url["https://example.com/slow"].status_code is None
    assert by_url["https://example.com/odd"].title == "Odd"
    assert by_url["https://example.com/odd"].has_schema is False
    assert by_url["https://example.com/ok"].title == "Ok"
    assert all(page.load_time_ms is not None for page in result.pages)


def test_oversized_response_is_not_parsed() -> None:
    handler, _seen = _site({"/": httpx.Response(200, content=b"x" * 300, headers={"content-type": "text/html"})})
    crawler = _crawler(handler, max_response_bytes=100)
    try:
        result = crawler.crawl("https://example.com")
    finally:
        crawler.close()

    assert len(result.pages) == 1
    assert result.pages[0].status_code == 200
    assert result.pages[0].title is None
    assert result.pages[0].word_count is None


def test_redirect_within_and_outside_domain_and_loop() -> None:
    def inside(request: httpx.Request) -> httpx.Response:
        path = _path(request.url)
        if path == "/robots.txt":
            return httpx.Response(404, text="missing")
        if path == "/":
            return httpx.Response(302, headers={"location": "/about"})
        if path == "/about":
            return _html("<html><title>About</title><p>Inside</p></html>")
        raise AssertionError(path)

    crawler = _crawler(inside)
    try:
        result = crawler.crawl("https://example.com")
    finally:
        crawler.close()
    assert result.pages[0].url == "https://example.com/about"
    assert result.pages[0].status_code == 200
    assert result.pages[0].title == "About"

    def outside(request: httpx.Request) -> httpx.Response:
        if request.url.host != "example.com":
            raise AssertionError(request.url.host)
        if _path(request.url) == "/robots.txt":
            return httpx.Response(404, text="missing")
        return httpx.Response(302, headers={"location": "https://evil.test/phish"})

    crawler = _crawler(outside)
    try:
        result = crawler.crawl("https://example.com")
    finally:
        crawler.close()
    assert result.pages[0].url == "https://example.com"
    assert result.pages[0].status_code == 302
    assert result.pages[0].title is None

    def loop(request: httpx.Request) -> httpx.Response:
        path = _path(request.url)
        if path == "/robots.txt":
            return httpx.Response(404, text="missing")
        if path == "/":
            return httpx.Response(301, headers={"location": "/loop"})
        return httpx.Response(301, headers={"location": "/"})

    crawler = _crawler(loop, max_redirects=5)
    try:
        result = crawler.crawl("https://example.com")
    finally:
        crawler.close()
    assert len(result.pages) == 1
    assert result.pages[0].title is None


def test_blocked_start_url_raises() -> None:
    crawler = _crawler(lambda _request: httpx.Response(200, text="no"))
    try:
        with pytest.raises(CrawlStartError):
            crawler.crawl("http://127.0.0.1/")
    finally:
        crawler.close()


def _user_and_brand(db: Session, email: str, website: str) -> Brand:
    user = User(email=email, password_hash="hash", full_name="Owner", is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    brand = Brand(
        owner_id=user.id,
        name="Example",
        website_url=website,
        industry="Software",
        country="United States",
        target_market="North America",
    )
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return brand


def _scores_are_null(audit: Audit) -> None:
    assert audit.overall_score is None
    assert audit.website_score is None
    assert audit.seo_score is None
    assert audit.ai_visibility_score is None
    assert audit.entity_score is None
    assert audit.semantic_score is None


def test_successful_crawl_stores_one_snapshot_and_leaves_scores_null(db: Session) -> None:
    brand = _user_and_brand(db, "owner@example.com", "https://example.com")
    other = _user_and_brand(db, "other@example.com", "https://contoso.example")
    audit = Audit(brand_id=brand.id, status=AuditStatus.PENDING)
    other_audit = Audit(brand_id=other.id, status=AuditStatus.COMPLETED)
    db.add_all([audit, other_audit])
    db.commit()
    db.add(WebsitePage(audit_id=audit.id, url="https://example.com/old", title="Old"))
    db.add(WebsitePage(audit_id=other_audit.id, url="https://contoso.example/", title="Keep"))
    db.commit()

    about = "<html><title>About</title><body><p>Team page</p></body></html>"
    handler, _seen = _site(
        {
            "/": _html(_page("Home", '<a href="/about">About</a><a href="/about#x">Dup</a>')),
            "/about": _html(about),
        }
    )
    crawler = _crawler(handler)
    try:
        result = run_crawl(db, audit, brand, crawler)
    finally:
        crawler.close()

    assert result.status == AuditStatus.COMPLETED
    db.refresh(audit)
    assert audit.status == AuditStatus.COMPLETED
    _scores_are_null(audit)
    rows = list(db.scalars(select(WebsitePage).where(WebsitePage.audit_id == audit.id)))
    assert sorted(row.url for row in rows) == ["https://example.com", "https://example.com/about"]
    assert len(rows) == 2
    kept = db.scalar(select(WebsitePage).where(WebsitePage.audit_id == other_audit.id))
    assert kept is not None and kept.url == "https://contoso.example/"

    crawler = _crawler(handler)
    try:
        again = run_crawl(db, audit, brand, crawler)
    finally:
        crawler.close()
    assert again.pages_crawled == 2
    count = db.scalar(select(func.count()).select_from(WebsitePage).where(WebsitePage.audit_id == audit.id))
    assert count == 2
    assert db.scalar(select(func.count()).select_from(WebsitePage).where(WebsitePage.audit_id == other_audit.id)) == 1
    db.refresh(audit)
    _scores_are_null(audit)


def test_failed_crawl_marks_audit_failed_without_touching_other_audits(db: Session) -> None:
    brand = _user_and_brand(db, "fail@example.com", "https://example.com")
    other = _user_and_brand(db, "keep@example.com", "https://contoso.example")
    audit = Audit(brand_id=brand.id, status=AuditStatus.PENDING)
    other_audit = Audit(brand_id=other.id, status=AuditStatus.COMPLETED)
    db.add_all([audit, other_audit])
    db.commit()
    db.add(WebsitePage(audit_id=audit.id, url="https://example.com/old"))
    db.add(WebsitePage(audit_id=other_audit.id, url="https://contoso.example/keep"))
    db.commit()
    audit_id = audit.id
    other_id = other_audit.id

    handler, _seen = _site({"/": _html(_page("Home"))})
    crawler = _crawler(handler)

    def explode(_start_url: str, _context=None) -> None:  # noqa: ANN001
        raise RuntimeError("boom")

    crawler.crawl = explode  # type: ignore[method-assign]
    with pytest.raises(CrawlFailedError) as caught:
        try:
            run_crawl(db, audit, brand, crawler)
        finally:
            crawler.close()
    assert "boom" not in str(caught.value)
    assert "Traceback" not in str(caught.value)
    db.refresh(audit)
    assert audit.status == AuditStatus.FAILED
    _scores_are_null(audit)
    assert db.scalar(select(func.count()).select_from(WebsitePage).where(WebsitePage.audit_id == audit_id)) == 0
    assert db.scalar(select(func.count()).select_from(WebsitePage).where(WebsitePage.audit_id == other_id)) == 1


def test_blocked_destination_marks_audit_failed_and_keeps_previous_pages(db: Session) -> None:
    brand = _user_and_brand(db, "local@example.com", "http://127.0.0.1")
    audit = Audit(brand_id=brand.id, status=AuditStatus.COMPLETED)
    db.add(audit)
    db.commit()
    db.add(WebsitePage(audit_id=audit.id, url="http://127.0.0.1/old"))
    db.commit()
    handler, seen = _site({"/": _html("no")})
    crawler = _crawler(handler)
    try:
        with pytest.raises(Exception) as caught:
            run_crawl(db, audit, brand, crawler)
    finally:
        crawler.close()
    assert type(caught.value).__name__ == "CrawlFailedError"
    db.refresh(audit)
    assert audit.status == AuditStatus.FAILED
    _scores_are_null(audit)
    assert db.scalar(select(func.count()).select_from(WebsitePage).where(WebsitePage.audit_id == audit.id)) == 1
    assert seen == []
