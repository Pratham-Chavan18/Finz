from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.core.config import settings

db_url = settings.DATABASE_URL

# Handle sqlite specific connect_args
if db_url.startswith("sqlite"):
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
else:
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
    )

from sqlalchemy import text

SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


def get_db():
    """Dependency that provides an active SQLAlchemy database session."""
    db: Session = SessionLocal()
    try:
        yield db
    finally:
        try:
            bind = db.get_bind()
            if bind and bind.dialect.name == "postgresql":
                db.execute(text("RESET app.current_tenant_id; RESET app.bypass_rls;"))
                db.commit()
        except Exception:
            pass
        db.close()
