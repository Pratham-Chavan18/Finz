import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.transaction import Transaction
from app.services.pnl import generate_monthly_pnl

# In-memory SQLite for test isolation
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


def seed_standard_pnl_transactions(db):
    """Seeds controlled transactions for 2026-01 and 2026-02."""
    txns = [
        # --- MONTH 1: 2026-01 ---
        # Revenue ($70,000)
        Transaction(transaction_code="T-REV-1", date=date(2026, 1, 10), description="Food Sales", amount=50000.0, category="Food Sales", pnl_bucket="Revenue"),
        Transaction(transaction_code="T-REV-2", date=date(2026, 1, 15), description="Bar Sales", amount=20000.0, category="Beverage Sales", pnl_bucket="Revenue"),
        
        # COGS ($28,000)
        Transaction(transaction_code="T-COG-1", date=date(2026, 1, 12), description="Sysco Food", amount=-21000.0, category="Food Inventory / Supplies", pnl_bucket="COGS"),
        Transaction(transaction_code="T-COG-2", date=date(2026, 1, 14), description="Liquor order", amount=-5000.0, category="Beverage Inventory / Alcohol", pnl_bucket="COGS"),
        Transaction(transaction_code="T-COG-3", date=date(2026, 1, 16), description="Takeout boxes", amount=-2000.0, category="Packaging & Disposables", pnl_bucket="COGS"),
        
        # Payroll ($22,000)
        Transaction(transaction_code="T-PAY-1", date=date(2026, 1, 15), description="Wages", amount=-18000.0, category="Salaries & Wages", pnl_bucket="Payroll"),
        Transaction(transaction_code="T-PAY-2", date=date(2026, 1, 15), description="Employer Taxes", amount=-4000.0, category="Payroll Taxes & Benefits", pnl_bucket="Payroll"),

        # OpEx ($8,500)
        Transaction(transaction_code="T-OPX-1", date=date(2026, 1, 1), description="Rent", amount=-6000.0, category="Rent & Occupancy", pnl_bucket="Operating Expenses"),
        Transaction(transaction_code="T-OPX-2", date=date(2026, 1, 20), description="Power & Gas", amount=-2000.0, category="Utilities (Electric, Gas, Water)", pnl_bucket="Operating Expenses"),
        Transaction(transaction_code="T-OPX-3", date=date(2026, 1, 5), description="Toast Cloud POS", amount=-500.0, category="Software & POS Subscriptions", pnl_bucket="Operating Expenses"),

        # Non-P&L: CapEx & Sales Tax ($13,000)
        Transaction(transaction_code="T-NP-1", date=date(2026, 1, 25), description="New Pizza Oven", amount=-10000.0, category="Capital Expenditure - Equipment Asset", pnl_bucket="Non-P&L"),
        Transaction(transaction_code="T-NP-2", date=date(2026, 1, 28), description="Sales Tax Payment", amount=-3000.0, category="Sales Tax Remittance", pnl_bucket="Non-P&L"),

        # --- MONTH 2: 2026-02 ---
        # Revenue ($80,000)
        Transaction(transaction_code="T-REV-3", date=date(2026, 2, 10), description="Food Sales", amount=60000.0, category="Food Sales", pnl_bucket="Revenue"),
        Transaction(transaction_code="T-REV-4", date=date(2026, 2, 15), description="Bar Sales", amount=20000.0, category="Beverage Sales", pnl_bucket="Revenue"),
        
        # COGS ($32,000)
        Transaction(transaction_code="T-COG-4", date=date(2026, 2, 12), description="Sysco Food", amount=-24000.0, category="Food Inventory / Supplies", pnl_bucket="COGS"),
        Transaction(transaction_code="T-COG-5", date=date(2026, 2, 14), description="Liquor order", amount=-8000.0, category="Beverage Inventory / Alcohol", pnl_bucket="COGS"),
        
        # Payroll ($24,000)
        Transaction(transaction_code="T-PAY-3", date=date(2026, 2, 15), description="Wages", amount=-24000.0, category="Salaries & Wages", pnl_bucket="Payroll"),

        # OpEx ($8,000)
        Transaction(transaction_code="T-OPX-4", date=date(2026, 2, 1), description="Rent", amount=-6000.0, category="Rent & Occupancy", pnl_bucket="Operating Expenses"),
        Transaction(transaction_code="T-OPX-5", date=date(2026, 2, 20), description="Power & Gas", amount=-2000.0, category="Utilities (Electric, Gas, Water)", pnl_bucket="Operating Expenses"),
    ]
    db.add_all(txns)
    db.commit()


def test_deterministic_pnl_arithmetic(db_session):
    """Verifies that mathematical calculations produce exact expected accounting outputs."""
    seed_standard_pnl_transactions(db_session)

    pnl = generate_monthly_pnl(db_session)
    assert pnl["months"] == ["2026-01", "2026-02"]

    # Month 1 checks:
    m1 = pnl["summary"]["2026-01"]
    assert m1["revenue"] == 70000.00
    assert m1["cogs"] == 28000.00
    assert m1["gross_profit"] == 42000.00
    assert m1["gross_margin_pct"] == 60.00
    assert m1["payroll"] == 22000.00
    assert m1["opex"] == 8500.00
    assert m1["total_operating_expenses"] == 30500.00
    # Operating Profit = 42000 - 30500 = 11500
    assert m1["operating_profit"] == 11500.00
    # Operating Margin % = 11500 / 70000 * 100 = 16.43%
    assert m1["operating_margin_pct"] == 16.43

    # Month 2 checks:
    m2 = pnl["summary"]["2026-02"]
    assert m2["revenue"] == 80000.00
    assert m2["cogs"] == 32000.00
    assert m2["gross_profit"] == 48000.00
    assert m2["gross_margin_pct"] == 60.00
    assert m2["payroll"] == 24000.00
    assert m2["opex"] == 8000.00
    assert m2["total_operating_expenses"] == 32000.00
    # Operating Profit = 48000 - 32000 = 16000
    assert m2["operating_profit"] == 16000.00
    assert m2["operating_margin_pct"] == 20.00

    # Grand Total checks:
    tot = pnl["summary"]["total"]
    assert tot["revenue"] == 150000.00
    assert tot["cogs"] == 60000.00
    assert tot["gross_profit"] == 90000.00
    assert tot["gross_margin_pct"] == 60.00
    assert tot["payroll"] == 46000.00
    assert tot["opex"] == 16500.00
    assert tot["total_operating_expenses"] == 62500.00
    assert tot["operating_profit"] == 27500.00


def test_non_pnl_isolation(db_session):
    """Proves that CapEx and tax payments are excluded from Operating Profit."""
    seed_standard_pnl_transactions(db_session)
    pnl = generate_monthly_pnl(db_session)

    # In 2026-01, $10,000 oven and $3,000 tax remittance must NOT lower operating profit
    m1 = pnl["summary"]["2026-01"]
    assert m1["operating_profit"] == 11500.00

    # Non-P&L section should capture them separately
    non_pnl = pnl["sections"]["non_pnl"]
    assert non_pnl["monthly_totals"]["2026-01"] == 13000.00
    assert len(non_pnl["lines"]) == 2


def test_api_pnl_endpoint(client, db_session):
    """Tests GET /api/v1/pnl endpoint via FastAPI TestClient."""
    seed_standard_pnl_transactions(db_session)

    res = client.get("/api/v1/pnl")
    assert res.status_code == 200
    data = res.json()

    assert "months" in data
    assert "summary" in data
    assert "sections" in data
    assert data["summary"]["total"]["revenue"] == 150000.00
    assert data["summary"]["2026-01"]["gross_profit"] == 42000.00
