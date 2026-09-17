"""HTTP middleware enforcing login and Mitarbeiter API allowlist."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth import (
    SESSION_COOKIE,
    is_public_api,
    load_user_for_token,
    mitarbeiter_allowed,
)
from app.database import SessionLocal
from app.models import UserRole


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        method = request.method.upper()

        if not path.startswith("/api"):
            return await call_next(request)

        if is_public_api(method, path):
            return await call_next(request)

        # OPTIONS for CORS
        if method == "OPTIONS":
            return await call_next(request)

        # Auth DB work must finish before call_next — never hold a connection
        # across the route handler (pool exhaustion + SQLite lock contention).
        db = SessionLocal()
        try:
            token = request.cookies.get(SESSION_COOKIE)
            user = load_user_for_token(db, token)
            if not user:
                return JSONResponse({"detail": "Nicht angemeldet"}, status_code=401)
            if user.role == UserRole.MITARBEITER and not mitarbeiter_allowed(method, path):
                return JSONResponse({"detail": "Keine Berechtigung"}, status_code=403)
            # Detach before close so request.state keeps a usable User instance.
            _ = (user.id, user.username, user.role, user.is_active)
            db.expunge(user)
            request.state.user = user
        finally:
            db.close()

        return await call_next(request)
