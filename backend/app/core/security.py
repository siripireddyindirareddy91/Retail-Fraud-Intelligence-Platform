import hashlib
import secrets
from datetime import timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, InvalidHashError

from ..models import now

password_hasher = PasswordHasher()
_dummy_hash = password_hasher.hash(secrets.token_urlsafe(24))


def digest(value: str):
    return hashlib.sha256(value.encode()).hexdigest()


def verify_password(value: str, encoded: str | None):
    try:
        return password_hasher.verify(encoded or _dummy_hash, value) and encoded is not None
    except (VerificationError, InvalidHashError):
        return False


def access_token(settings, user_id: str, session_id: str):
    issued = now()
    return jwt.encode({"sub": user_id, "sid": session_id, "jti": secrets.token_hex(16), "iat": issued, "nbf": issued, "exp": issued + timedelta(minutes=settings.access_minutes), "iss": settings.jwt_issuer, "aud": settings.jwt_audience}, settings.jwt_secret.get_secret_value(), algorithm="HS256")


def decode_access(settings, token: str):
    return jwt.decode(token, settings.jwt_secret.get_secret_value(), algorithms=["HS256"], issuer=settings.jwt_issuer, audience=settings.jwt_audience, options={"require": ["sub", "sid", "jti", "iat", "nbf", "exp", "iss", "aud"]})
