import pytest
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.models.tenant import Tenant
from app.models.user import User
from app.models.transaction import Transaction, AuditLog
from app.core.security import hash_password, create_access_token
from app.ai.model_router import ModelRouter, TaskType
from app.ai.tools import execute_tool

# Isolated test DB
SQLALCHEMY_DATABASE_URL = "sqlite:///:memory:"
engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def test_db():
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


@pytest.fixture(scope="function")
def client(test_db):
    def override_get_db():
        try:
            yield test_db
        finally:
            pass

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def seeded_tenants(test_db):
    """Creates Tenant A, Tenant B, and users with ADMIN, ACCOUNTANT, VIEWER roles."""
    # Tenant A
    tenant_a = Tenant(name="Alpha Bistro", slug="alpha-bistro", plan="STARTER", status="active")
    # Tenant B
    tenant_b = Tenant(name="Beta Trattoria", slug="beta-trattoria", plan="PRO", status="active")
    test_db.add_all([tenant_a, tenant_b])
    test_db.commit()
    test_db.refresh(tenant_a)
    test_db.refresh(tenant_b)

    # Users for Tenant A
    admin_a = User(
        tenant_id=tenant_a.id,
        email="admin_a@alpha.com",
        name="Admin Alpha",
        password_hash=hash_password("Password123!"),
        role="ADMIN",
        is_active=True,
    )
    viewer_a = User(
        tenant_id=tenant_a.id,
        email="viewer_a@alpha.com",
        name="Viewer Alpha",
        password_hash=hash_password("Password123!"),
        role="VIEWER",
        is_active=True,
    )

    # User for Tenant B
    admin_b = User(
        tenant_id=tenant_b.id,
        email="admin_b@beta.com",
        name="Admin Beta",
        password_hash=hash_password("Password123!"),
        role="ADMIN",
        is_active=True,
    )
    test_db.add_all([admin_a, viewer_a, admin_b])
    test_db.commit()

    # Transactions for Tenant A: $10,000 revenue
    tx_a = Transaction(
        tenant_id=tenant_a.id,
        transaction_code="TX-ALPHA-01",
        date=date(2026, 1, 15),
        description="Toast POS Settlement Alpha",
        counterparty="Toast Inc",
        amount=10000.0,
        category="Food Sales",
        pnl_bucket="Revenue",
        confidence=0.98,
        review_status="confirmed",
        is_flagged_for_review=False,
    )

    # Transactions for Tenant B: $5,000 revenue
    tx_b = Transaction(
        tenant_id=tenant_b.id,
        transaction_code="TX-BETA-01",
        date=date(2026, 1, 20),
        description="Toast POS Settlement Beta",
        counterparty="Toast Inc",
        amount=5000.0,
        category="Food Sales",
        pnl_bucket="Revenue",
        confidence=0.98,
        review_status="confirmed",
        is_flagged_for_review=False,
    )

    test_db.add_all([tx_a, tx_b])
    test_db.commit()
    test_db.refresh(tx_a)
    test_db.refresh(tx_b)

    return {
        "tenant_a": tenant_a,
        "tenant_b": tenant_b,
        "admin_a": admin_a,
        "viewer_a": viewer_a,
        "admin_b": admin_b,
        "tx_a": tx_a,
        "tx_b": tx_b,
    }


# ==============================================================================
# 1. TENANT ISOLATION TESTS
# ==============================================================================

def test_tenant_isolation_transactions(client, seeded_tenants):
    """Tenant B cannot see Tenant A's transactions."""
    token_b = create_access_token(seeded_tenants["admin_b"].id, seeded_tenants["admin_b"].email, role="ADMIN")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    res = client.get("/api/v1/transactions", headers=headers_b)
    assert res.status_code == 200
    data = res.json()
    assert data["total"] == 1
    assert data["items"][0]["transaction_code"] == "TX-BETA-01"
    assert all(t["transaction_code"] != "TX-ALPHA-01" for t in data["items"])


def test_tenant_isolation_pnl(client, seeded_tenants):
    """Tenant B's P&L calculation only includes Tenant B transactions."""
    token_b = create_access_token(seeded_tenants["admin_b"].id, seeded_tenants["admin_b"].email, role="ADMIN")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    res = client.get("/api/v1/pnl", headers=headers_b)
    assert res.status_code == 200
    pnl = res.json()
    total_rev = pnl["summary"]["total"]["revenue"]
    assert total_rev == 5000.0  # Only Tenant B's $5,000, never Tenant A's $10,000


def test_tenant_isolation_traceability(client, seeded_tenants):
    """Tenant B's traceability drawer sees only Tenant B underlying evidence."""
    token_b = create_access_token(seeded_tenants["admin_b"].id, seeded_tenants["admin_b"].email, role="ADMIN")
    headers_b = {"Authorization": f"Bearer {token_b}"}

    res = client.get("/api/v1/traceability/revenue", headers=headers_b)
    assert res.status_code == 200
    data = res.json()
    assert data["transaction_count"] == 1
    assert data["transactions"][0]["transaction_code"] == "TX-BETA-01"


# ==============================================================================
# 2. RBAC TESTS
# ==============================================================================

def test_rbac_viewer_forbidden_from_modifications(client, seeded_tenants):
    """Viewer role cannot modify transaction category or confirm classifications."""
    token_viewer = create_access_token(seeded_tenants["viewer_a"].id, seeded_tenants["viewer_a"].email, role="VIEWER")
    headers_viewer = {"Authorization": f"Bearer {token_viewer}"}

    # Attempt category modification
    res = client.patch(
        f"/api/v1/transactions/{seeded_tenants['tx_a'].id}/category",
        json={"category": "Beverage Sales"},
        headers=headers_viewer,
    )
    assert res.status_code == 403
    assert "Access forbidden" in res.json()["detail"]

    # Attempt review confirmation
    res_confirm = client.post(
        f"/api/v1/transactions/{seeded_tenants['tx_a'].id}/confirm",
        headers=headers_viewer,
    )
    assert res_confirm.status_code == 403


def test_rbac_admin_allowed_modifications(client, seeded_tenants):
    """Admin role can modify transaction category and logs immutable audit trail."""
    token_admin = create_access_token(seeded_tenants["admin_a"].id, seeded_tenants["admin_a"].email, role="ADMIN")
    headers_admin = {"Authorization": f"Bearer {token_admin}"}

    res = client.patch(
        f"/api/v1/transactions/{seeded_tenants['tx_a'].id}/category",
        json={"category": "Beverage Sales", "note": "Classified by head accountant"},
        headers=headers_admin,
    )
    assert res.status_code == 200
    assert res.json()["transaction"]["category"] == "Beverage Sales"

    # Verify audit log was created with tenant_id and user_id
    audit_res = client.get("/api/v1/audit-logs", headers=headers_admin)
    assert audit_res.status_code == 200
    logs = audit_res.json()["logs"]
    assert len(logs) >= 1
    assert logs[0]["new_category"] == "Beverage Sales"


# ==============================================================================
# 3. AI CACHING & TOOL TENANT ISOLATION
# ==============================================================================

def test_ai_cache_isolation_between_tenants():
    """Identical query by Tenant A and Tenant B must produce distinct cache keys."""
    router = ModelRouter()
    query = "What was our revenue in January 2026?"

    key_a = router._generate_cache_key(tenant_id=1, query=query)
    key_b = router._generate_cache_key(tenant_id=2, query=query)

    assert key_a != key_b
    assert key_a.startswith("ai_cache:1:")
    assert key_b.startswith("ai_cache:2:")

    # Store cache for Tenant A
    router.set_cached_response(tenant_id=1, query=query, response_data={"answer": "Tenant A Revenue: $10,000"})

    # Query for Tenant B must return None
    cached_b = router.get_cached_response(tenant_id=2, query=query)
    assert cached_b is None

    # Query for Tenant A must return Tenant A's cached response
    cached_a = router.get_cached_response(tenant_id=1, query=query)
    assert cached_a is not None
    assert cached_a["answer"] == "Tenant A Revenue: $10,000"


def test_ai_tool_tenant_spoofing_defense(test_db, seeded_tenants):
    """
    LLM tool calling cannot override server-provided tenant_id.
    Even if LLM passes tenant_id=999, server context enforces active tenant.
    """
    tenant_a_id = seeded_tenants["tenant_a"].id
    # Malicious or hallucinated args from LLM attempting to pass another tenant
    malicious_args = {"month": "2026-01", "tenant_id": 999}

    result = execute_tool(
        tool_name="get_monthly_pnl",
        arguments=malicious_args,
        db=test_db,
        tenant_id=tenant_a_id,  # Server-provided context
    )

    # Returns Tenant A's $10,000, not error or tenant 999
    assert result.get("revenue") == 10000.0


# ==============================================================================
# 4. PUBLIC DEMO SUMMARY (NO LEAKAGE)
# ==============================================================================

def test_public_demo_summary_unauthenticated(client, seeded_tenants):
    """Public endpoint returns sanitized demo data and requires zero authentication."""
    res = client.get("/api/v1/public/demo-summary")
    assert res.status_code == 200
    data = res.json()
    assert data["mode"] == "sample"
    assert "transactions_analyzed" in data
    assert "review_period" in data
    assert "revenue" in data
    assert "gross_profit" in data
    assert "operating_profit" in data
    assert "workspace_label" in data
