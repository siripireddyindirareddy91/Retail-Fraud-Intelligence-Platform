from datetime import timedelta

import jwt
from sqlalchemy import select

from app.models import AuthSession, User, now
from conftest import register


def csrf(client):
    return {"X-CSRF-Token": client.cookies.get("rf_csrf")}


def test_registration_password_hash_and_no_role_injection(client, app, account, headers):
    assert client.get("/api/v1/auth/me", headers=headers).json()["role"] == "researcher"
    with app.state.sessions() as db:
        user = db.get(User, account["user"]["id"])
        assert user.password_hash.startswith("$argon2id$")
        assert "correct horse" not in user.password_hash
    rejected = client.post("/api/v1/auth/register", json={"email": "other@example.com", "display_name": "Other", "password": "long password value", "role": "administrator"})
    assert rejected.status_code == 422
    assert "long password value" not in rejected.text


def test_login_and_validation(client, account):
    assert client.post("/api/v1/auth/login", json={"email": "researcher@example.com", "password": "incorrect password"}).status_code == 401
    response = client.post("/api/v1/auth/login", json={"email": "RESEARCHER@example.com", "password": "correct horse battery staple"})
    assert response.status_code == 200
    assert "HttpOnly" in response.headers.get_list("set-cookie")[0]
    assert client.post("/api/v1/auth/register", json={"email": "invalid", "password": "secret"}).status_code == 422


def test_refresh_csrf_rotation_replay_and_logout(client, headers):
    assert client.post("/api/v1/auth/refresh").status_code == 403
    old_refresh = client.cookies.get("rf_refresh")
    csrf_header = csrf(client)
    rotated = client.post("/api/v1/auth/refresh", headers=csrf_header)
    assert rotated.status_code == 200
    assert old_refresh != client.cookies.get("rf_refresh")
    replay = client.post("/api/v1/auth/refresh", headers={**csrf_header, "Cookie": f"rf_refresh={old_refresh}; rf_csrf={csrf_header['X-CSRF-Token']}"})
    assert replay.status_code == 401
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    login = client.post("/api/v1/auth/login", json={"email": "researcher@example.com", "password": "correct horse battery staple"}).json()
    fresh = {"Authorization": "Bearer " + login["access_token"]}
    assert client.post("/api/v1/auth/logout", headers=csrf(client)).status_code == 204
    assert client.get("/api/v1/auth/me", headers=fresh).status_code == 401


def test_expired_tampered_and_wrong_audience_tokens(client, account, settings):
    claims = jwt.decode(account["access_token"], options={"verify_signature": False})
    for alteration in ({"exp": now() - timedelta(seconds=10)}, {"aud": "another-app"}, {"iss": "another-issuer"}):
        invalid = jwt.encode({**claims, **alteration}, settings.jwt_secret.get_secret_value(), algorithm="HS256")
        assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer " + invalid}).status_code == 401
    assert client.get("/api/v1/auth/me", headers={"Authorization": "Bearer invalid"}).status_code == 401


def test_origin_and_rate_limit(client, settings):
    settings.login_limit = 2
    data = {"email": "nobody@example.com", "password": "incorrect password"}
    assert client.post("/api/v1/auth/login", json=data, headers={"Origin": "https://untrusted.example"}).status_code == 403
    assert client.post("/api/v1/auth/login", json=data).status_code == 401
    assert client.post("/api/v1/auth/login", json=data).status_code == 401
    limited = client.post("/api/v1/auth/login", json=data)
    assert limited.status_code == 429 and "retry-after" in limited.headers


def test_revoked_or_inactive_account_cannot_use_session(client, account, headers, app):
    with app.state.sessions() as db:
        user = db.get(User, account["user"]["id"])
        user.active = False
        db.commit()
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/refresh", headers=csrf(client)).status_code == 401


def test_sessions_store_only_hashed_refresh_tokens(client, account, app):
    with app.state.sessions() as db:
        session = db.scalar(select(AuthSession))
        assert len(session.refresh_hash) == 64
        assert session.refresh_hash != client.cookies.get("rf_refresh")
