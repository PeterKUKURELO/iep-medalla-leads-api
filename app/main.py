from __future__ import annotations

import logging
import re
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from starlette.middleware.trustedhost import TrustedHostMiddleware

from app.config import get_settings
from app.brands import get_brand_registry
from app.database import engine
from app.logging_config import configure_logging
from app.rate_limit import InMemoryRateLimiter
from app.routers.leads import router as leads_router
from app.routers.leads_v2 import router as leads_v2_router
from app.routers.complaints import router as complaints_router

settings = get_settings()
configure_logging()
logger = logging.getLogger(__name__)
get_brand_registry()  # Fail fast before accepting traffic.

app = FastAPI(
    title=settings.app_name,
    version="0.2.0",
    docs_url="/docs" if settings.docs_enabled else None,
    redoc_url="/redoc" if settings.docs_enabled else None,
    openapi_url="/openapi.json" if settings.docs_enabled else None,
)
app.state.rate_limiter = InMemoryRateLimiter(settings.rate_limit_requests, settings.rate_limit_window_seconds)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.frontend_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID"],
)


@app.middleware("http")
async def protect_and_observe_requests(request: Request, call_next):
    started = time.monotonic()
    supplied_request_id = request.headers.get("x-request-id", "")
    request_id = supplied_request_id if re.fullmatch(r"[A-Za-z0-9._-]{1,64}", supplied_request_id) else str(uuid4())

    protected_paths = {"/api/v1/leads", "/api/v2/leads", "/api/v1/complaints"}
    if request.method == "POST" and request.url.path in protected_paths:
        client_ip = request.client.host if request.client else "unknown"
        if not request.app.state.rate_limiter.allow(client_ip):
            response = JSONResponse(
                status_code=429,
                content={"detail": "Demasiados intentos. Intenta nuevamente en unos minutos." if request.url.path == "/api/v1/leads" else "Rate limit exceeded."},
                headers={"Retry-After": str(settings.rate_limit_window_seconds)},
            )
            response.headers["X-Request-ID"] = request_id
            return response

    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > settings.max_body_bytes:
                response = JSONResponse(status_code=413, content={"detail": "Solicitud demasiado grande."})
                response.headers["X-Request-ID"] = request_id
                return response
        except ValueError:
            response = JSONResponse(status_code=400, content={"detail": "Content-Length invalido."})
            response.headers["X-Request-ID"] = request_id
            return response

    if request.method == "POST" and request.url.path in protected_paths:
        chunks = bytearray()
        async for chunk in request.stream():
            chunks.extend(chunk)
            if len(chunks) > settings.max_body_bytes:
                response = JSONResponse(status_code=413, content={"detail": "Solicitud demasiado grande."})
                response.headers["X-Request-ID"] = request_id
                return response
        request._body = bytes(chunks)

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "http_request_completed",
        extra={
            "request_id": request_id,
            "status_code": response.status_code,
            "duration_ms": round((time.monotonic() - started) * 1000, 2),
        },
    )
    return response


@app.get("/health", tags=["health"])
def health() -> JSONResponse:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
    except SQLAlchemyError:
        return JSONResponse(status_code=503, content={"status": "unavailable", "database": "unavailable"})
    return JSONResponse(content={"status": "ok", "database": "ok"})


app.include_router(leads_router)
app.include_router(leads_v2_router)
app.include_router(complaints_router)
