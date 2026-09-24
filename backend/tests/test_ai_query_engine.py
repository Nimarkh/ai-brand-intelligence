"""Unit tests for deterministic AI query generation and response extraction."""

from __future__ import annotations

from app.models.enums import AiQueryCategory
from app.services.ai.query_engine.extraction import extract_response_signals
from app.services.ai.query_engine.generator import QueryGenerator, normalize_query_text
from app.services.ai.query_engine.models import BrandContext


def _brand(**overrides) -> BrandContext:
    data = {
        "name": "Acme Analytics",
        "industry": "marketing analytics",
        "country": "Sweden",
        "target_market": "Nordics",
        "description": "B2B analytics platform",
        "website_url": "https://acme.example",
    }
    data.update(overrides)
    return BrandContext(**data)


def test_normalize_query_text_trims_and_collapses_whitespace() -> None:
    assert normalize_query_text("  What   is   Acme?  ") == "What is Acme?"


def test_generation_is_deterministic_and_stable() -> None:
    generator = QueryGenerator()
    brand = _brand()
    first = generator.generate(brand, max_queries=18)
    second = generator.generate(brand, max_queries=18)
    assert [(q.query_text, q.category) for q in first] == [
        (q.query_text, q.category) for q in second
    ]
    assert 12 <= len(first) <= 18


def test_generation_covers_all_six_categories() -> None:
    queries = QueryGenerator().generate(_brand(), max_queries=18)
    categories = {q.category for q in queries}
    assert categories == set(AiQueryCategory)


def test_generation_substitutes_brand_and_market() -> None:
    queries = QueryGenerator().generate(_brand(), max_queries=18)
    texts = [q.query_text for q in queries]
    assert any("Acme Analytics" in text for text in texts)
    assert any("marketing analytics" in text for text in texts)
    assert any("Nordics" in text for text in texts)
    joined = "\n".join(texts).casefold()
    assert "bliss" not in joined
    assert "bliss agency" not in joined


def test_generation_falls_back_to_country_for_market() -> None:
    queries = QueryGenerator().generate(
        _brand(target_market=None, country="Germany"),
        max_queries=18,
    )
    assert any("Germany" in q.query_text for q in queries)


def test_deduplication_case_insensitive() -> None:
    # Max large enough that only templates matter; duplicates would inflate count.
    queries = QueryGenerator().generate(_brand(), max_queries=50)
    keys = [q.query_text.casefold() for q in queries]
    assert len(keys) == len(set(keys))


def test_max_query_limit_truncates_with_diversity() -> None:
    queries = QueryGenerator().generate(_brand(), max_queries=6)
    assert len(queries) == 6
    assert {q.category for q in queries} == set(AiQueryCategory)


def test_max_queries_zero_returns_empty() -> None:
    assert QueryGenerator().generate(_brand(), max_queries=0) == []


def test_brand_mentioned_case_insensitive() -> None:
    result = extract_response_signals(
        "Many firms exist. acme analytics is one option.",
        "Acme Analytics",
    )
    assert result.brand_mentioned is True
    assert result.brand_position is not None
    assert result.brand_position >= 1


def test_brand_not_mentioned() -> None:
    result = extract_response_signals("No relevant company is listed.", "Acme Analytics")
    assert result.brand_mentioned is False
    assert result.brand_position is None


def test_brand_position_orders_candidates() -> None:
    text = "Rival Labs and Other Co are options. Acme Analytics is also strong."
    result = extract_response_signals(text, "Acme Analytics")
    assert result.brand_mentioned is True
    assert result.brand_position == 3


def test_citation_heuristic_url_and_markers() -> None:
    with_url = extract_response_signals(
        "See https://example.com/report for details.",
        "Acme",
    )
    assert with_url.citation_found is True
    with_marker = extract_response_signals("According to sources [1] this is true.", "Acme")
    assert with_marker.citation_found is True
    plain = extract_response_signals("No references here.", "Acme")
    assert plain.citation_found is False
