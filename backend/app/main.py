import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from app.api.audits import router as audits_router
from app.api.auth import router as auth_router
from app.api.brands import router as brands_router
from app.api.dashboard import router as dashboard_router
from app.api.health import router as health_router
from app.api.intelligence import router as intelligence_router
from app.api.query_explorer import router as query_explorer_router
from app.api.reports import router as reports_router
from app.core.config import settings
from app.core.database import engine
from app.core.middleware import (
    AuthRateLimitMiddleware,
    CsrfOriginMiddleware,
    RequestSizeLimitMiddleware,
    SecurityHeadersMiddleware,
)

_LOG_FORMAT = "%(levelname)s %(name)s %(message)s"


def _configure_logging() -> None:
    root = logging.getLogger()
    if not root.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(_LOG_FORMAT))
        root.addHandler(handler)
    root.setLevel(logging.INFO)

    for name in ("app", "app.security", "app.crawler", "uvicorn.access", "uvicorn.error"):
        log = logging.getLogger(name)
        log.setLevel(logging.INFO)
        if not log.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter(_LOG_FORMAT))
            log.addHandler(handler)
            log.propagate = False


_configure_logging()
logger = logging.getLogger("app")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log method/path/status without cookies, Authorization, or other secrets."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        response = await call_next(request)
        logging.getLogger("app").info(
            "request method=%s path=%s status=%s",
            request.method,
            request.url.path,
            response.status_code,
        )
        return response


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "startup environment=%s api_prefix=%s cookie_secure=%s",
        settings.ENVIRONMENT,
        settings.API_PREFIX,
        settings.COOKIE_SECURE,
    )
    try:
        yield
    finally:
        engine.dispose()
        logger.info("shutdown complete")


app = FastAPI(
    title="AI Brand Intelligence API",
    description="Backend API for the AI Brand Intelligence platform.",
    version="0.1.0",
    lifespan=lifespan,
    docs_url=None if settings.is_production else "/docs",
    redoc_url=None if settings.is_production else "/redoc",
    openapi_url=None if settings.is_production else "/openapi.json",
)

# Middleware is applied in reverse order of addition (last added = outermost).
# CORS must be outermost so preflight OPTIONS is handled before CSRF checks.
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(RequestSizeLimitMiddleware)
app.add_middleware(AuthRateLimitMiddleware)
app.add_middleware(CsrfOriginMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)

app.include_router(health_router, prefix=settings.API_PREFIX)
app.include_router(auth_router, prefix=settings.API_PREFIX)
app.include_router(brands_router, prefix=settings.API_PREFIX)
app.include_router(dashboard_router, prefix=settings.API_PREFIX)
app.include_router(intelligence_router, prefix=settings.API_PREFIX)
app.include_router(query_explorer_router, prefix=settings.API_PREFIX)
app.include_router(reports_router, prefix=settings.API_PREFIX)
app.include_router(audits_router, prefix=settings.API_PREFIX)


@app.exception_handler(SQLAlchemyError)
async def handle_database_error(_request: Request, _exc: SQLAlchemyError) -> JSONResponse:
    logging.getLogger("app.security").exception("database_error")
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred."},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    # Preserve FastAPI/Starlette HTTP and validation errors; never leak internals.
    if isinstance(exc, StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content={"detail": exc.detail},
            headers=dict(exc.headers) if exc.headers else None,
        )
    if isinstance(exc, RequestValidationError):
        return JSONResponse(status_code=422, content={"detail": jsonable_encoder(exc.errors())})

    logging.getLogger("app.security").exception("unhandled_error type=%s", type(exc).__name__)
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal error occurred."},
    )
