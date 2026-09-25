from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import NullPool
from app.core.config import settings

db_url = settings.DATABASE_URL

# Handle sqlite vs Supabase connection pooler (port 6543)
is_sqlite = db_url.startswith("sqlite")
is_pooler = ":6543" in db_url or "pooler" in db_url or "supavisor" in db_url

if is_sqlite:
    engine = create_engine(
        db_url,
        connect_args={"check_same_thread": False},
    )
elif is_pooler:
    # Supabase Transaction Pooler (port 6543) requires NullPool to prevent connection state issues
    engine = create_engine(
        db_url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
else:
    engine = create_engine(
        db_url,
        pool_pre_ping=True,
    )

SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


def get_db():
    """Dependency that provides an active SQLAlchemy database session."""
    db: Session = SessionLocal()
    try:
        yield db
    except Exception:
        try:
            db.rollback()
        except Exception:
            pass
        raise
    finally:
        try:
            bind = db.get_bind()
            if bind and bind.dialect.name == "postgresql":
                db.execute(text("RESET app.current_tenant_id; RESET app.bypass_rls;"))
        except Exception:
            pass
        finally:
            db.close()
