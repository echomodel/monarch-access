"""Tests for investment holdings operations.

These tests double as executable documentation of the Web_GetHoldings
response shape and the normalization applied to it.
"""

from monarch.holdings import normalize_holding, normalize_portfolio


class TestGetHoldings:
    """Holdings retrieval via the local provider."""

    def test_whole_portfolio_returns_all_current_holdings(self, local_provider):
        """No account filter returns the current snapshot across all accounts."""
        holdings = local_provider.get_holdings()
        tickers = {h["ticker"] for h in holdings}
        assert tickers == {"AAPL", "BTC", "VFIAX"}

    def test_single_account_filter(self, local_provider):
        """account_ids narrows holdings to that account."""
        holdings = local_provider.get_holdings(account_ids=["acc_011"])
        assert len(holdings) == 1
        assert holdings[0]["ticker"] == "VFIAX"

    def test_filter_excludes_other_accounts(self, local_provider):
        """Brokerage account returns its securities, not the 401k's."""
        holdings = local_provider.get_holdings(account_ids=["acc_009"])
        tickers = {h["ticker"] for h in holdings}
        assert tickers == {"AAPL", "BTC"}

    def test_holding_has_expected_fields(self, local_provider):
        """Normalized holdings expose the documented model."""
        holdings = local_provider.get_holdings(account_ids=["acc_011"])
        h = holdings[0]
        for field in [
            "ticker", "name", "quantity", "closing_price", "current_value",
            "cost_basis", "is_manual", "tax_lots",
        ]:
            assert field in h, f"Missing field: {field}"

    def test_populated_tax_lots(self, local_provider):
        """A security with multiple acquisition lots surfaces each lot."""
        holdings = local_provider.get_holdings(account_ids=["acc_009"])
        aapl = next(h for h in holdings if h["ticker"] == "AAPL")
        assert len(aapl["tax_lots"]) == 2
        assert aapl["tax_lots"][0] == {"acquisition_quantity": 30, "cost_basis_per_unit": 140.00}
        assert aapl["tax_lots"][1] == {"acquisition_quantity": 20, "cost_basis_per_unit": 165.00}
        assert aapl["cost_basis"] == 7500.00
        assert aapl["quantity"] == 50

    def test_null_cost_basis_synced_position(self, local_provider):
        """A synced position without provider-supplied basis returns null cost_basis."""
        holdings = local_provider.get_holdings(account_ids=["acc_009"])
        btc = next(h for h in holdings if h["ticker"] == "BTC")
        assert btc["cost_basis"] is None
        assert btc["tax_lots"] == []
        assert btc["current_value"] == 32000.00

    def test_manual_holding_flagged(self, local_provider):
        """A manual lot marks the aggregate holding is_manual."""
        holdings = local_provider.get_holdings(account_ids=["acc_011"])
        assert holdings[0]["is_manual"] is True

    def test_synced_holding_not_manual(self, local_provider):
        """A synced lot leaves is_manual false."""
        holdings = local_provider.get_holdings(account_ids=["acc_009"])
        aapl = next(h for h in holdings if h["ticker"] == "AAPL")
        assert aapl["is_manual"] is False

    def test_as_of_date_historical_snapshot(self, local_provider):
        """as_of_date returns that date's snapshot, which differs from current."""
        historical = local_provider.get_holdings(
            account_ids=["acc_009"], as_of_date="2025-01-15"
        )
        # Only AAPL existed in the historical snapshot, at a lower quantity.
        assert len(historical) == 1
        aapl = historical[0]
        assert aapl["ticker"] == "AAPL"
        assert aapl["quantity"] == 30
        assert aapl["cost_basis"] == 4200.00

        # Current snapshot for the same account is different.
        current = local_provider.get_holdings(account_ids=["acc_009"])
        current_aapl = next(h for h in current if h["ticker"] == "AAPL")
        assert current_aapl["quantity"] == 50

    def test_unknown_date_returns_empty(self, local_provider):
        """A date with no snapshot returns no holdings."""
        assert local_provider.get_holdings(as_of_date="2000-01-01") == []


class TestNormalizeHolding:
    """Direct tests of the normalization that runs on raw API nodes."""

    def test_normalize_flattens_security_and_aggregate(self):
        node = {
            "id": "agg_x",
            "quantity": 10,
            "costBasis": 1000.0,
            "totalValue": 1500.0,
            "securityPriceChangeDollars": 5.0,
            "securityPriceChangePercent": 0.33,
            "lastSyncedAt": "2026-05-29T10:00:00Z",
            "holdings": [
                {
                    "isManual": False,
                    "taxLots": [
                        {"acquisitionQuantity": 10, "costBasisPerUnit": 100.0},
                    ],
                }
            ],
            "security": {
                "ticker": "XYZ",
                "name": "Example Corp",
                "typeDisplay": "Equity",
                "currentPrice": 151.0,
                "closingPrice": 150.0,
            },
        }
        h = normalize_holding(node)
        assert h["ticker"] == "XYZ"
        assert h["name"] == "Example Corp"
        assert h["type"] == "Equity"
        assert h["quantity"] == 10
        assert h["current_value"] == 1500.0
        assert h["cost_basis"] == 1000.0
        assert h["closing_price"] == 150.0
        assert h["current_price"] == 151.0
        assert h["tax_lots"] == [{"acquisition_quantity": 10, "cost_basis_per_unit": 100.0}]

    def test_normalize_handles_missing_security_and_holdings(self):
        """A bare node doesn't crash normalization."""
        h = normalize_holding({"id": "agg_y", "quantity": 0})
        assert h["ticker"] is None
        assert h["tax_lots"] == []
        assert h["is_manual"] is False

    def test_normalize_portfolio_unwraps_edges(self):
        data = {
            "portfolio": {
                "aggregateHoldings": {
                    "edges": [
                        {"node": {"id": "a", "security": {"ticker": "A"}}},
                        {"node": {"id": "b", "security": {"ticker": "B"}}},
                    ]
                }
            }
        }
        holdings = normalize_portfolio(data)
        assert [h["ticker"] for h in holdings] == ["A", "B"]

    def test_normalize_portfolio_empty(self):
        assert normalize_portfolio({}) == []
