"""Custom middleware that catches unhandled exceptions, logs them to the
database (timestamp, endpoint, HTTP method, error message, stack trace, and the
authenticated user id when available) and returns a proper JSON error response.

Note on placement: FastAPI/Starlette handle ``HTTPException`` (401/404/422/...)
*inside* the routing layer and convert them to responses before they reach this
middleware. Therefore this middleware only ever sees genuinely *unhandled*
exceptions (i.e. would-be 500s) — exactly what the assignment asks us to log.
"""
from __future__ import annotations

import traceback
import uuid

import jwt
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.logging import get_logger
from app.core.security import decode_token
from app.db.session import AsyncSessionLocal
from app.models.error_log import ErrorLog

logger = get_logger(__name__)


def _extract_user_id(request: Request) -> int | None:
    """Best-effort resolution of the authenticated user id.

    First check request.state (set by the auth dependency), then fall back to
    decoding the bearer token directly — so we can attribute errors even when
    they occur before/around the auth dependency.
    """
    state_uid = getattr(request.state, "user_id", None)
    if state_uid is not None:
        try:
            return int(state_uid)
        except (TypeError, ValueError):
            return None

    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        token = auth.split(" ", 1)[1].strip()
        try:
            payload = decode_token(token)
            sub = payload.get("sub")
            return int(sub) if sub is not None else None
        except (jwt.PyJWTError, TypeError, ValueError):
            return None
    return None


async def _log_error_to_db(
    request: Request, exc: Exception, request_id: str, user_id: int | None
) -> None:
    stack = "".join(
        traceback.format_exception(type(exc), exc, exc.__traceback__)
    )
    try:
        async with AsyncSessionLocal() as session:
            session.add(
                ErrorLog(
                    endpoint=request.url.path,
                    method=request.method,
                    status_code=500,
                    error_message=f"{type(exc).__name__}: {exc}",
                    stack_trace=stack,
                    user_id=user_id,
                )
            )
            await session.commit()
    except Exception:  # noqa: BLE001 - logging must never mask the original error
        logger.exception(
            "Failed to persist error log for request %s (%s %s)",
            request_id,
            request.method,
            request.url.path,
        )


class ExceptionLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = str(uuid.uuid4())
        try:
            return await call_next(request)
        except Exception as exc:  # noqa: BLE001 - intentional catch-all
            user_id = _extract_user_id(request)
            logger.error(
                "Unhandled exception [%s] on %s %s (user=%s): %s",
                request_id,
                request.method,
                request.url.path,
                user_id,
                exc,
            )
            await _log_error_to_db(request, exc, request_id, user_id)
            return JSONResponse(
                status_code=500,
                content={
                    "error": "Internal Server Error",
                    "detail": "An unexpected error occurred and has been logged.",
                    "request_id": request_id,
                },
            )
