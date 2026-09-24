"""Pure unit tests for the AI Visibility Engine."""

from __future__ import annotations

from decimal import Decimal
from uuid import uuid4

import pytest

from app.services.ai.visibility import (
    AIVisibilityEngine,
    CITATION_WEIGHT,
    MENTION_WEIGHT,
    POSITION_WEIGHT,
    ResponseInput,
    SEMANTIC_WEIGHT,
    VISIBILITY_WEIGHTS,
    VisibilityStatus,
    position_to_score,
    semantic_alignment,
    tokenize_content,
)
from app.services.ai.visibility.scoring import score_overall
from app.services.ai.visibility.models import ComponentScore, VisibilityMetrics
from app.services.ai.visibility.metrics import compute_metrics
from app.services.ai.visibility.scoring import assemble_result, build_components


def _resp(
    *,
    mentioned: bool = False,
    position: int | None = None,
    citation: bool = False,
    query: str = "What is Acme Analytics known for?",
    text: str = "Acme Analytics provides marketing analytics tools.",
) -> ResponseInput:
    return ResponseInput(
        query_id=uuid4(),
        response_id=uuid4(),
        query_text=query,
        response_text=text,
        brand_mentioned=mentioned,
        brand_position=position,
        citation_found=citation,
    )


def test_weights_sum_to_one() -> None:
    assert sum(VISIBILITY_WEIGHTS.values()) == Decimal("1.00")
    assert MENTION_WEIGHT == Decimal("0.30")
    assert CITATION_WEIGHT == Decimal("0.25")
    assert POSITION_WEIGHT == Decimal("0.25")
    assert SEMANTIC_WEIGHT == Decimal("0.20")


@pytest.mark.parametrize(
    ("mentioned_flags", "expected"),
    [
        ([False, False], Decimal("0")),
        ([True, False], Decimal("0.5")),
        ([True, True], Decimal("1")),
    ],
)
def test_mention_rate(mentioned_flags: list[bool], expected: Decimal) -> None:
    responses = [_resp(mentioned=flag, position=1 if flag else None) for flag in mentioned_flags]
    metrics, _ = compute_metrics(responses)
    assert metrics.mention_rate == expected


def test_mention_rate_no_responses() -> None:
    metrics, values = compute_metrics([])
    assert metrics.mention_rate is None
    assert values == []


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        ([False, False], Decimal("0")),
        ([True, False], Decimal("0.5")),
        ([True, True], Decimal("1")),
    ],
)
def test_citation_rate(flags: list[bool], expected: Decimal) -> None:
    responses = [_resp(citation=flag) for flag in flags]
    metrics, _ = compute_metrics(responses)
    assert metrics.citation_rate == expected


@pytest.mark.parametrize(
    ("position", "mentioned", "expected"),
    [
        (1, True, Decimal("100")),
        (2, True, Decimal("75")),
        (3, True, Decimal("50")),
        (4, True, Decimal("25")),
        (5, True, Decimal("0")),
        (9, True, Decimal("0")),
        (None, False, Decimal("0")),
        (1, False, Decimal("0")),
    ],
)
def test_position_to_score(position: int | None, mentioned: bool, expected: Decimal) -> None:
    assert position_to_score(position, brand_mentioned=mentioned) == expected


def test_position_average_example() -> None:
    # 1,1,2,3,null → 100,100,75,50,0 → avg 65
    responses = [
        _resp(mentioned=True, position=1),
        _resp(mentioned=True, position=1),
        _resp(mentioned=True, position=2),
        _resp(mentioned=True, position=3),
        _resp(mentioned=False, position=None, text="No brand here."),
    ]
    metrics, _ = compute_metrics(responses)
    assert metrics.position_score == Decimal("65.0")


def test_tokenize_content_drops_stop_words() -> None:
    tokens = tokenize_content("What is the best company for analytics?")
    assert "what" not in tokens
    assert "the" not in tokens
    assert "best" in tokens
    assert "company" in tokens
    assert "analytics" in tokens


def test_semantic_full_overlap() -> None:
    query = "Acme Analytics marketing tools"
    response = "Acme Analytics marketing tools are widely used."
    value = semantic_alignment(query, response, brand_mentioned=True)
    assert value == Decimal("1.0000")


def test_semantic_partial_overlap() -> None:
    value = semantic_alignment(
        "leading marketing analytics platforms",
        "marketing platforms exist worldwide",
        brand_mentioned=False,
    )
    assert value is not None
    assert Decimal("0") < value < Decimal("1")


def test_semantic_no_overlap() -> None:
    value = semantic_alignment(
        "quantum computing research",
        "gardening tips for spring",
        brand_mentioned=False,
    )
    assert value == Decimal("0.0000")


def test_semantic_stop_word_only_query() -> None:
    assert semantic_alignment("what is the", "anything", brand_mentioned=False) is None


def test_semantic_empty_response() -> None:
    assert semantic_alignment("marketing analytics", "", brand_mentioned=False) == Decimal("0")


def test_semantic_brand_bonus_and_cap() -> None:
    # High overlap without brand
    base = semantic_alignment(
        "marketing analytics platform",
        "marketing analytics platform overview",
        brand_mentioned=False,
    )
    boosted = semantic_alignment(
        "marketing analytics platform",
        "marketing analytics platform overview",
        brand_mentioned=True,
    )
    assert base is not None and boosted is not None
    assert boosted >= base
    assert boosted <= Decimal("1.0000")


def test_final_score_all_components() -> None:
    responses = [
        _resp(
            mentioned=True,
            position=1,
            citation=True,
            query="Acme Analytics marketing services",
            text="Acme Analytics marketing services https://example.com",
        )
    ]
    result = AIVisibilityEngine().score(total_queries=1, responses=responses)
    assert result.status == VisibilityStatus.AVAILABLE
    assert result.overall_score is not None
    assert Decimal("0") <= result.overall_score <= Decimal("100")
    assert result.metrics.semantic_alignment is not None


def test_semantic_unavailable_renormalizes_weights() -> None:
    # Force semantic unavailable via stop-word-only queries
    responses = [
        _resp(
            mentioned=True,
            position=1,
            citation=False,
            query="what is the",
            text="Acme Analytics is great.",
        )
    ]
    metrics, _ = compute_metrics(responses)
    assert metrics.semantic_score is None
    components = build_components(metrics)
    overall, updated = score_overall(components)
    semantic = next(item for item in updated if item.name == "semantic")
    assert semantic.status == VisibilityStatus.UNAVAILABLE
    assert semantic.effective_weight is None
    available = [item for item in updated if item.status == VisibilityStatus.AVAILABLE]
    assert available
    assert abs(sum((item.effective_weight or Decimal("0")) for item in available) - Decimal("1")) < Decimal(
        "0.001"
    )
    assert overall is not None


def test_score_bounded_and_rounded() -> None:
    responses = [_resp(mentioned=True, position=1, citation=True) for _ in range(3)]
    result = AIVisibilityEngine().score(total_queries=3, responses=responses)
    assert result.overall_score is not None
    assert result.overall_score == result.overall_score.quantize(Decimal("0.1"))


def test_availability_zero_responses() -> None:
    result = AIVisibilityEngine().score(total_queries=18, responses=[])
    assert result.status == VisibilityStatus.UNAVAILABLE
    assert result.overall_score is None
    assert result.successful_responses == 0
    assert result.failed_responses == 18


def test_availability_partial_provisional() -> None:
    responses = [_resp(mentioned=True, position=1) for _ in range(15)]
    result = AIVisibilityEngine().score(total_queries=18, responses=responses)
    assert result.status == VisibilityStatus.PROVISIONAL
    assert result.successful_responses == 15
    assert result.failed_responses == 3
    assert result.response_coverage == Decimal("0.8333")


def test_availability_complete() -> None:
    responses = [_resp(mentioned=True, position=1) for _ in range(5)]
    result = AIVisibilityEngine().score(total_queries=5, responses=responses)
    assert result.status == VisibilityStatus.AVAILABLE
    assert result.failed_responses == 0
    assert result.response_coverage == Decimal("1.0000")


def test_assemble_unavailable_excludes_zero_fabrication() -> None:
    result = assemble_result(
        metrics=VisibilityMetrics(
            mention_rate=None,
            citation_rate=None,
            average_position=None,
            position_score=None,
            semantic_alignment=None,
            semantic_score=None,
        ),
        total_queries=10,
        successful_responses=0,
        failed_responses=10,
    )
    assert result.overall_score is None
    assert all(c.score is None for c in result.components)
