"""Ask Intelligence orchestration. The provider sees only a prepared context object."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.user import User
from app.services.ai.models import AIConfigurationError, AIProviderError, AIRequestError
from app.services.ai.provider import AIProvider
from app.services.intelligence.context import (
    build_audit_context,
    context_for_prompt,
    detect_intent,
    select_evidence,
)
from app.services.intelligence.models import (
    AnswerContext,
    AskOutcome,
    AuditCatalog,
    HistoryTurn,
)
from app.services.intelligence.prompt import build_provider_request
from app.services.intelligence.retrieval import IntelligenceAuditNotFound, resolve_audit, to_audit_option
from app.services.intelligence.safety import bound_prompt_payload, redact_sensitive, trim_history

EMPTY_MESSAGE = (
    "Ask Intelligence needs an audit to work with. "
    "Create a brand and run an audit to start asking questions."
)
UNAVAILABLE_MESSAGE = "AI analysis is temporarily unavailable. Please try again."
TIMEOUT_MESSAGE = "The analysis timed out. Please try again."
INSUFFICIENT_MESSAGE = (
    "I'm focused on analyzing your brand intelligence data for this audit. "
    "I don't have enough audit context to answer that question."
)


class IntelligenceProviderFailure(Exception):
    """The configured provider could not answer. Safe messages only."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


def list_audit_catalog(
    current_user: User,
    db: Session,
    *,
    audit_id: UUID | None = None,
) -> AuditCatalog:
    """Owned audits for the selector. Does not call an AI provider."""
    audits, selected = resolve_audit(db, current_user.id, audit_id)
    return AuditCatalog(
        audits=tuple(to_audit_option(row) for row in audits),
        selected_audit_id=selected.id if selected is not None else None,
    )


async def ask_intelligence(
    current_user: User,
    db: Session,
    provider: AIProvider,
    *,
    audit_id: UUID | None,
    question: str,
    history: list[HistoryTurn],
) -> AskOutcome:
    """Answer one question from persisted audit context.

    Raises:
        IntelligenceAuditNotFound: audit id is missing or not owned.
        IntelligenceProviderFailure: configuration, timeout, or provider failure.
    """
    _audits, audit = resolve_audit(db, current_user.id, audit_id)
    if audit is None:
        return AskOutcome(
            audit_id=None,
            answer=None,
            context=None,
            sources=(),
            empty=True,
            message=EMPTY_MESSAGE,
        )

    context = build_audit_context(db, audit)
    intent = detect_intent(question)
    sources = select_evidence(intent, context, question.lower())
    payload = bound_prompt_payload(context_for_prompt(context, intent))
    request = build_provider_request(
        question=question,
        brand_name=context.brand.name,
        intent=intent,
        context_payload=payload,
        history=trim_history(history),
    )
    try:
        response = await provider.generate(request)
    except AIConfigurationError as exc:
        raise IntelligenceProviderFailure(UNAVAILABLE_MESSAGE) from exc
    except (AIProviderError, AIRequestError) as exc:
        if _is_timeout(exc):
            raise IntelligenceProviderFailure(TIMEOUT_MESSAGE) from exc
        raise IntelligenceProviderFailure(UNAVAILABLE_MESSAGE) from exc

    answer = redact_sensitive(response.text)
    if not answer:
        answer = INSUFFICIENT_MESSAGE

    overall = next((score for score in context.scores if score.name == "overall"), None)
    return AskOutcome(
        audit_id=audit.id,
        answer=answer,
        context=AnswerContext(
            brand_name=context.brand.name,
            audit_date=context.audit.audit_date,
            overall_score=overall.score if overall is not None else None,
            overall_status=overall.status if overall is not None else "UNAVAILABLE",
        ),
        sources=sources,
        empty=False,
        message=None,
    )


def _is_timeout(exc: Exception) -> bool:
    text = str(exc).lower()
    return "timed out" in text or "timeout" in text
