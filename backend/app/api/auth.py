from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    generate_refresh_token,
    hash_refresh_token,
)
from app.db.session import get_db
from app.models.user import User, RefreshToken
from app.schemas.auth import (
    UserRegister,
    UserLogin,
    UserResponse,
    TokenResponse,
    MessageResponse,
)
from app.api.deps import get_current_user

auth_router = APIRouter(prefix="/auth", tags=["authentication"])


def set_refresh_cookie(response: Response, raw_token: str) -> None:
    """Helper to set secure HttpOnly refresh token cookie."""
    response.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=raw_token,
        httponly=True,
        secure=settings.AUTH_COOKIE_SECURE,
        samesite=settings.AUTH_COOKIE_SAMESITE,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )


def clear_refresh_cookie(response: Response) -> None:
    """Helper to clear refresh token cookie."""
    response.delete_cookie(
        key=settings.AUTH_COOKIE_NAME,
        path="/",
        samesite=settings.AUTH_COOKIE_SAMESITE,
    )


@auth_router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
def register(
    payload: UserRegister,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Register a new user account with Argon2 password hashing.
    Issues short-lived access JWT in response body and long-lived refresh token in HttpOnly cookie.
    """
    normalized_email = payload.email.lower().strip()
    existing = db.query(User).filter(User.email == normalized_email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="An account with this email already exists.",
        )

    # Provision company workspace / tenant
    import re
    from app.models.tenant import Tenant

    company_title = (payload.company_name or f"{payload.name.strip()}'s Restaurant Co.").strip()
    slug_base = re.sub(r'[^a-z0-9]+', '-', company_title.lower()).strip('-') or 'workspace'
    slug = f"{slug_base}-{int(datetime.now(timezone.utc).timestamp())}"
    tenant = Tenant(
        name=company_title,
        slug=slug,
        plan="STARTER",
        status="active",
    )
    db.add(tenant)
    db.commit()
    db.refresh(tenant)

    hashed_pw = hash_password(payload.password)
    user = User(
        tenant_id=tenant.id,
        name=payload.name.strip(),
        email=normalized_email,
        password_hash=hashed_pw,
        role="ADMIN",  # First user in a new company workspace is ADMIN
        is_active=True,
        last_login_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    # Issue access token
    access_token = create_access_token(user_id=user.id, email=user.email, role=user.role)

    # Issue refresh token
    raw_token, token_hash, expires_at = generate_refresh_token()
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        is_revoked=False,
    )
    db.add(refresh_record)
    db.commit()

    set_refresh_cookie(response, raw_token)

    user_resp = UserResponse.model_validate(user)
    user_resp.tenant_id = user.tenant_id
    user_resp.tenant_name = tenant.name

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=user_resp,
    )


@auth_router.post("/login", response_model=TokenResponse)
def login(
    payload: UserLogin,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Authenticate user credentials, return short-lived access JWT,
    and attach HttpOnly refresh token cookie.
    """
    normalized_email = payload.email.lower().strip()
    user = db.query(User).filter(User.email == normalized_email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated or suspended.",
        )

    # Update last login timestamp
    user.last_login_at = datetime.now(timezone.utc)

    # Issue access token
    access_token = create_access_token(user_id=user.id, email=user.email, role=user.role)

    # Issue refresh token and store hash
    raw_token, token_hash, expires_at = generate_refresh_token()
    refresh_record = RefreshToken(
        user_id=user.id,
        token_hash=token_hash,
        expires_at=expires_at,
        is_revoked=False,
    )
    db.add(refresh_record)
    db.commit()

    set_refresh_cookie(response, raw_token)

    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@auth_router.post("/refresh", response_model=TokenResponse)
def refresh_session(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Validate refresh token cookie, rotate refresh token, and return a new access token.
    Never exposes refresh token to client-side JavaScript.
    """
    raw_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    if not raw_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token missing from request cookies.",
        )

    token_hash = hash_refresh_token(raw_token)
    token_record = (
        db.query(RefreshToken)
        .filter(RefreshToken.token_hash == token_hash)
        .first()
    )

    now = datetime.now(timezone.utc)
    if not token_record or token_record.is_revoked:
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked refresh token. Please sign in again.",
        )

    # Handle expiration (convert naive/aware if needed)
    record_exp = token_record.expires_at
    if record_exp.tzinfo is None:
        record_exp = record_exp.replace(tzinfo=timezone.utc)

    if record_exp < now:
        token_record.is_revoked = True
        db.commit()
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Expired refresh token. Please sign in again.",
        )

    user = db.query(User).filter(User.id == token_record.user_id).first()
    if not user or not user.is_active:
        clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User account is inactive or not found.",
        )

    # Token Rotation: Revoke old token and issue a fresh one
    token_record.is_revoked = True

    new_raw, new_hash, new_exp = generate_refresh_token()
    new_record = RefreshToken(
        user_id=user.id,
        token_hash=new_hash,
        expires_at=new_exp,
        is_revoked=False,
    )
    db.add(new_record)
    db.commit()

    # Issue new access token
    new_access_token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    set_refresh_cookie(response, new_raw)

    return TokenResponse(
        access_token=new_access_token,
        token_type="bearer",
        user=UserResponse.model_validate(user),
    )


@auth_router.post("/logout", response_model=MessageResponse)
def logout(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
):
    """
    Revokes the refresh token in the database and clears the HttpOnly cookie.
    """
    raw_token = request.cookies.get(settings.AUTH_COOKIE_NAME)
    if raw_token:
        token_hash = hash_refresh_token(raw_token)
        token_record = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == token_hash)
            .first()
        )
        if token_record:
            token_record.is_revoked = True
            db.commit()

    clear_refresh_cookie(response)
    return MessageResponse(message="Successfully logged out.")


@auth_router.get("/me", response_model=UserResponse)
def get_current_user_profile(
    current_user: User = Depends(get_current_user),
):
    """
    Returns the authenticated user's profile.
    Password hash is never included.
    """
    return UserResponse.model_validate(current_user)
