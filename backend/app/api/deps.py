from uuid import UUID

import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.security import decode_access_token
from app.models.user import User
from app.services.ai import AIProvider, get_ai_provider

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token = request.cookies.get(settings.COOKIE_NAME)
    if not token:
        raise UNAUTHORIZED

    try:
        user_id: UUID = decode_access_token(token)
    except (jwt.InvalidTokenError, ValueError):
        raise UNAUTHORIZED from None

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise UNAUTHORIZED

    return user


def get_configured_ai_provider() -> AIProvider:
    """Resolve the configured AI provider for future FastAPI dependencies.

    Phase 10 does not expose a public generate endpoint. Tests may override
    this dependency without touching production provider construction.
    """
    return get_ai_provider()
