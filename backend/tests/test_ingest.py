import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.base import Base
from app.db.session import get_db
from decimal import Decimal
from app.services.ingest import parse_currency, parse_date_value, parse_csv_content

# In-memory SQLite for test isolation
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="module", autouse=True)
def init_test_db():
    Base.metadata.create_all(bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    Base.metadata.drop_all(bind=engine)


def test_parse_currency():
    assert parse_currency("-$4,151.25") == Decimal("-4151.25")
    assert parse_currency('"$17,513.84"') == Decimal("17513.84")
    assert parse_currency("-$875.00") == Decimal("-875.00")
    assert parse_currency("$750.84") == Decimal("750.84")
    assert parse_currency("($1,250.00)") == Decimal("-1250.00")
    assert parse_currency("0.00") == Decimal("0.00")
    assert parse_currency(None) == Decimal("0.00")


def test_parse_date_value():
    assert parse_date_value("2026-01-08") == date(2026, 1, 8)
    assert parse_date_value("01/08/2026") == date(2026, 1, 8)


def test_parse_csv_content():
    sample_csv = """Transaction ID,Date,Description,Counterparty,Amount,Method
T1051,2026-01-01,Rent,Landlord,"-$9,000.00",ACH
T1001,2026-01-08,POS batch deposit,Toast POS,"$17,513.84",Bank deposit
"""
    records = parse_csv_content(sample_csv)
    assert len(records) == 2
    assert records[0]["transaction_code"] == "T1051"
    assert records[0]["amount"] == Decimal("-9000.00")
    assert records[0]["counterparty"] == "Landlord"
    assert records[1]["transaction_code"] == "T1001"
    assert records[1]["amount"] == Decimal("17513.84")


def test_ingest_sample_dataset_and_queries():
    with TestClient(app) as client:
        # 1. Reset first
        del_resp = client.delete("/api/v1/transactions")
        assert del_resp.status_code == 200

        # 2. Ingest bundled sample dataset (NYC Restaurant Co.)
        resp = client.post("/api/v1/ingest/sample")
        assert resp.status_code == 200
        data = resp.json()
        assert data["inserted"] == 181
        assert data["total"] == 181

        # 3. Check stats
        stats_resp = client.get("/api/v1/transactions/stats")
        assert stats_resp.status_code == 200
        stats = stats_resp.json()
        assert stats["total_transactions"] == 181
        assert stats["total_inflows"] > 0
        assert stats["total_outflows"] < 0

        # 4. Query paginated list
        list_resp = client.get("/api/v1/transactions?limit=10&page=1")
        assert list_resp.status_code == 200
        list_data = list_resp.json()
        assert len(list_data["items"]) == 10
        assert list_data["total"] == 181
        assert list_data["pages"] == 19

        # 5. Search
        search_resp = client.get("/api/v1/transactions?search=Toast")
        assert search_resp.status_code == 200
        search_data = search_resp.json()
        assert search_data["total"] > 0
        for item in search_data["items"]:
            assert "toast" in item["description"].lower() or "toast" in (item["counterparty"] or "").lower()

        # 6. Sorting
        sort_resp = client.get("/api/v1/transactions?sort_by=amount&sort_dir=desc&limit=5")
        assert sort_resp.status_code == 200
        sort_items = sort_resp.json()["items"]
        assert sort_items[0]["amount"] >= sort_items[1]["amount"]
