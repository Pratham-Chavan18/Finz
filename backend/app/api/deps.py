from typing import Optional, List
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import decode_access_token
from app.core.tenant import set_tenant_context
from app.db.session import get_db
from app.models.user import User
from app.models.tenant import Tenant

security_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    auth_header: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Validates the Bearer access token from Authorization header and returns
    the active User from the database.
    """
    if not auth_header or not auth_header.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication credentials were not provided.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    token = auth_header.credentials
    try:
        payload = decode_access_token(token)
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Access token has expired. Please refresh your session.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(e)}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id_str = payload.get("sub")
    if not user_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing user identifier.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id = int(user_id_str)
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token user identifier.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User associated with token no longer exists.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is deactivated or suspended.",
        )

    # Ensure user has a valid tenant association
    if not user.tenant_id or not user.tenant:
        # Default or initial tenant provisioning
        default_tenant = db.query(Tenant).filter(Tenant.slug == f"tenant-{user.id}").first()
        if not default_tenant:
            default_tenant = Tenant(
                name=f"{user.name}'s Workspace",
                slug=f"workspace-{user.id}",
                plan="STARTER",
                status="active",
            )
            db.add(default_tenant)
            db.commit()
            db.refresh(default_tenant)
        user.tenant_id = default_tenant.id
        db.commit()
        db.refresh(user)

    # Establish transaction-local RLS tenant context
    set_tenant_context(db, user.tenant_id)

    return user


def get_current_tenant(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Tenant:
    """
    Returns the Tenant entity for the authenticated user and asserts RLS context.
    """
    tenant = db.query(Tenant).filter(Tenant.id == current_user.tenant_id).first()
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tenant workspace not found for active user.",
        )
    return tenant


def require_roles(allowed_roles: List[str]):
    """
    RBAC dependency factory checking current_user.role against allowed roles.
    Supported roles: ADMIN, ACCOUNTANT, VIEWER.
    """
    def role_checker(current_user: User = Depends(get_current_user)) -> User:
        user_role = (current_user.role or "VIEWER").upper()
        allowed_normalized = [r.upper() for r in allowed_roles]
        if user_role not in allowed_normalized:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Access forbidden: Admin privileges required. Requires one of {allowed_roles} roles. Your role is '{current_user.role}'.",
            )
        return current_user
    return role_checker


get_current_admin_user = require_roles(["ADMIN"])
get_current_accountant_user = require_roles(["ADMIN", "ACCOUNTANT"])
get_current_viewer_user = require_roles(["ADMIN", "ACCOUNTANT", "VIEWER"])
