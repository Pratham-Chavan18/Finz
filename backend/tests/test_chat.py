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
from app.services.chat import fallback_deterministic_query as process_financial_query

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


def seed_chat_test_dataset(db):
    """Seeds controlled transactions for 2026-01 and 2026-02."""
    txns = [
        # JAN 2026
        Transaction(transaction_code="T-REV-101", date=date(2026, 1, 10), description="Toast POS deposit", counterparty="Toast POS", amount=50000.0, category="Food Sales", pnl_bucket="Revenue"),
        Transaction(transaction_code="T-REV-102", date=date(2026, 1, 15), description="Bar register", counterparty="Toast POS", amount=20000.0, category="Beverage Sales", pnl_bucket="Revenue"),
        Transaction(transaction_code="T-COG-101", date=date(2026, 1, 12), description="Sysco Meat", counterparty="Sysco", amount=-21000.0, category="Food Inventory / Supplies", pnl_bucket="COGS"),
        Transaction(transaction_code="T-PAY-101", date=date(2026, 1, 15), description="Biweekly staff pay", counterparty="Gusto", amount=-18000.0, category="Salaries & Wages", pnl_bucket="Payroll"),
        Transaction(transaction_code="T-PAY-102", date=date(2026, 1, 15), description="Employer tax", counterparty="Gusto", amount=-4000.0, category="Payroll Taxes & Benefits", pnl_bucket="Payroll"),
        Transaction(transaction_code="T-OPX-101", date=date(2026, 1, 1), description="Rent", counterparty="Landlord", amount=-6000.0, category="Rent & Occupancy", pnl_bucket="Operating Expenses"),

        # Non-P&L / Flagged
        Transaction(
            transaction_code="T-ATTN-101",
            date=date(2026, 1, 25),
            description="Restaurant Equipment World Oven",
            counterparty="Restaurant Equipment World",
            amount=-7800.0,
            category="Capital Expenditure - Equipment Asset",
            pnl_bucket="Non-P&L",
            confidence=0.90,
            rationale="Major CapEx asset capitalized to balance sheet",
            is_flagged_for_review=True,
            review_status="flagged",
        ),

        # FEB 2026
        Transaction(transaction_code="T-REV-201", date=date(2026, 2, 10), description="Toast POS deposit", counterparty="Toast POS", amount=60000.0, category="Food Sales", pnl_bucket="Revenue"),
        Transaction(transaction_code="T-REV-202", date=date(2026, 2, 15), description="Bar register", counterparty="Toast POS", amount=20000.0, category="Beverage Sales", pnl_bucket="Revenue"),
        Transaction(transaction_code="T-COG-201", date=date(2026, 2, 12), description="Sysco Meat", counterparty="Sysco", amount=-24000.0, category="Food Inventory / Supplies", pnl_bucket="COGS"),
        Transaction(transaction_code="T-PAY-201", date=date(2026, 2, 15), description="Biweekly staff pay", counterparty="Gusto", amount=-24000.0, category="Salaries & Wages", pnl_bucket="Payroll"),
        Transaction(transaction_code="T-OPX-201", date=date(2026, 2, 1), description="Rent", counterparty="Landlord", amount=-6000.0, category="Rent & Occupancy", pnl_bucket="Operating Expenses"),
    ]
    db.add_all(txns)
    db.commit()


def test_query_1_revenue_in_month(db_session):
    """Query 1: 'What was our revenue in Jan 2026?'"""
    seed_chat_test_dataset(db_session)
    res = process_financial_query(db_session, "What was our revenue in Jan 2026?")

    assert "get_monthly_revenue" in res["tools_used"]
    # $50,000 + $20,000 = $70,000.00
    assert "70,000.00" in res["reply"]
    assert "Food Sales" in res["reply"]
    assert len(res["citations"]) > 0


def test_query_2_payroll_each_month(db_session):
    """Query 2: 'How much did we spend on payroll each month?'"""
    seed_chat_test_dataset(db_session)
    res = process_financial_query(db_session, "How much did we spend on payroll each month?")

    assert "get_payroll_spend" in res["tools_used"]
    # Total payroll: Jan $22,000 + Feb $24,000 = $46,000.00
    assert "46,000.00" in res["reply"]
    assert "2026-01" in res["reply"]
    assert "2026-02" in res["reply"]
    assert len(res["citations"]) > 0


def test_query_3_operating_profit_variance(db_session):
    """Query 3: 'Why did operating profit change between Jan and Feb?'"""
    seed_chat_test_dataset(db_session)
    res = process_financial_query(db_session, "Why did operating profit change between Jan and Feb?")

    assert "get_operating_profit_variance" in res["tools_used"]
    # In Jan: GP 42k - OpEx 28k = 14k profit. In Feb: GP 56k - OpEx 30k = 26k profit. Delta = +12,000
    assert "Operating Profit" in res["reply"]
    assert len(res["citations"]) > 0


def test_query_4_transactions_needing_attention(db_session):
    """Query 4: 'Which transactions need my attention?'"""
    seed_chat_test_dataset(db_session)
    res = process_financial_query(db_session, "Which transactions need my attention?")

    assert "get_attention_items" in res["tools_used"]
    assert "T-ATTN-101" in res["reply"]
    assert "Restaurant Equipment World" in res["reply"]
    assert "7,800.00" in res["reply"]
    assert len(res["citations"]) > 0


def test_query_5_transactions_behind_variance(db_session):
    """Query 5: 'Show me the transactions behind that variance'"""
    seed_chat_test_dataset(db_session)
    res = process_financial_query(db_session, "Show me the transactions behind the food inventory variance")

    assert "get_transactions_by_category" in res["tools_used"]
    assert "Sysco" in res["reply"]
    assert len(res["citations"]) > 0


def test_chat_api_endpoints(client, db_session):
    """Tests POST /api/v1/chat and GET /api/v1/chat/suggestions via FastAPI TestClient."""
    seed_chat_test_dataset(db_session)

    # 1. Test suggestions
    sug_res = client.get("/api/v1/chat/suggestions")
    assert sug_res.status_code == 200
    assert len(sug_res.json()["suggestions"]) >= 4

    # 2. Test chat endpoint
    chat_res = client.post(
        "/api/v1/chat",
        json={"message": "What was our revenue in Jan 2026?"},
    )
    assert chat_res.status_code == 200
    data = chat_res.json()
    assert "reply" in data
    assert "citations" in data
    assert "tools_used" in data
    assert "70,000" in data["reply"]
