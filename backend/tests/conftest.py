import pytest
from app.api.deps import get_current_user
from app.models.user import User
from app.main import app


@pytest.fixture(autouse=True)
def auto_auth_for_legacy_tests(request):
    """
    Ensures existing financial/variance/P&L tests run seamlessly by providing
    an authenticated context, while keeping test_auth.py purely unmocked for
    rigorous real-world security testing.
    """
    if "test_auth" in request.node.nodeid or "test_deepseek_ai" in request.node.nodeid or "test_saas_multi_tenancy" in request.node.nodeid:
        yield
        return

    mock_user = User(
        id=999,
        email="test_analyst@finreview.internal",
        name="Test Financial Analyst",
        role="ADMIN",
        is_active=True,
    )
    app.dependency_overrides[get_current_user] = lambda: mock_user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_current_user, None)
