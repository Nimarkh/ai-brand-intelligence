from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.intelligence import (
    AskRequest,
    AskResponse,
    IntelligenceAuditList,
    serialize_ask,
    serialize_catalog,
)
from app.services.ai.factory import get_ai_provider
from app.services.ai.models import AIConfigurationError
from app.services.ai.provider import AIProvider
from app.services.intelligence.models import HistoryTurn
from app.services.intelligence.retrieval import IntelligenceAuditNotFound
from app.services.intelligence.service import (
    TIMEOUT_MESSAGE,
    UNAVAILABLE_MESSAGE,
    IntelligenceProviderFailure,
    ask_intelligence,
    list_audit_catalog,
)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])

NOT_FOUND = HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found.")


def get_intelligence_provider(_user: User = Depends(get_current_user)) -> AIProvider:
    """Resolve the Phase 10 provider after authentication.

    Configuration failures stay generic and do not include secrets.
    """
    try:
        return get_ai_provider()
    except AIConfigurationError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=UNAVAILABLE_MESSAGE,
        ) from None


@router.get(
    "/audits",
    response_model=IntelligenceAuditList,
    summary="List audits available to Ask Intelligence",
    description=(
        "Return audits owned by the authenticated user, completed first, "
        "then newest completion, then newest creation. "
        "Optional audit_id selects that owned audit. A foreign audit returns 404. "
        "When audit_id is omitted, the latest completed owned audit is selected, "
        "otherwise the latest owned audit. This endpoint does not call an AI provider."
    ),
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Not found"},
    },
)
def list_audits_for_intelligence(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    audit_id: Annotated[UUID | None, Query()] = None,
) -> IntelligenceAuditList:
    try:
        catalog = list_audit_catalog(current_user, db, audit_id=audit_id)
    except IntelligenceAuditNotFound:
        raise NOT_FOUND from None
    return serialize_catalog(catalog)


@router.post(
    "/ask",
    response_model=AskResponse,
    summary="Ask a question about one owned audit",
    description=(
        "Answer a natural-language question using bounded persisted audit context. "
        "The model cannot query the database. "
        "Optional audit_id must be owned or the response is 404. "
        "When audit_id is omitted, the latest completed owned audit is used, "
        "otherwise the latest owned audit. "
        "If the user has no audits, the response is empty and no provider is called. "
        "Conversation history is not stored."
    ),
    responses={
        401: {"description": "Not authenticated"},
        404: {"description": "Not found"},
        422: {"description": "Invalid question or history"},
        503: {"description": "AI analysis is temporarily unavailable"},
    },
)
async def ask(
    body: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
    provider: AIProvider = Depends(get_intelligence_provider),
) -> AskResponse:
    try:
        result = await ask_intelligence(
            current_user,
            db,
            provider,
            audit_id=body.audit_id,
            question=body.question,
            history=[HistoryTurn(role=item.role, content=item.content) for item in body.history],
        )
    except IntelligenceAuditNotFound:
        raise NOT_FOUND from None
    except IntelligenceProviderFailure as exc:
        status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        detail = exc.message or UNAVAILABLE_MESSAGE
        if detail == TIMEOUT_MESSAGE:
            detail = TIMEOUT_MESSAGE
        raise HTTPException(status_code=status_code, detail=detail) from None
    return serialize_ask(result)
