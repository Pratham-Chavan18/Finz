import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db, engine
from app.models.transaction import Transaction, AuditLog


# In-memory test SQLite engine for isolation
TEST_DB_URL = "sqlite:///:memory:"
test_engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)


@pytest.fixture(scope="module")
def client():
    Base.metadata.create_all(bind=test_engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=test_engine)


def test_complete_end_to_end_user_journey(client):
    """
    Executes the complete end-to-end evaluation journey:
    1. Reset database
    2. Ingest NYC Restaurant Co. 181 raw transactions
    3. Run batch categorization into Chart of Accounts
    4. Verify Review Queue flags low confidence & CapEx
    5. Perform manual audited category override
    6. Verify audit trail records override
    7. Generate deterministic monthly P&L
    8. Calculate month-over-month variances and driver transactions
    9. Query source-grounded AI Financial Analyst and verify citation chips
    """
    # 1. Reset Database
    reset_res = client.delete("/api/v1/transactions")
    assert reset_res.status_code == 200

    # 2. Ingest Real Challenge Dataset
    ingest_res = client.post("/api/v1/ingest/sample")
    assert ingest_res.status_code == 200
    ingest_data = ingest_res.json()
    assert ingest_data["inserted"] == 181

    # Verify transaction table stats
    stats_res = client.get("/api/v1/transactions/stats")
    assert stats_res.status_code == 200
    assert stats_res.json()["total_transactions"] == 181
    assert stats_res.json()["total_inflows"] > 0
    assert stats_res.json()["total_outflows"] < 0

    # 3. Execute Batch Categorization
    cat_res = client.post("/api/v1/categorize/batch?force=true")
    assert cat_res.status_code == 200
    cat_data = cat_res.json()
    assert cat_data["categorized_count"] == 181
    assert cat_data["flagged_for_review"] > 0

    # 4. Inspect Human Review Queue
    queue_res = client.get("/api/v1/review-queue")
    assert queue_res.status_code == 200
    queue_data = queue_res.json()
    assert queue_data["count"] > 0
    first_flagged = queue_data["items"][0]

    # 5. Perform Audited Manual Reclassification
    override_res = client.patch(
        f"/api/v1/transactions/{first_flagged['id']}/category",
        json={
            "category": "Operating Supplies & Office",
            "note": "Audited override during end-to-end evaluation",
        },
    )
    assert override_res.status_code == 200
    assert override_res.json()["transaction"]["category"] == "Operating Supplies & Office"

    # 6. Verify Permanent Audit Trail
    audit_res = client.get("/api/v1/audit-logs")
    assert audit_res.status_code == 200
    logs = audit_res.json()["logs"]
    assert len(logs) >= 1
    assert logs[0]["transaction_id"] == first_flagged["id"]
    assert logs[0]["new_category"] == "Operating Supplies & Office"

    # 7. Generate Deterministic Monthly P&L
    pnl_res = client.get("/api/v1/pnl")
    assert pnl_res.status_code == 200
    pnl_data = pnl_res.json()
    assert len(pnl_data["months"]) >= 2
    assert pnl_data["summary"]["total"]["revenue"] > 0
    assert pnl_data["summary"]["total"]["cogs"] > 0
    assert pnl_data["summary"]["total"]["gross_profit"] > 0
    assert pnl_data["summary"]["total"]["total_operating_expenses"] > 0

    # 8. Compute MoM Variances & Drivers
    var_res = client.get("/api/v1/variance?only_material=false")
    assert var_res.status_code == 200
    var_data = var_res.json()
    assert len(var_data["category_variances"]) > 0
    # Top variance must include driver transactions
    top_var = var_data["category_variances"][0]
    assert "explanation" in top_var
    assert len(top_var["drivers"]) > 0

    # 9. Query Source-Grounded AI Financial Analyst
    chat_res = client.post(
        "/api/v1/chat",
        json={"message": "What was our revenue in Jan 2026?"},
    )
    assert chat_res.status_code == 200
    chat_data = chat_res.json()
    assert "reply" in chat_data
    assert "citations" in chat_data
    assert len(chat_data["citations"]) > 0
    assert any(t in chat_data["tools_used"] for t in ["get_monthly_revenue", "get_monthly_pnl"])
