import sys
from app.db.session import SessionLocal
from app.models.tenant import Tenant
from app.models.user import User
from app.core.security import hash_password
from app.services.ingest import load_bundled_sample_dataset
from app.services.categorization import run_batch_categorization
from sqlalchemy import text

def seed():
    db = SessionLocal()
    try:
        bind = db.get_bind()
        if bind and bind.dialect.name == "postgresql":
            db.execute(text("SET LOCAL app.bypass_rls = 'on'"))

        tenant = db.query(Tenant).filter_by(id=1).first()
        if not tenant:
            tenant = Tenant(id=1, name="NYC Restaurant Co.", slug="nyc-restaurant-co", plan="pro", status="active")
            db.add(tenant)
            db.commit()
            print("Tenant 1 created.")
        else:
            print("Tenant 1 already exists.")

        user = db.query(User).filter_by(email="analyst@finreview.com").first()
        if not user:
            user = User(
                email="analyst@finreview.com",
                name="Lead Financial Analyst",
                password_hash=hash_password("Password123!"),
                role="ADMIN",
                tenant_id=1,
                is_active=True,
            )
            db.add(user)
            db.commit()
            print("User analyst@finreview.com created.")
        else:
            user.tenant_id = 1
            user.password_hash = hash_password("Password123!")
            db.commit()
            print("User analyst@finreview.com updated.")

        res = load_bundled_sample_dataset(db, tenant_id=1)
        print("Ingest result:", res)

        cat_res = run_batch_categorization(db, tenant_id=1, force=True)
        print("Categorization result:", cat_res)

        # Synchronize PostgreSQL sequences to avoid duplicate key conflicts
        if bind and bind.dialect.name == "postgresql":
            tables = ["tenants", "users", "transactions", "audit_logs", "refresh_tokens", "import_batches"]
            for tbl in tables:
                try:
                    db.execute(text(f"SELECT setval(pg_get_serial_sequence('{tbl}', 'id'), coalesce(max(id), 1)) FROM {tbl};"))
                except Exception:
                    pass
            db.commit()

    except Exception as e:
        db.rollback()
        print(f"Error during seeding: {e}", file=sys.stderr)
        raise
    finally:
        db.close()

if __name__ == "__main__":
    seed()
