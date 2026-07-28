"""
ERPX API entrypoint.

Boots the FastAPI application: structured logging, CORS, request-context
middleware, security headers, response compression, rate limiting,
Prometheus metrics, global exception handlers, and the versioned API
router. Run in development with:

    uvicorn app.main:app --reload

or via docker-compose (`docker compose up api`).
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from prometheus_fastapi_instrumentator import Instrumentator
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.exception_handlers import register_exception_handlers
from app.core.logging_config import configure_logging, get_logger
from app.middleware.request_context import RequestContextMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from modules.audit.hooks import register_audit_hooks

configure_logging()
logger = get_logger(__name__)
register_audit_hooks()

limiter = Limiter(key_func=get_remote_address, default_limits=[settings.RATE_LIMIT_DEFAULT])


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("erpx_api_startup", environment=settings.ENVIRONMENT)
    yield
    logger.info("erpx_api_shutdown")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.PROJECT_NAME,
        description="ERPX — Enterprise ERP + LMS + CRM + Accounting + Pentrix Platform",
        version="0.1.0",
        docs_url="/api/docs" if not settings.is_production else None,
        redoc_url="/api/redoc" if not settings.is_production else None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    # ---- Rate limiting ----
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

    # ---- CORS ----
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
        expose_headers=["X-Request-ID"],
    )

    # ---- Response compression ----
    # Only bodies over 1KB are compressed — smaller payloads aren't worth the CPU cost.
    app.add_middleware(GZipMiddleware, minimum_size=1024)

    # ---- Request context / access logging ----
    app.add_middleware(RequestContextMiddleware)

    # ---- Security headers ----
    app.add_middleware(SecurityHeadersMiddleware)

    # ---- Global exception handling ----
    register_exception_handlers(app)

    # ---- Routers ----
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # ---- Prometheus metrics (exposed at /metrics, scraped by the Prometheus
    # server configured in infrastructure/monitoring) ----
    Instrumentator().instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

    return app


app = create_app()
