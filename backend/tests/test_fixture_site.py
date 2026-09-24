"""Phase 20 — fixture website characteristics and crawler regression."""

from __future__ import annotations

from pathlib import Path

from tests.fixtures.test_site import FIXTURE_ORIGIN, build_fixture_crawler, fixture_root


def test_fixture_files_exist() -> None:
    root = fixture_root()
    for name in ("index.html", "about.html", "product.html", "contact.html", "robots.txt"):
        assert (root / name).is_file()


def test_fixture_site_crawl_persists_known_pages() -> None:
    crawler = build_fixture_crawler(max_pages=10, max_depth=2)
    try:
        result = crawler.crawl(FIXTURE_ORIGIN)
    finally:
        crawler.close()

    by_url = {page.url: page for page in result.pages}
    assert f"{FIXTURE_ORIGIN}" in by_url or f"{FIXTURE_ORIGIN}/" in by_url
    home = by_url.get(FIXTURE_ORIGIN) or by_url[f"{FIXTURE_ORIGIN}/"]
    assert home.status_code == 200
    assert home.title and "Fixture Brand" in home.title
    assert home.h1_count == 1
    assert home.has_schema is True
    assert home.word_count is not None and home.word_count >= 50

    about = by_url[f"{FIXTURE_ORIGIN}/about"]
    assert about.title == "About Fixture Brand"
    assert about.meta_description is None or about.meta_description == ""
    assert about.word_count is not None and about.word_count < 50

    product = by_url[f"{FIXTURE_ORIGIN}/product"]
    assert product.title is not None and len(product.title) > 60
    assert product.h1_count == 2
    assert product.has_schema is True

    contact = by_url[f"{FIXTURE_ORIGIN}/contact"]
    assert contact.status_code == 200
    assert contact.meta_description

    broken = by_url[f"{FIXTURE_ORIGIN}/broken"]
    assert broken.status_code == 404

    slow = by_url[f"{FIXTURE_ORIGIN}/slow"]
    assert slow.status_code == 200
    assert slow.load_time_ms is not None and slow.load_time_ms >= 0


def test_fixture_html_is_self_contained() -> None:
    """Fixture pages must not reference public internet hosts."""
    root = fixture_root()
    banned = ("example.com", "google.", "openai.", "cdn.", "http://127.", "localhost")
    for path in Path(root).glob("*.html"):
        text = path.read_text(encoding="utf-8").lower()
        for token in banned:
            assert token not in text, f"{path.name} contains {token}"
