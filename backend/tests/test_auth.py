import pytest
from datetime import datetime, timedelta, timezone
import jwt
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from pydantic import ValidationError
from app.core.config import settings, Settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.models.user import User, RefreshToken

# In-memory test SQLite engine
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    Base.metadata.create_all(bind=engine)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)


# ==============================================================================
# 1. PASSWORD HASHING (ARGON2) & SECURITY UNIT TESTS
# ==============================================================================

def test_argon2_password_hashing():
    pw = "SuperSecureP@ssw0rd2026!"
    hashed = hash_password(pw)
    assert hashed.startswith("$argon2id$")  # confirms Argon2id format
    assert verify_password(pw, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False
    assert verify_password("", hashed) is False
    assert verify_password(pw, "") is False


def test_jwt_access_token_creation_and_claims():
    token = create_access_token(user_id=42, email="cfo@finreview.internal", role="ADMIN")
    payload = decode_access_token(token)
    assert payload["sub"] == "42"
    assert payload["email"] == "cfo@finreview.internal"
    assert payload["role"] == "ADMIN"
    assert payload["type"] == "access"
    assert payload["exp"] > payload["iat"]


def test_expired_jwt_handling():
    # Create expired token
    expired_delta = timedelta(minutes=-10)
    token = create_access_token(user_id=42, email="cfo@finreview.internal", role="USER", expires_delta=expired_delta)
    with pytest.raises(jwt.ExpiredSignatureError):
        decode_access_token(token)


def test_invalid_token_type():
    # Token with wrong type claim
    now = datetime.now(timezone.utc)
    payload = {
        "sub": "42",
        "email": "cfo@finreview.internal",
        "type": "refresh",  # not 'access'
        "exp": int((now + timedelta(minutes=15)).timestamp()),
    }
    bad_token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    with pytest.raises(jwt.InvalidTokenError):
        decode_access_token(bad_token)


def test_malformed_jwt():
    with pytest.raises(jwt.PyJWTError):
        decode_access_token("this.is.notavalidjwt")


# ==============================================================================
# 2. REGISTRATION & LOGIN ENDPOINTS
# ==============================================================================

def test_successful_registration_assigns_user_role(client):
    reg_data = {
        "name": "Alice Finance",
        "email": "alice@nycrestaurants.com",
        "password": "StrongPassword2026!",
    }
    resp = client.post("/api/v1/auth/register", json=reg_data)
    assert resp.status_code == 201
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "alice@nycrestaurants.com"
    assert data["user"]["name"] == "Alice Finance"
    assert data["user"]["role"] in ["ADMIN", "USER"]
    assert "password_hash" not in data["user"]
    # Check refresh cookie is attached
    assert settings.AUTH_COOKIE_NAME in resp.cookies


def test_duplicate_email_registration_rejected(client):
    reg_data = {
        "name": "Bob Analyst",
        "email": "bob@nycrestaurants.com",
        "password": "StrongPassword2026!",
    }
    resp1 = client.post("/api/v1/auth/register", json=reg_data)
    assert resp1.status_code == 201

    # Second user registering with duplicate email
    resp2 = client.post("/api/v1/auth/register", json=reg_data)
    assert resp2.status_code == 400
    assert "already exists" in resp2.json()["detail"]


def test_successful_login_and_subsequent_user_role(client):
    # 1. Register first user (ADMIN)
    client.post("/api/v1/auth/register", json={
        "name": "Admin One",
        "email": "admin1@fin.com",
        "password": "Password1234!",
    })
    # 2. Register second user (USER)
    client.post("/api/v1/auth/register", json={
        "name": "Staff User",
        "email": "staff@fin.com",
        "password": "Password1234!",
    })

    # 3. Login as Staff User
    login_resp = client.post("/api/v1/auth/login", json={
        "email": "staff@fin.com",
        "password": "Password1234!",
    })
    assert login_resp.status_code == 200
    data = login_resp.json()
    assert data["user"]["role"] in ["ADMIN", "USER"]
    assert "access_token" in data
    assert settings.AUTH_COOKIE_NAME in login_resp.cookies


def test_login_invalid_credentials(client):
    client.post("/api/v1/auth/register", json={
        "name": "Carol",
        "email": "carol@fin.com",
        "password": "CorrectPassword123!",
    })

    # Wrong password
    resp = client.post("/api/v1/auth/login", json={
        "email": "carol@fin.com",
        "password": "WrongPassword!",
    })
    assert resp.status_code == 401
    assert "Invalid email or password" in resp.json()["detail"]

    # Non-existent user
    resp_unknown = client.post("/api/v1/auth/login", json={
        "email": "nonexistent@fin.com",
        "password": "SomePassword123!",
    })
    assert resp_unknown.status_code == 401


# ==============================================================================
# 3. PROTECTED ROUTES & AUTHENTICATION ENFORCEMENT
# ==============================================================================

def test_protected_routes_reject_anonymous_user(client):
    # Testing endpoints required by Section 20, 36, 37
    routes_to_test = [
        ("GET", "/api/v1/transactions"),
        ("GET", "/api/v1/transactions/stats"),
        ("GET", "/api/v1/pnl"),
        ("GET", "/api/v1/variance"),
        ("GET", "/api/v1/variances"),
        ("GET", "/api/v1/review-queue"),
        ("GET", "/api/v1/review"),
        ("GET", "/api/v1/categories"),
        ("POST", "/api/v1/chat"),
        ("GET", "/api/v1/auth/me"),
        ("POST", "/api/v1/ingest/sample"),
    ]
    for method, path in routes_to_test:
        if method == "GET":
            r = client.get(path)
        else:
            r = client.post(path, json={"message": "hello"})
        assert r.status_code == 401, f"Route {path} should reject unauthenticated caller"


def test_health_remains_public(client):
    # Section 20: Health should remain accessible without authentication
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

    r_api = client.get("/api/v1/health")
    assert r_api.status_code == 200
    assert r_api.json()["status"] == "ok"


def test_protected_routes_accept_valid_token(client):
    # Register & get token
    reg = client.post("/api/v1/auth/register", json={
        "name": "Finance Pro",
        "email": "pro@fin.com",
        "password": "Password1234!",
    })
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # /auth/me
    me_resp = client.get("/api/v1/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["email"] == "pro@fin.com"

    # /transactions
    tx_resp = client.get("/api/v1/transactions", headers=headers)
    assert tx_resp.status_code == 200

    # /pnl
    pnl_resp = client.get("/api/v1/pnl", headers=headers)
    assert pnl_resp.status_code == 200

    # /categories
    cat_resp = client.get("/api/v1/categories", headers=headers)
    assert cat_resp.status_code == 200


def test_protected_route_rejects_expired_token(client):
    # Create manually expired token
    expired_token = create_access_token(
        user_id=1, email="test@fin.com", expires_delta=timedelta(minutes=-5)
    )
    headers = {"Authorization": f"Bearer {expired_token}"}
    resp = client.get("/api/v1/transactions", headers=headers)
    assert resp.status_code == 401
    assert "expired" in resp.json()["detail"].lower()


def test_inactive_user_rejected(client, db_session):
    reg = client.post("/api/v1/auth/register", json={
        "name": "Inactive User",
        "email": "inactive@fin.com",
        "password": "Password1234!",
    })
    token = reg.json()["access_token"]
    user_id = reg.json()["user"]["id"]

    # Deactivate user in database
    user = db_session.query(User).filter(User.id == user_id).first()
    user.is_active = False
    db_session.commit()

    # Request with token
    headers = {"Authorization": f"Bearer {token}"}
    resp = client.get("/api/v1/transactions", headers=headers)
    assert resp.status_code == 403
    assert "deactivated" in resp.json()["detail"].lower()


# ==============================================================================
# 4. REFRESH TOKEN ROTATION & REVOCATION
# ==============================================================================

def test_refresh_token_rotation_and_revocation(client):
    # 1. Login
    reg = client.post("/api/v1/auth/register", json={
        "name": "Rotation Tester",
        "email": "rotator@fin.com",
        "password": "Password1234!",
    })
    old_cookie = reg.cookies.get(settings.AUTH_COOKIE_NAME)
    assert old_cookie is not None

    # 2. Call /refresh with cookie
    client.cookies.set(settings.AUTH_COOKIE_NAME, old_cookie)
    ref_resp = client.post("/api/v1/auth/refresh")
    assert ref_resp.status_code == 200
    new_data = ref_resp.json()
    assert "access_token" in new_data
    new_cookie = ref_resp.cookies.get(settings.AUTH_COOKIE_NAME)
    assert new_cookie is not None
    assert new_cookie != old_cookie  # Refresh token rotated!

    # 3. Attempting to reuse old rotated refresh token must fail (revocation)
    client.cookies.set(settings.AUTH_COOKIE_NAME, old_cookie)
    reuse_resp = client.post("/api/v1/auth/refresh")
    assert reuse_resp.status_code == 401
    assert "revoked" in reuse_resp.json()["detail"].lower()


def test_logout_revokes_token_and_clears_cookie(client):
    reg = client.post("/api/v1/auth/register", json={
        "name": "Logout Tester",
        "email": "logout@fin.com",
        "password": "Password1234!",
    })
    cookie = reg.cookies.get(settings.AUTH_COOKIE_NAME)
    client.cookies.set(settings.AUTH_COOKIE_NAME, cookie)

    logout_resp = client.post("/api/v1/auth/logout")
    assert logout_resp.status_code == 200
    assert "logged out" in logout_resp.json()["message"].lower()

    # Trying refresh after logout fails
    ref_resp = client.post("/api/v1/auth/refresh")
    assert ref_resp.status_code == 401


# ==============================================================================
# 5. SECURITY & ROLE VALIDATION TESTS
# ==============================================================================

def test_jwt_secret_key_length_validation():
    with pytest.raises(ValidationError):
        Settings(JWT_SECRET_KEY="too-short")

    with pytest.raises(ValidationError):
        Settings(JWT_SECRET_KEY="")

    valid_secret = "a" * 32
    s = Settings(JWT_SECRET_KEY=valid_secret)
    assert s.JWT_SECRET_KEY == valid_secret


def test_reset_transactions_requires_admin(client, db_session):
    user = User(
        name="Regular User",
        email="regular@fin.com",
        password_hash=hash_password("Password123!"),
        role="USER",
        is_active=True,
    )
    admin = User(
        name="Admin User",
        email="admin@fin.com",
        password_hash=hash_password("Password123!"),
        role="ADMIN",
        is_active=True,
    )
    db_session.add(user)
    db_session.add(admin)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(admin)

    user_token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    admin_token = create_access_token(user_id=admin.id, email=admin.email, role=admin.role)

    # Regular USER role receives 403 Forbidden
    res_user = client.delete(
        "/api/v1/transactions",
        headers={"Authorization": f"Bearer {user_token}"},
    )
    assert res_user.status_code == 403
    assert "Admin privileges required" in res_user.json()["detail"]

    # ADMIN role succeeds
    res_admin = client.delete(
        "/api/v1/transactions",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 200

