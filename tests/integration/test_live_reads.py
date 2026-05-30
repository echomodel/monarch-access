"""Live read-only integration tests for the Monarch API.

These tests make real API calls and require valid credentials. They are
automatically skipped if no token is configured.

They call the SDK modules directly (the same code paths the CLI and MCP tools
use), so they verify the real GraphQL/REST round-trips end-to-end. Everything
here is read-only — no mutations against the live account.

To run:
    pytest tests/integration/
"""

import pytest

from monarch.client import MonarchClient


def _has_token() -> bool:
    """Check if a Monarch token is available in the mcp-app local user store."""
    try:
        from monarch.providers.api.provider import _load_token
        _load_token()
        return True
    except Exception:
        return False


# Skip all tests in this module if no token is available
pytestmark = pytest.mark.skipif(
    not _has_token(),
    reason="No Monarch token configured (run: monarch-admin connect local && monarch-admin users add local --token TOKEN)"
)


@pytest.fixture
def client():
    """Create a MonarchClient for live API calls."""
    from monarch.providers.api.provider import _load_token
    return MonarchClient(token=_load_token())


class TestLiveReads:
    """Read-only tests against the live Monarch API."""

    @pytest.mark.asyncio
    async def test_list_accounts(self, client):
        """Fetch accounts from the live API."""
        from monarch import accounts

        accts = await accounts.get_accounts(client)

        assert isinstance(accts, list)
        assert len(accts) > 0, "Expected at least one account"
        account = accts[0]
        assert "id" in account
        assert "displayName" in account

    @pytest.mark.asyncio
    async def test_list_categories(self, client):
        """Fetch categories from the live API."""
        from monarch import categories

        cats = await categories.get_categories(client)

        assert isinstance(cats, list)
        assert len(cats) > 0, "Expected at least one category"
        category = cats[0]
        assert "id" in category
        assert "name" in category

    @pytest.mark.asyncio
    async def test_list_transactions(self, client):
        """Fetch a small window of transactions from the live API."""
        from datetime import date, timedelta
        from monarch.transactions import list as txn_list

        end = date.today()
        start = end - timedelta(days=7)

        result = await txn_list.get_transactions(
            client,
            limit=3,
            start_date=start.isoformat(),
            end_date=end.isoformat(),
        )

        assert isinstance(result, dict)
        assert "results" in result
        assert "totalCount" in result
        assert isinstance(result["results"], list)
        assert len(result["results"]) <= 3

    @pytest.mark.asyncio
    async def test_get_holdings(self, client):
        """Fetch investment holdings from the live API (Web_GetHoldings)."""
        from monarch import holdings

        items = await holdings.get_holdings(client)

        assert isinstance(items, list)
        # Holdings may legitimately be empty (no investment accounts), but when
        # present each item must carry the normalized fields.
        for h in items:
            assert "ticker" in h
            assert "quantity" in h
            assert "cost_basis" in h
            assert "tax_lots" in h
            assert isinstance(h["tax_lots"], list)

    @pytest.mark.asyncio
    async def test_download_balance_history(self, client):
        """Download an account's balance history and derive its token (REST)."""
        from monarch import accounts, balances

        accts = await accounts.get_accounts(client)
        assert accts, "Expected at least one account"
        account_id = accts[0]["id"]

        snapshots = await balances.download_balance_history(client, account_id)
        assert isinstance(snapshots, list)
        for s in snapshots[:5]:
            assert "date" in s
            assert "balance" in s

        # The read-before-write token is derivable from the downloaded history
        # and is stable for the same content.
        token = balances.history_token(snapshots)
        assert isinstance(token, int)
        assert balances.history_token(snapshots) == token
