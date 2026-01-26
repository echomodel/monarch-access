"""Live read-only integration tests for Monarch API.

These tests make real API calls and require valid credentials.
They are automatically skipped if no token is configured.

To run:
    pytest tests/integration/
"""

import pytest

from monarch.config import get_token
from monarch.client import MonarchClient


# Skip all tests in this module if no token is available
pytestmark = pytest.mark.skipif(
    get_token() is None,
    reason="No Monarch token configured (set MONARCH_TOKEN or create ~/.config/monarch/token)"
)


@pytest.fixture
def client():
    """Create a MonarchClient for live API calls."""
    return MonarchClient()


class TestLiveReads:
    """Read-only tests against the live Monarch API."""

    @pytest.mark.asyncio
    async def test_list_accounts(self, client):
        """Verify we can fetch accounts from the live API."""
        from monarch.mcp.server import get_accounts

        accounts = await get_accounts(client)

        assert isinstance(accounts, list)
        assert len(accounts) > 0, "Expected at least one account"

        # Verify account structure
        account = accounts[0]
        assert "id" in account
        assert "displayName" in account

    @pytest.mark.asyncio
    async def test_list_categories(self, client):
        """Verify we can fetch categories from the live API."""
        from monarch.mcp.server import get_categories

        categories = await get_categories(client)

        assert isinstance(categories, list)
        assert len(categories) > 0, "Expected at least one category"

        # Verify category structure
        category = categories[0]
        assert "id" in category
        assert "name" in category

    @pytest.mark.asyncio
    async def test_list_transactions(self, client):
        """Verify we can fetch transactions from the live API."""
        from datetime import date, timedelta
        from monarch.mcp.server import get_transactions

        # Only fetch last 7 days, limit 3
        end = date.today()
        start = end - timedelta(days=7)

        result = await get_transactions(
            client,
            limit=3,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )

        assert isinstance(result, dict)
        assert "results" in result
        assert "totalCount" in result

        transactions = result["results"]
        assert isinstance(transactions, list)
        assert len(transactions) <= 3
