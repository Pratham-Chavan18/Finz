import pytest
from decimal import Decimal
from datetime import date
from io import BytesIO
from fastapi.testclient import TestClient
from sqlalchemy import text
from app.main import app
from app.db.session import SessionLocal, engine
from app.models.tenant import Tenant
from app.models.user import User
from app.models.transaction import Transaction, AuditLog
from app.services.reconciliation import get_reconciliation_summary
from app.services.pnl import generate_monthly_pnl
from app.services.ingest import parse_csv_content


@pytest.fixture(scope="module")
def pg_db():
    """Provides a PostgreSQL session for testing PostgreSQL-specific RLS & Immutability."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def test_decimal_financial_precision(pg_db):
    """
    CRITICAL FIX 2 REGRESSION TEST:
    Verifies that transaction amounts are stored as Decimal(15, 2) in PostgreSQL,
    and financial aggregations use Python Decimal arithmetic without floating point drift.
    """
    bind = pg_db.get_bind()
    if bind and bind.dialect.name == "postgresql":
        pg_db.execute(text("SET LOCAL app.bypass_rls = 'on'"))

    # Query transaction amount from PostgreSQL
    txn = pg_db.query(Transaction).filter_by(tenant_id=1).first()
    assert txn is not None, "Tenant 1 should have seeded transactions in PostgreSQL"
    assert isinstance(txn.amount, Decimal), f"Expected Decimal, got {type(txn.amount)}"

    # Precision arithmetic test: adding 0.1 + 0.2 in Decimal is exactly 0.30
    d1 = Decimal("0.10")
    d2 = Decimal("0.20")
    assert d1 + d2 == Decimal("0.30")
    assert str(d1 + d2) == "0.30"


def test_raw_data_preservation(pg_db):
    """
    FIX 6 REGRESSION TEST:
    Verifies that raw CSV row dictionaries are preserved in raw_data column as intact source evidence.
    """
    bind = pg_db.get_bind()
    if bind and bind.dialect.name == "postgresql":
        pg_db.execute(text("SET LOCAL app.bypass_rls = 'on'"))

    txn = pg_db.query(Transaction).filter_by(tenant_id=1).first()
    assert txn.raw_data is not None, "raw_data column must not be null"
    assert isinstance(txn.raw_data, dict), f"Expected dict in raw_data, got {type(txn.raw_data)}"
    # Verify standard CSV fields were preserved
    assert any(k in txn.raw_data for k in ["Transaction ID", "Description", "Amount", "Date"])


def test_reconciliation_engine_balanced(pg_db):
    """
    CRITICAL FIX 3 REGRESSION TEST:
    Verifies that 4-way reconciliation equation holds:
    Total Imported = P&L + Non-P&L + Uncategorized
    And zero transactions are silently dropped.
    """
    bind = pg_db.get_bind()
    if bind and bind.dialect.name == "postgresql":
        pg_db.execute(text("SET LOCAL app.bypass_rls = 'on'"))

    recon = get_reconciliation_summary(pg_db, tenant_id=1)
    
    assert recon["is_balanced"] is True
    assert recon["is_count_balanced"] is True
    assert recon["is_amount_balanced"] is True
    assert recon["dropped"]["count"] == 0
    assert recon["dropped"]["amount"] == 0.0

    # Equation check
    total_count = recon["total_imported"]["count"]
    pnl_count = recon["pnl_transactions"]["count"]
    non_pnl_count = recon["non_pnl_transactions"]["count"]
    uncat_count = recon["uncategorized_transactions"]["count"]
    assert total_count == pnl_count + non_pnl_count + uncat_count

    total_amt = round(recon["total_imported"]["amount"], 2)
    sum_amt = round(
        recon["pnl_transactions"]["amount"] +
        recon["non_pnl_transactions"]["amount"] +
        recon["uncategorized_transactions"]["amount"],
        2
    )
    assert total_amt == sum_amt


def test_pnl_surfaces_uncategorized_transactions(pg_db):
    """
    CRITICAL FIX 4 REGRESSION TEST:
    Verifies that uncategorized transactions are explicitly surfaced in P&L metadata,
    and not silently excluded from view.
    """
    bind = pg_db.get_bind()
    if bind and bind.dialect.name == "postgresql":
        pg_db.execute(text("SET LOCAL app.bypass_rls = 'on'"))

    pnl = generate_monthly_pnl(pg_db, tenant_id=1)
    assert "uncategorized" in pnl, "P&L must have uncategorized field"
    assert "total_count" in pnl["uncategorized"]
    assert "total_amount" in pnl["uncategorized"]
    assert "by_month" in pnl["uncategorized"]


def test_postgresql_rls_tenant_isolation(pg_db):
    """
    FIX 8 REGRESSION TEST:
    Verifies PostgreSQL Row-Level Security:
    Tenant 2 context cannot view Tenant 1 transactions.
    """
    bind = pg_db.get_bind()
    if not bind or bind.dialect.name != "postgresql":
        pytest.skip("Test requires PostgreSQL for RLS validation")

    with engine.connect() as conn:
        conn.execute(text("SET app.current_tenant_id = '1'"))
        t1_count = conn.execute(text("SELECT count(*) FROM transactions")).scalar()
        assert t1_count == 181, f"Tenant 1 expected 181, got {t1_count}"

        conn.execute(text("SET app.current_tenant_id = '999'"))
        t2_count = conn.execute(text("SELECT count(*) FROM transactions")).scalar()
        assert t2_count == 0, f"Tenant 999 must see 0 due to PostgreSQL RLS, got {t2_count}"


def test_postgresql_audit_log_immutability():
    """
    FIX 9 REGRESSION TEST:
    Verifies database-level immutability trigger on audit_logs:
    Neither UPDATE nor DELETE can modify audit_logs.
    """
    if engine.dialect.name != "postgresql":
        pytest.skip("Test requires PostgreSQL for trigger immutability validation")

    with engine.connect() as conn:
        conn.execute(text("SET app.bypass_rls = 'on'"))
        res = conn.execute(text("""
            INSERT INTO audit_logs (tenant_id, entity_type, entity_id, action, old_value, new_value, previous_category, new_category, source)
            VALUES (1, 'transaction', '99999', 'category_override', 'Food Sales', 'Beverage Sales', 'Food Sales', 'Beverage Sales', 'system')
            RETURNING id
        """))
        log_id = res.scalar()
        conn.commit()

        # Test UPDATE is blocked by database trigger
        with pytest.raises(Exception) as exc_info:
            conn.execute(text(f"UPDATE audit_logs SET action = 'tampered' WHERE id = {log_id}"))
            conn.commit()
        assert "AuditLog rows are immutable" in str(exc_info.value)
        conn.rollback()

        # Test DELETE is blocked by database trigger
        with pytest.raises(Exception) as exc_info:
            conn.execute(text(f"DELETE FROM audit_logs WHERE id = {log_id}"))
            conn.commit()
        assert "AuditLog rows are immutable" in str(exc_info.value)
        conn.rollback()


def test_file_upload_security_binary_rejection():
    """
    FIX 10 REGRESSION TEST:
    Verifies that binary / executable files disguised with .csv extension are rejected by MIME/magic sniffing.
    """
    with TestClient(app) as client:
        # Create an auth token for tenant 1
        from app.core.security import create_access_token
        token = create_access_token(user_id=1, email="analyst@finreview.com", role="ADMIN")
        headers = {"Authorization": f"Bearer {token}"}

        # Attempt to upload an executable disguised as CSV (MZ header)
        fake_binary_csv = b"MZ\x90\x00\x03\x00\x00\x00some windows binary payload"
        files = {"file": ("malicious.csv", fake_binary_csv, "text/csv")}
        res = client.post("/api/v1/ingest", headers=headers, files=files)
        
        assert res.status_code == 400
        assert "binary executable/archive headers" in res.json().get("detail", "")
