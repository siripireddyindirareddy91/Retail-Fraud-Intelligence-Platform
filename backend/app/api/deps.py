from typing import Annotated

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from ..core.errors import APIError
from ..core.security import decode_access
from ..models import AuthSession, User, now

bearer = HTTPBearer(auto_error=False)


def get_db(request: Request):
    with request.app.state.sessions() as session:
        yield session


DB = Annotated[Session, Depends(get_db)]


def current_user(request: Request, db: DB, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    try:
        if credentials is None:
            raise ValueError()
        claims = decode_access(request.app.state.settings, credentials.credentials)
        auth_session = db.get(AuthSession, claims["sid"])
        user = db.get(User, claims["sub"])
        if not auth_session or auth_session.user_id != claims["sub"] or auth_session.revoked_at or auth_session.expires_at <= now() or not user or not user.active:
            raise ValueError()
        request.state.auth_session_id = auth_session.id
        return user
    except (jwt.InvalidTokenError, ValueError, KeyError, TypeError):
        raise APIError(401, "authentication_required", "Sign in with a valid, unexpired session.", headers={"WWW-Authenticate": "Bearer"})


CurrentUser = Annotated[User, Depends(current_user)]


def administrator(user: CurrentUser):
    if user.role != "administrator":
        raise APIError(403, "administrator_required", "Administrator access is required.")
    return user


Admin = Annotated[User, Depends(administrator)]


def owned(db, model, resource_id, owner_id, owner_field="owner_id"):
    resource = db.get(model, str(resource_id))
    if resource is None or getattr(resource, owner_field) != owner_id:
        raise APIError(404, "not_found", "The resource was not found.")
    return resource
