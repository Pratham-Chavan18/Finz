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


def test_review_queue_listing_and_actions(client, db_session):
    """Integration test for review queue retrieval, confirmation, and dismissal."""
    # Seed 1 flagged item and 1 unflagged item
    t1 = Transaction(
        transaction_code="T-REV-01",
        date=date(2026, 1, 10),
        description="Restaurant Equipment World - Commercial Oven",
        counterparty="Restaurant Equipment World",
        amount=-7800.0,
        category="Capital Expenditure - Equipment Asset",
        pnl_bucket="Non-P&L",
        confidence=0.92,
        rationale="CapEx asset requiring review",
        is_flagged_for_review=True,
        review_status="flagged",
    )
    t2 = Transaction(
        transaction_code="T-REV-02",
        date=date(2026, 1, 12),
        description="Sysco Produce Delivery",
        counterparty="Sysco",
        amount=-1200.0,
        category="Food Inventory / Supplies",
        pnl_bucket="COGS",
        confidence=0.96,
        is_flagged_for_review=False,
        review_status="pending",
    )
    t3 = Transaction(
        transaction_code="T-REV-03",
        date=date(2026, 1, 14),
        description="Ambiguous vendor payment",
        counterparty="Vendor X",
        amount=-450.0,
        category="Operating Supplies & Office",
        pnl_bucket="Operating Expenses",
        confidence=0.65,
        rationale="Low confidence classification",
        is_flagged_for_review=True,
        review_status="flagged",
    )
    db_session.add_all([t1, t2, t3])
    db_session.commit()

    # 1. Fetch Review Queue (should return exactly t1 and t3)
    res = client.get("/api/v1/review-queue")
    assert res.status_code == 200
    data = res.json()
    assert data["count"] == 2
    codes = [item["transaction_code"] for item in data["items"]]
    assert "T-REV-01" in codes
    assert "T-REV-03" in codes
    assert "T-REV-02" not in codes

    # 2. Confirm classification of T-REV-01
    confirm_res = client.post(f"/api/v1/transactions/{t1.id}/confirm")
    assert confirm_res.status_code == 200
    assert confirm_res.json()["review_status"] == "confirmed"
    assert confirm_res.json()["is_flagged_for_review"] is False

    # Check AuditLog
    audit_confirm = db_session.query(AuditLog).filter(AuditLog.transaction_id == t1.id).first()
    assert audit_confirm is not None
    assert audit_confirm.source == "user"
    assert "Confirmed classification" in audit_confirm.note

    # 3. Dismiss review flag for T-REV-03
    dismiss_res = client.post(f"/api/v1/transactions/{t3.id}/dismiss")
    assert dismiss_res.status_code == 200
    assert dismiss_res.json()["review_status"] == "dismissed"
    assert dismiss_res.json()["is_flagged_for_review"] is False

    # 4. Review Queue should now be empty (0 items)
    empty_res = client.get("/api/v1/review-queue")
    assert empty_res.status_code == 200
    assert empty_res.json()["count"] == 0
