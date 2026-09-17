"""Auth helpers: password hashing, sessions, FastAPI dependencies."""

from __future__ import annotations

import hashlib
import hmac
import re
import secrets
from base64 import b64decode, b64encode
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.database import get_db
from app.models import AuthSession, User, UserRole

SESSION_COOKIE = "holzlinge_session"

# Mitarbeiter: nur Lesen für Staff-UI + Umwandeln
MITARBEITER_ALLOW = (
    ("GET", re.compile(r"^/api/auth/me$")),
    ("POST", re.compile(r"^/api/auth/logout$")),
    ("POST", re.compile(r"^/api/auth/change-password$")),
    ("GET", re.compile(r"^/api/products$")),
    ("GET", re.compile(r"^/api/products/\d+$")),
    ("GET", re.compile(r"^/api/locations$")),
    ("GET", re.compile(r"^/api/movements$")),
    ("GET", re.compile(r"^/api/colors$")),
    ("GET", re.compile(r"^/api/media$")),
    ("GET", re.compile(r"^/api/units$")),
    ("POST", re.compile(r"^/api/products/\d+/transform$")),
)

PUBLIC_API_PATHS = {
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/health"),
}


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    # n=2**14, r=8, p=1 — ausreichend für interne App
    dk = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return "scrypt$16384$8$1$" + b64encode(salt).decode() + "$" + b64encode(dk).decode()


def verify_password(password: str, stored: str) -> bool:
    try:
        algo, n_s, r_s, p_s, salt_b64, hash_b64 = stored.split("$", 5)
        if algo != "scrypt":
            return False
        salt = b64decode(salt_b64)
        expected = b64decode(hash_b64)
        dk = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_s),
            r=int(r_s),
            p=int(p_s),
            dklen=len(expected),
        )
        return hmac.compare_digest(dk, expected)
    except (ValueError, TypeError):
        return False


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_session(db: Session, user: User) -> str:
    token = secrets.token_urlsafe(32)
    idle = timedelta(hours=settings.session_idle_hours)
    now = _utcnow()
    db.add(
        AuthSession(
            user_id=user.id,
            token_hash=hash_token(token),
            created_at=now,
            last_seen_at=now,
            expires_at=now + idle,
        )
    )
    db.commit()
    return token


# Avoid SQLite write storms from parallel UI fetches (Promise.all).
SESSION_TOUCH_MIN_INTERVAL = timedelta(minutes=5)


def touch_session(db: Session, session: AuthSession) -> None:
    idle = timedelta(hours=settings.session_idle_hours)
    now = _utcnow()
    last = session.last_seen_at
    if last is not None:
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if now - last < SESSION_TOUCH_MIN_INTERVAL:
            return
    session.last_seen_at = now
    session.expires_at = now + idle
    db.commit()


def delete_session_by_token(db: Session, token: str | None) -> None:
    if not token:
        return
    row = db.scalars(select(AuthSession).where(AuthSession.token_hash == hash_token(token))).first()
    if row:
        db.delete(row)
        db.commit()


def load_user_for_token(db: Session, token: str | None) -> User | None:
    if not token:
        return None
    session = db.scalars(select(AuthSession).where(AuthSession.token_hash == hash_token(token))).first()
    if not session:
        return None
    now = _utcnow()
    exp = session.expires_at
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < now:
        db.delete(session)
        db.commit()
        return None
    user = db.get(User, session.user_id)
    if not user or not user.is_active:
        db.delete(session)
        db.commit()
        return None
    touch_session(db, session)
    return user


def mitarbeiter_allowed(method: str, path: str) -> bool:
    for m, pattern in MITARBEITER_ALLOW:
        if method.upper() == m and pattern.match(path):
            return True
    return False


def is_public_api(method: str, path: str) -> bool:
    return (method.upper(), path) in PUBLIC_API_PATHS


def get_optional_user(
    request: Request,
    db: Session = Depends(get_db),
    holzlinge_session: Annotated[str | None, Cookie(alias=SESSION_COOKIE)] = None,
) -> User | None:
    state_user = getattr(request.state, "user", None)
    if state_user is not None:
        return state_user
    return load_user_for_token(db, holzlinge_session)


def require_user(user: Annotated[User | None, Depends(get_optional_user)]) -> User:
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Nicht angemeldet")
    return user


def require_admin(user: Annotated[User, Depends(require_user)]) -> User:
    if user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Nur Admin")
    return user


CurrentUser = Annotated[User, Depends(require_user)]
AdminUser = Annotated[User, Depends(require_admin)]
