import os
import json
import pytest
from unittest.mock import MagicMock, patch
from datetime import date
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
import openai

from app.main import app
from app.db.base import Base
from app.db.session import get_db
from app.core.config import settings, Settings
from app.core.security import create_access_token
from app.models.user import User
from app.models.transaction import Transaction
from app.ai.deepseek_client import DeepSeekClient, DeepSeekClientError
from app.ai.tools import (
    ALLOWED_TOOLS,
    FINANCIAL_TOOLS_SCHEMA,
    execute_tool,
    get_monthly_pnl,
    compare_months,
    get_variance_drivers,
    get_review_items,
)
from app.ai.analyst import FinancialAIAnalyst, SYSTEM_PROMPT

# Test SQLite Engine
TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False}, poolclass=StaticPool)
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


@pytest.fixture(scope="function")
def auth_headers(db_session):
    user = User(
        name="Analyst Tester",
        email="analyst@finreview.test",
        password_hash="argon2hash",
        role="USER",
        is_active=True,
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)

    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return {"Authorization": f"Bearer {token}"}


def seed_test_transactions(db):
    txns = [
        Transaction(transaction_code="T-101", date=date(2026, 1, 15), description="POS Sales", counterparty="Toast", amount=40000.0, category="Food Sales", pnl_bucket="Revenue"),
        Transaction(transaction_code="T-102", date=date(2026, 1, 16), description="Food Delivery", counterparty="Sysco", amount=-15000.0, category="Food Inventory / Supplies", pnl_bucket="COGS"),
        Transaction(transaction_code="T-103", date=date(2026, 1, 20), description="Oven Repair", counterparty="RepairCo", amount=-2500.0, category="Repairs & Maintenance", pnl_bucket="OpEx", is_flagged_for_review=True, rationale="High repair variance"),
        Transaction(transaction_code="T-201", date=date(2026, 2, 15), description="POS Sales", counterparty="Toast", amount=55000.0, category="Food Sales", pnl_bucket="Revenue"),
        Transaction(transaction_code="T-202", date=date(2026, 2, 16), description="Food Delivery", counterparty="Sysco", amount=-20000.0, category="Food Inventory / Supplies", pnl_bucket="COGS"),
    ]
    db.add_all(txns)
    db.commit()


# ==============================================================================
# 1. CONFIGURATION TESTS
# ==============================================================================

def test_deepseek_configuration_loaded():
    assert settings.DEEPSEEK_BASE_URL == "https://api.deepseek.com"
    assert settings.DEEPSEEK_MODEL == "deepseek-flash"
    assert settings.deepseek_model == "deepseek-flash"
    assert settings.deepseek_base_url == "https://api.deepseek.com"


def test_missing_api_key_client_behavior():
    client = DeepSeekClient(api_key="")
    assert not client.is_configured
    health = client.health_check()
    assert health["configured"] is False
    assert health["available"] is False

    with pytest.raises(DeepSeekClientError) as exc_info:
        client.chat(messages=[{"role": "user", "content": "Hello"}])
    assert exc_info.value.status_code == 503
    assert "not configured" in exc_info.value.message


def test_client_initialization_with_key():
    client = DeepSeekClient(api_key="mock-deepseek-key-123", model="deepseek-flash")
    assert client.is_configured
    assert client.model == "deepseek-flash"


# ==============================================================================
# 2. PROVIDER ERROR HANDLING (MOCKED)
# ==============================================================================

def test_chat_successful_response_mocked():
    client = DeepSeekClient(api_key="mock-key")
    mock_resp = MagicMock()
    mock_resp.choices = [
        MagicMock(message=MagicMock(content="Revenue in January was $40,000.00.", tool_calls=None))
    ]

    with patch.object(client._client.chat.completions, "create", return_value=mock_resp):
        res = client.chat(messages=[{"role": "user", "content": "What was revenue?"}])
        assert res.choices[0].message.content == "Revenue in January was $40,000.00."


def test_chat_provider_402_balance_error_handled():
    client = DeepSeekClient(api_key="mock-key")
    mock_response = MagicMock(status_code=402, headers={})
    api_err = openai.APIStatusError(
        message="Insufficient Balance",
        response=mock_response,
        body={"error": {"message": "Insufficient Balance"}},
    )

    with patch.object(client._client.chat.completions, "create", side_effect=api_err):
        with pytest.raises(DeepSeekClientError) as exc:
            client.chat(messages=[{"role": "user", "content": "Hello"}])
        assert exc.value.status_code == 402
        assert "insufficient" in exc.value.message.lower()


def test_chat_timeout_error_handled():
    client = DeepSeekClient(api_key="mock-key")
    timeout_err = openai.APITimeoutError(request=MagicMock())

    with patch.object(client._client.chat.completions, "create", side_effect=timeout_err):
        with pytest.raises(DeepSeekClientError) as exc:
            client.chat(messages=[{"role": "user", "content": "Hello"}])
        assert exc.value.status_code == 504
        assert exc.value.is_retryable is True


# ==============================================================================
# 3. FINANCIAL TOOL VALIDATION & EXECUTION TESTS
# ==============================================================================

def test_invalid_tool_call_rejected(db_session):
    res = execute_tool(db_session, "drop_all_tables", {"sql": "DROP TABLE users;"})
    assert "error" in res
    assert "not an authorized financial tool" in res["error"]


def test_valid_financial_tool_get_monthly_pnl(db_session):
    seed_test_transactions(db_session)
    res = execute_tool(db_session, "get_monthly_pnl", {"month": "2026-01"})
    assert "error" not in res
    assert res["month"] == "2026-01"
    assert res["revenue"] == 40000.0
    assert res["cogs"] == 15000.0
    assert res["gross_profit"] == 25000.0


def test_valid_financial_tool_compare_months(db_session):
    seed_test_transactions(db_session)
    res = execute_tool(db_session, "compare_months", {"month_a": "2026-01", "month_b": "2026-02"})
    assert "error" not in res
    assert res["baseline_month"] == "2026-01"
    assert res["current_month"] == "2026-02"
    assert len(res["summary_variances"]) > 0


def test_valid_financial_tool_get_review_items(db_session):
    seed_test_transactions(db_session)
    res = execute_tool(db_session, "get_review_items", {"limit": 5})
    assert res["count"] == 1
    assert res["review_items"][0]["transaction_code"] == "T-103"
    assert "Oven Repair" in res["review_items"][0]["description"]


def test_no_financial_total_generated_directly_by_ai():
    # Strict verification that system prompt enforces backend tools as single source of truth
    assert "Never invent financial numbers" in SYSTEM_PROMPT
    assert "Never calculate authoritative financial totals yourself" in SYSTEM_PROMPT
    assert "Use backend tool results as the source of truth" in SYSTEM_PROMPT
    assert "Never execute SQL directly" in SYSTEM_PROMPT


# ==============================================================================
# 4. AI ANALYST SERVICE & TOOL CALLING WORKFLOW
# ==============================================================================

def test_analyst_tool_calling_loop_mocked(db_session):
    seed_test_transactions(db_session)
    client_mock = MagicMock(spec=DeepSeekClient)
    client_mock.is_configured = True

    # 1. Turn 1: Model calls tool get_monthly_pnl
    tool_call_obj = MagicMock()
    tool_call_obj.id = "call_abc123"
    tool_call_obj.function.name = "get_monthly_pnl"
    tool_call_obj.function.arguments = json.dumps({"month": "2026-01"})

    turn1_msg = MagicMock(tool_calls=[tool_call_obj], content=None)
    turn1_resp = MagicMock(choices=[MagicMock(message=turn1_msg)])

    # 2. Turn 2: Model synthesizes tool output into final explanation
    turn2_msg = MagicMock(
        tool_calls=None,
        content="In January 2026, total revenue was $40,000.00 with COGS of $15,000.00, yielding a gross profit of $25,000.00."
    )
    turn2_resp = MagicMock(choices=[MagicMock(message=turn2_msg)])

    client_mock.chat.side_effect = [turn1_resp, turn2_resp]

    analyst = FinancialAIAnalyst(client=client_mock)
    result = analyst.process_query(db_session, "What was our revenue and profit in Jan 2026?")

    assert "get_monthly_pnl" in result["tools_used"]
    assert "40,000.00" in result["reply"]
    assert client_mock.chat.call_count == 2


def test_analyst_fallback_when_client_unconfigured(db_session):
    seed_test_transactions(db_session)
    client_mock = MagicMock(spec=DeepSeekClient)
    client_mock.is_configured = False

    analyst = FinancialAIAnalyst(client=client_mock)
    result = analyst.process_query(db_session, "What was our revenue in Jan 2026?")

    # Fallback delivers authoritative database calculation
    assert "Food Sales" in result["reply"]
    assert len(result["citations"]) > 0


# ==============================================================================
# 5. ENDPOINT SECURITY & HEALTH TESTS
# ==============================================================================

def test_ai_health_endpoint_authenticated(client, auth_headers):
    resp = client.get("/api/v1/ai/health", headers=auth_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] in ("ollama", "deepseek")
    assert "configured" in data
    assert "available" in data
    assert "model" in data
    # Ensure no secret API key is in the response payload
    assert "api_key" not in data
    assert "key" not in data


def test_ai_health_endpoint_unauthorized(client):
    # Missing Bearer token
    resp = client.get("/api/v1/ai/health")
    assert resp.status_code == 401


def test_chat_endpoint_unauthorized(client):
    resp = client.post("/api/v1/chat", json={"message": "What was our revenue?"})
    assert resp.status_code == 401


def test_chat_endpoint_empty_message_rejected(client, auth_headers):
    resp = client.post("/api/v1/chat", json={"message": "   "}, headers=auth_headers)
    assert resp.status_code == 400
    assert "cannot be empty" in resp.json()["detail"].lower()


# ==============================================================================
# 6. OPTIONAL LIVE INTEGRATION TEST (RUN_DEEPSEEK_INTEGRATION_TEST)
# ==============================================================================

def test_deepseek_live_integration():
    """
    Live test against DeepSeek API service.
    Only executed when RUN_DEEPSEEK_INTEGRATION_TEST=true.
    Never prints or logs the actual API secret.
    """
    enabled = os.getenv("RUN_DEEPSEEK_INTEGRATION_TEST", "false").lower() == "true"
    if not enabled:
        pytest.skip("Live DeepSeek integration test skipped (enable via RUN_DEEPSEEK_INTEGRATION_TEST=true)")

    real_client = DeepSeekClient()
    if not real_client.is_configured:
        pytest.skip("DeepSeek API key is not configured in environment.")

    health = real_client.health_check()
    assert health["provider"] == "deepseek"
    assert health["configured"] is True
