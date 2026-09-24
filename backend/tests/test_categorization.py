import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.transaction import Transaction, AuditLog
from app.services.categorization import (
    classify_transaction_rule_based,
    run_batch_categorization,
    update_transaction_category,
    CHART_OF_ACCOUNTS,
)

# In-memory SQLite database for test isolation
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"

engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
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
    app.dependency_overrides.clear()


def test_chart_of_accounts_structure():
    """Verifies that all 5 key P&L and Non-P&L buckets are defined."""
    buckets = {item["pnl_bucket"] for item in CHART_OF_ACCOUNTS}
    assert "Revenue" in buckets
    assert "COGS" in buckets
    assert "Payroll" in buckets
    assert "Operating Expenses" in buckets
    assert "Non-P&L" in buckets


def test_rule_based_classification_golden_vendors():
    """Tests accounting heuristics on key real-world restaurant vendors."""
    # 1. COGS: Food
    cat, bucket, conf, _, _ = classify_transaction_rule_based("Sysco wholesale ingredients", "Sysco", -1245.50)
    assert bucket == "COGS"
    assert cat == "Food Inventory / Supplies"
    assert conf >= 0.90

    # 2. COGS: Beverage
    cat, bucket, conf, _, _ = classify_transaction_rule_based("Southern Glazer invoice", "Southern Glazer", -850.00)
    assert bucket == "COGS"
    assert cat == "Beverage Inventory / Alcohol"

    # 3. Payroll: Wages
    cat, bucket, conf, _, _ = classify_transaction_rule_based("Biweekly staff wages", "Gusto", -9450.00)
    assert bucket == "Payroll"
    assert cat == "Salaries & Wages"

    # 4. OpEx: Rent
    cat, bucket, conf, _, _ = classify_transaction_rule_based("Monthly retail lease", "Landlord", -6500.00)
    assert bucket == "Operating Expenses"
    assert cat == "Rent & Occupancy"

    # 5. Revenue: Food Sales
    cat, bucket, conf, _, _ = classify_transaction_rule_based("POS batch food sales", "Toast POS", 4500.00)
    assert bucket == "Revenue"
    assert cat == "Food Sales"

    # 6. Non-P&L: CapEx Equipment Asset
    cat, bucket, conf, _, flagged = classify_transaction_rule_based("Equipment purchase - new oven", "Restaurant Equipment World", -7800.00)
    assert bucket == "Non-P&L"
    assert cat == "Capital Expenditure - Equipment Asset"
    assert flagged is True  # Must be flagged for balance sheet review

    # 7. Non-P&L: Sales Tax Remittance
    cat, bucket, conf, _, flagged = classify_transaction_rule_based("Sales tax remittance payment", "Dept. of Revenue", -1900.00)
    assert bucket == "Non-P&L"
    assert cat == "Sales Tax Remittance"
    assert flagged is True


def test_batch_categorization(db_session):
    """Verifies that run_batch_categorization assigns categories and sets review flags."""
    tx1 = Transaction(
        transaction_code="T101",
        date=date(2026, 1, 15),
        description="Sysco Fresh Produce",
        counterparty="Sysco",
        amount=-820.00,
    )
    tx2 = Transaction(
        transaction_code="T102",
        date=date(2026, 1, 16),
        description="Equipment purchase - new oven",
        counterparty="Restaurant Equipment World",
        amount=-7800.00,
    )
    db_session.add_all([tx1, tx2])
    db_session.commit()

    result = run_batch_categorization(db_session)
    assert result["categorized_count"] == 2
    assert result["flagged_for_review"] >= 1

    db_session.refresh(tx1)
    db_session.refresh(tx2)

    assert tx1.category == "Food Inventory / Supplies"
    assert tx1.pnl_bucket == "COGS"
    assert tx1.is_flagged_for_review is False

    assert tx2.category == "Capital Expenditure - Equipment Asset"
    assert tx2.pnl_bucket == "Non-P&L"
    assert tx2.is_flagged_for_review is True
    assert tx2.review_status == "flagged"


def test_user_category_correction_creates_audit_log(db_session):
    """Verifies that updating a transaction records an immutable audit log and updates status."""
    tx = Transaction(
        transaction_code="T201",
        date=date(2026, 1, 20),
        description="Miscellaneous Amazon purchase",
        counterparty="Amazon",
        amount=-150.00,
        category="Operating Supplies & Office",
        pnl_bucket="Operating Expenses",
        confidence=0.70,
        is_flagged_for_review=True,
        review_status="flagged",
    )
    db_session.add(tx)
    db_session.commit()

    # User reclassifies to Packaging & Disposables
    updated = update_transaction_category(
        db=db_session,
        transaction_id=tx.id,
        new_category="Packaging & Disposables",
        note="These were to-go containers ordered on Amazon",
        source="user",
    )

    assert updated.category == "Packaging & Disposables"
    assert updated.pnl_bucket == "COGS"
    assert updated.review_status == "corrected"
    assert updated.is_flagged_for_review is False

    # Check AuditLog
    audit = db_session.query(AuditLog).filter(AuditLog.transaction_id == tx.id).first()
    assert audit is not None
    assert audit.previous_category == "Operating Supplies & Office"
    assert audit.new_category == "Packaging & Disposables"
    assert audit.source == "user"
    assert "to-go containers" in audit.note


def test_api_categorize_and_correction_flow(client, db_session):
    """Integration test of API endpoints: categories, batch categorize, patch category, audit logs."""
    # 1. Test GET /api/v1/categories
    cat_res = client.get("/api/v1/categories")
    assert cat_res.status_code == 200
    data = cat_res.json()
    assert "chart_of_accounts" in data
    assert len(data["chart_of_accounts"]) >= 15

    # 2. Seed a transaction
    tx = Transaction(
        transaction_code="T301",
        date=date(2026, 2, 1),
        description="Gusto Payroll Run",
        counterparty="Gusto",
        amount=-5200.00,
    )
    db_session.add(tx)
    db_session.commit()

    # 3. Test POST /api/v1/categorize/batch
    batch_res = client.post("/api/v1/categorize/batch")
    assert batch_res.status_code == 200
    assert batch_res.json()["categorized_count"] == 1

    # Verify transaction updated
    db_session.refresh(tx)
    assert tx.category == "Salaries & Wages"

    # 4. Test PATCH /api/v1/transactions/{id}/category
    patch_res = client.patch(
        f"/api/v1/transactions/{tx.id}/category",
        json={"category": "Payroll Taxes & Benefits", "note": "Adjusted to taxes bucket"},
    )
    assert patch_res.status_code == 200
    assert patch_res.json()["transaction"]["category"] == "Payroll Taxes & Benefits"

    # 5. Test GET /api/v1/audit-logs
    audit_res = client.get("/api/v1/audit-logs")
    assert audit_res.status_code == 200
    logs = audit_res.json()["logs"]
    assert len(logs) == 1
    assert logs[0]["transaction_id"] == tx.id
    assert logs[0]["previous_category"] == "Salaries & Wages"
    assert logs[0]["new_category"] == "Payroll Taxes & Benefits"
