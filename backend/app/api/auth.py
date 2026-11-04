import secrets
from datetime import timedelta

from fastapi import APIRouter, Request, Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError

from .deps import CurrentUser, DB
from ..core.errors import APIError
from ..core.security import access_token, digest, password_hasher, verify_password
from ..models import AuditEvent, AuthSession, UsedRefreshToken, User, UserSettings, now, uid
from ..schemas import Credentials, Registration
from ..services.rate_limit import client_key, enforce

router = APIRouter(prefix="/auth", tags=["Authentication"])
COOKIE = "rf_refresh"
CSRF_COOKIE = "rf_csrf"


def user_data(user):
    return {"id": user.id, "email": user.email, "display_name": user.display_name, "role": user.role, "active": user.active}


def verify_origin(request):
    origin = request.headers.get("origin")
    if origin and origin not in request.app.state.settings.allowed_origins:
        raise APIError(403, "untrusted_origin", "This request origin is not allowed.")


def cookies(response, settings, refresh, csrf):
    response.set_cookie(COOKIE, refresh, max_age=settings.refresh_days * 86400, httponly=True, secure=settings.cookie_secure, samesite="strict", path="/api/v1/auth")
    response.set_cookie(CSRF_COOKIE, csrf, max_age=settings.refresh_days * 86400, httponly=False, secure=settings.cookie_secure, samesite="strict", path="/")
    response.headers["Cache-Control"] = "no-store"


def new_session(db, response, settings, user):
    session_id = uid()
    refresh, csrf = f"{session_id}.{secrets.token_urlsafe(48)}", secrets.token_urlsafe(32)
    session = AuthSession(id=session_id, user_id=user.id, refresh_hash=digest(refresh), csrf_hash=digest(csrf), expires_at=now() + timedelta(days=settings.refresh_days))
    db.add(session)
    db.add(AuditEvent(actor_id=user.id, action="auth.login", resource_id=session_id))
    db.commit()
    cookies(response, settings, refresh, csrf)
    return {"access_token": access_token(settings, user.id, session_id), "token_type": "bearer", "user": user_data(user)}


@router.post("/register", status_code=201)
def register(payload: Registration, request: Request, response: Response, db: DB):
    verify_origin(request)
    enforce(db, f"register:{client_key(request)}", request.app.state.settings.register_limit)
    user = User(email=str(payload.email), display_name=payload.display_name, password_hash=password_hasher.hash(payload.password), role="researcher")
    db.add(user)
    try:
        db.flush()
        db.add(UserSettings(user_id=user.id))
        db.add(AuditEvent(actor_id=user.id, action="auth.register", resource_id=user.id))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise APIError(409, "registration_conflict", "An account with this email already exists.")
    return new_session(db, response, request.app.state.settings, user)


@router.post("/login")
def login(payload: Credentials, request: Request, response: Response, db: DB):
    verify_origin(request)
    maximum = request.app.state.settings.login_limit
    enforce(db, f"login-ip:{client_key(request)}", maximum)
    enforce(db, f"login-account:{payload.email}", maximum)
    user = db.scalar(select(User).where(User.email == str(payload.email)))
    if not verify_password(payload.password, user.password_hash if user else None) or not user.active:
        raise APIError(401, "invalid_credentials", "Email or password is incorrect.")
    return new_session(db, response, request.app.state.settings, user)


def cookie_session(request, db):
    verify_origin(request)
    raw = request.cookies.get(COOKIE, "")
    token_hash = digest(raw)
    session = db.scalar(select(AuthSession).where(AuthSession.refresh_hash == token_hash))
    if session is None:
        used = db.get(UsedRefreshToken, token_hash)
        if used:
            session = db.get(AuthSession, used.session_id)
            # Only a matching CSRF token can revoke a rotated session.
            csrf = request.headers.get("x-csrf-token", "")
            if session and secrets.compare_digest(session.csrf_hash, digest(csrf)):
                session.revoked_at = now()
                db.commit()
        raise APIError(401, "invalid_session", "The refresh session is invalid. Sign in again.")
    csrf = request.headers.get("x-csrf-token", "")
    if not csrf or not secrets.compare_digest(session.csrf_hash, digest(csrf)):
        raise APIError(403, "csrf_failed", "A valid CSRF header is required.")
    user = db.get(User, session.user_id)
    if session.revoked_at or session.expires_at <= now() or not user or not user.active:
        raise APIError(401, "invalid_session", "The session has expired or was revoked.")
    return session, user


@router.post("/refresh")
def refresh(request: Request, response: Response, db: DB):
    enforce(db, f"refresh:{client_key(request)}", 120)
    session, user = cookie_session(request, db)
    old_hash = session.refresh_hash
    raw = f"{session.id}.{secrets.token_urlsafe(48)}"
    changed = db.execute(update(AuthSession).where(AuthSession.id == session.id, AuthSession.refresh_hash == old_hash, AuthSession.revoked_at.is_(None)).values(refresh_hash=digest(raw))).rowcount
    if changed != 1:
        db.rollback()
        raise APIError(401, "session_rotated", "The refresh token was already rotated.")
    db.add(UsedRefreshToken(token_hash=old_hash, session_id=session.id))
    db.commit()
    cookies(response, request.app.state.settings, raw, request.headers["x-csrf-token"])
    return {"access_token": access_token(request.app.state.settings, user.id, session.id), "token_type": "bearer", "user": user_data(user)}


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response, db: DB):
    session, user = cookie_session(request, db)
    session.revoked_at = now()
    db.add(AuditEvent(actor_id=user.id, action="auth.logout", resource_id=session.id))
    db.commit()
    response.delete_cookie(COOKIE, path="/api/v1/auth", secure=request.app.state.settings.cookie_secure, httponly=True, samesite="strict")
    response.delete_cookie(CSRF_COOKIE, path="/", secure=request.app.state.settings.cookie_secure, samesite="strict")


@router.get("/me")
def me(user: CurrentUser):
    return user_data(user)
