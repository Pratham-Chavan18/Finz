from typing import Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import logging

logger = logging.getLogger(__name__)


def set_tenant_context(db: Session, tenant_id: int) -> None:
    """
    Sets the database session tenant context for PostgreSQL Row-Level Security (RLS).
    Uses transaction-local parameter 'app.current_tenant_id' to prevent connection pool leakage.
    Safe no-op on SQLite for local developer environments while providing defence-in-depth on Postgres.
    """
    bind = db.get_bind()
    if bind and bind.dialect.name == "postgresql":
        try:
            db.execute(
                text("SET app.current_tenant_id = :tenant_id"),
                {"tenant_id": str(tenant_id)},
            )
        except Exception as e:
            logger.warning(f"Could not set PostgreSQL RLS tenant context: {e}")
