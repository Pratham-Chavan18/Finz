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
from app.services.variance import calculate_monthly_variances

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


def seed_two_month_transactions(db):
    """Seeds transactions with known variances between Jan and Feb."""
    txns = [
        # --- JAN 2026 ---
        # Food Sales: $50,000
        Transaction(transaction_code="T-JAN-01", date=date(2026, 1, 10), description="Food Sales", counterparty="Toast POS", amount=50000.0, category="Food Sales", pnl_bucket="Revenue"),
        # Food Inventory: $20,000 (negative outflow)
        Transaction(transaction_code="T-JAN-02", date=date(2026, 1, 12), description="Sysco Food", counterparty="Sysco", amount=-20000.0, category="Food Inventory / Supplies", pnl_bucket="COGS"),
        # Small supplies: $200 (not material)
        Transaction(transaction_code="T-JAN-03", date=date(2026, 1, 15), description="Staples Pens", counterparty="Staples", amount=-200.0, category="Operating Supplies & Office", pnl_bucket="Operating Expenses"),

        # --- FEB 2026 ---
        # Food Sales: $65,000 (+ $15,000, +30.0%) -> FAVORABLE & MATERIAL
        Transaction(transaction_code="T-FEB-01", date=date(2026, 2, 10), description="Food Sales Batch 1", counterparty="Toast POS", amount=40000.0, category="Food Sales", pnl_bucket="Revenue"),
        Transaction(transaction_code="T-FEB-02", date=date(2026, 2, 20), description="Food Sales Batch 2", counterparty="Toast POS", amount=25000.0, category="Food Sales", pnl_bucket="Revenue"),
        
        # Food Inventory: $28,000 (+ $8,000 expense, +40.0%) -> UNFAVORABLE & MATERIAL
        Transaction(transaction_code="T-FEB-03", date=date(2026, 2, 12), description="Sysco Meat Order", counterparty="Sysco", amount=-18000.0, category="Food Inventory / Supplies", pnl_bucket="COGS"),
        Transaction(transaction_code="T-FEB-04", date=date(2026, 2, 22), description="US Foods Produce", counterparty="US Foods", amount=-10000.0, category="Food Inventory / Supplies", pnl_bucket="COGS"),

        # Small supplies: $250 (+ $50 expense, +25%) -> NOT MATERIAL (< $1000)
        Transaction(transaction_code="T-FEB-05", date=date(2026, 2, 15), description="Staples Paper", counterparty="Staples", amount=-250.0, category="Operating Supplies & Office", pnl_bucket="Operating Expenses"),
    ]
    db.add_all(txns)
    db.commit()


def test_variance_calculation_and_polarity(db_session):
    """Verifies that favorable/unfavorable polarity follows accounting logic."""
    seed_two_month_transactions(db_session)

    res = calculate_monthly_variances(
        db=db_session,
        baseline_month="2026-01",
        current_month="2026-02",
        min_amount=1000.0,
        min_pct=10.0,
        only_material=False,
    )

    cats = {c["category"]: c for c in res["category_variances"]}
    
    # 1. Food Sales: Revenue grew from $50,000 to $65,000 (+15,000 / +30.0%) -> Favorable
    food_sales = cats["Food Sales"]
    assert food_sales["delta_amount"] == 15000.00
    assert food_sales["delta_pct"] == 30.00
    assert food_sales["is_favorable"] is True
    assert food_sales["is_material"] is True

    # 2. Food Inventory: Expense grew from $20,000 to $28,000 (+8,000 / +40.0%) -> Unfavorable
    food_inv = cats["Food Inventory / Supplies"]
    assert food_inv["delta_amount"] == 8000.00
    assert food_inv["delta_pct"] == 40.00
    assert food_inv["is_favorable"] is False  # Cost increase is unfavorable
    assert food_inv["is_material"] is True

    # 3. Operating Supplies: Delta is $50 -> Not material (< $1,000)
    supplies = cats["Operating Supplies & Office"]
    assert supplies["delta_amount"] == 50.00
    assert supplies["is_material"] is False


def test_materiality_filter(db_session):
    """Verifies that only_material=True filters out immaterial shifts."""
    seed_two_month_transactions(db_session)

    res = calculate_monthly_variances(
        db=db_session,
        baseline_month="2026-01",
        current_month="2026-02",
        min_amount=1000.0,
        min_pct=10.0,
        only_material=True,
    )

    material_cats = [c["category"] for c in res["category_variances"]]
    assert "Food Sales" in material_cats
    assert "Food Inventory / Supplies" in material_cats
    assert "Operating Supplies & Office" not in material_cats


def test_driver_attribution(db_session):
    """Verifies that top driving transactions are identified and cited."""
    seed_two_month_transactions(db_session)

    res = calculate_monthly_variances(
        db=db_session,
        baseline_month="2026-01",
        current_month="2026-02",
        only_material=True,
    )

    food_inv = next(c for c in res["category_variances"] if c["category"] == "Food Inventory / Supplies")
    drivers = food_inv["drivers"]
    assert len(drivers) == 2
    assert drivers[0]["transaction_code"] == "T-FEB-03"
    assert drivers[0]["counterparty"] == "Sysco"
    assert "Sysco" in food_inv["explanation"]


def test_api_variance_endpoint(client, db_session):
    """Tests GET /api/v1/variance via FastAPI TestClient."""
    seed_two_month_transactions(db_session)

    res = client.get("/api/v1/variance?baseline_month=2026-01&current_month=2026-02")
    assert res.status_code == 200
    data = res.json()

    assert data["baseline_month"] == "2026-01"
    assert data["current_month"] == "2026-02"
    assert len(data["category_variances"]) == 2
