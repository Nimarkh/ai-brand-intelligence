"""Application security middleware: CSRF origin checks, headers, body limits, abuse controls.

These are intentionally small. They are not a full WAF or distributed rate limiter.
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict, deque
from urllib.parse import urlsplit

from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

from app.core.config import settings

logger = logging.getLogger("app.security")

_SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS", "TRACE"})
_DOCS_PREFIXES = ("/docs", "/redoc", "/openapi.json")

# In-process only. Not shared across workers or hosts. See docs/security.md.
_AUTH_RATE_LIMIT = 40
_AUTH_RATE_WINDOW_SECONDS = 60.0
_auth_hits: dict[str, deque[float]] = defaultdict(deque)

MAX_REQUEST_BODY_BYTES = 1_048_576  # 1 MiB


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Attach conservative security headers to every response."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "geolocation=(), microphone=(), camera=()")

        path = request.url.path
        if not any(path == prefix or path.startswith(prefix + "/") for prefix in _DOCS_PREFIXES):
            # API responses never need to load scripts or frames.
            response.headers.setdefault(
                "Content-Security-Policy",
                "default-src 'none'; frame-ancestors 'none'; base-uri 'none'; form-action 'none'",
            )

        if settings.ENVIRONMENT.strip().lower() == "production" or settings.COOKIE_SECURE:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return response


class CsrfOriginMiddleware(BaseHTTPMiddleware):
    """Reject cross-origin state-changing requests that present a foreign Origin/Referer.

    Complements SameSite cookies and CORS. Missing Origin and Referer are allowed so
    non-browser clients (tests, curl) keep working. Browsers send Origin on
    credentialed cross-site POSTs, which this middleware rejects when not allowlisted.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if request.method in _SAFE_METHODS:
            return await call_next(request)

        origin = request.headers.get("origin")
        if origin:
            if origin == "null" or not _origin_allowed(origin):
                logger.warning("csrf_origin_rejected method=%s", request.method)
                return JSONResponse(status_code=403, content={"detail": "Forbidden."})
            return await call_next(request)

        referer = request.headers.get("referer")
        if referer:
            referer_origin = _referer_origin(referer)
            if referer_origin is None or not _origin_allowed(referer_origin):
                logger.warning("csrf_referer_rejected method=%s", request.method)
                return JSONResponse(status_code=403, content={"detail": "Forbidden."})
        return await call_next(request)


class RequestSizeLimitMiddleware(BaseHTTPMiddleware):
    """Reject oversized request bodies early via Content-Length."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        raw = request.headers.get("content-length")
        if raw is not None:
            try:
                length = int(raw)
            except ValueError:
                return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length."})
            if length > MAX_REQUEST_BODY_BYTES:
                return JSONResponse(status_code=413, content={"detail": "Request body too large."})
        return await call_next(request)


class AuthRateLimitMiddleware(BaseHTTPMiddleware):
    """Simple per-IP rate limit for login and register.

    In-process only. Suitable for development and single-worker demos.
    Production should use a reverse-proxy or shared store limiter.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        path = request.url.path.rstrip("/")
        auth_suffixes = (
            f"{settings.API_PREFIX.rstrip('/')}/auth/login",
            f"{settings.API_PREFIX.rstrip('/')}/auth/register",
        )
        if request.method == "POST" and path in auth_suffixes:
            client = request.client.host if request.client else "unknown"
            if _rate_limited(f"{client}:{path}"):
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Too many attempts. Please try again later."},
                )
        return await call_next(request)


def _origin_allowed(origin: str) -> bool:
    return origin in settings.cors_origin_list


def _referer_origin(referer: str) -> str | None:
    try:
        parts = urlsplit(referer)
    except ValueError:
        return None
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        return None
    return f"{parts.scheme}://{parts.netloc}"


def _rate_limited(key: str) -> bool:
    now = time.monotonic()
    bucket = _auth_hits[key]
    cutoff = now - _AUTH_RATE_WINDOW_SECONDS
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= _AUTH_RATE_LIMIT:
        return True
    bucket.append(now)
    return False


def reset_auth_rate_limits() -> None:
    """Test helper to clear in-process counters."""
    _auth_hits.clear()
