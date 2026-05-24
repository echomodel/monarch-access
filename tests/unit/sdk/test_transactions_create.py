"""Tests for transactions create operations.

The SDK exposes a plural-only create_transactions that takes a list of input
dicts and returns a per-item result envelope (created[], failed[], counts).
"""

import pytest


class TestTransactionsCreate:
    """Test creating transactions via the plural API."""

    def _input(self, account_id, category_id, **overrides):
        item = {
            "date": "2026-01-15",
            "account_id": account_id,
            "amount": -100.50,
            "merchant_name": "Test Merchant",
            "category_id": category_id,
            "notes": "Test transaction notes",
        }
        item.update(overrides)
        return item

    def test_create_single_basic(self, local_provider):
        """Creating one transaction returns success envelope with the new row."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()

        assert len(accounts) > 0
        assert len(categories) > 0

        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]
        item = self._input(account_id, category_id)

        result = local_provider.create_transactions([item])

        assert result["success"] is True
        assert result["success_count"] == 1
        assert result["failure_count"] == 0
        assert result["failed"] == []
        assert len(result["created"]) == 1

        entry = result["created"][0]
        assert entry["index"] == 0
        assert entry["input"] == item
        txn = entry["transaction"]
        assert txn["id"] is not None
        assert txn["amount"] == -100.50
        assert txn["date"] == "2026-01-15"
        assert txn["notes"] == "Test transaction notes"
        assert txn["merchant"]["name"] == "Test Merchant"
        assert txn["account"]["id"] == account_id
        assert txn["category"]["id"] == category_id

    def test_create_can_be_retrieved(self, local_provider):
        """A created transaction is retrievable by ID."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        result = local_provider.create_transactions([
            self._input(account_id, category_id, date="2026-02-01",
                        amount=-50.00, merchant_name="Retrievable Merchant"),
        ])

        created_id = result["created"][0]["transaction"]["id"]
        fetched = local_provider.get_transaction(created_id)
        assert fetched is not None
        assert fetched["amount"] == -50.00
        assert fetched["merchant"]["name"] == "Retrievable Merchant"

    def test_create_appears_in_list(self, local_provider):
        """Created transaction is reflected in subsequent list queries."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        initial = local_provider.get_transactions(limit=1000)["totalCount"]

        result = local_provider.create_transactions([
            self._input(account_id, category_id, date="2026-03-01",
                        amount=-75.00, merchant_name="List Test Merchant"),
        ])
        created_id = result["created"][0]["transaction"]["id"]

        after = local_provider.get_transactions(limit=1000)
        assert after["totalCount"] == initial + 1
        assert created_id in [t["id"] for t in after["results"]]

    def test_create_positive_amount(self, local_provider):
        """Positive amounts (income) round-trip correctly."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        result = local_provider.create_transactions([
            self._input(account_id, category_id, date="2026-04-01",
                        amount=500.00, merchant_name="Income Source",
                        notes="Income transaction"),
        ])
        assert result["created"][0]["transaction"]["amount"] == 500.00

    def test_create_rounds_amount(self, local_provider):
        """Amount is rounded to 2 decimal places."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        result = local_provider.create_transactions([
            self._input(account_id, category_id, date="2026-05-01",
                        amount=-99.999, merchant_name="Rounding Test"),
        ])
        assert result["created"][0]["transaction"]["amount"] == -100.00

    def test_create_empty_notes(self, local_provider):
        """Empty-string notes are preserved (not coerced to None)."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        result = local_provider.create_transactions([
            self._input(account_id, category_id, date="2026-08-01",
                        amount=-25.00, merchant_name="No Notes Merchant",
                        notes=""),
        ])
        assert result["created"][0]["transaction"]["notes"] == ""

    def test_create_default_fields(self, local_provider):
        """Defaults for manually-created transactions match live API behavior."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        result = local_provider.create_transactions([
            self._input(account_id, category_id, date="2026-09-01",
                        amount=-10.00, merchant_name="Defaults Test",
                        notes=None),
        ])
        txn = result["created"][0]["transaction"]
        assert txn["pending"] is False
        assert txn["hideFromReports"] is False
        assert txn["needsReview"] is False
        assert txn["isSplitTransaction"] is False
        assert txn["tags"] == []

    def test_create_invalid_account_reported_per_item(self, local_provider):
        """Invalid account is reported in failed[] without raising."""
        categories = local_provider.get_categories()
        category_id = categories[0]["id"]

        result = local_provider.create_transactions([
            self._input("nonexistent_account_id", category_id, date="2026-06-01",
                        amount=-50.00, merchant_name="Bad Account"),
        ])

        assert result["success"] is False
        assert result["success_count"] == 0
        assert result["failure_count"] == 1
        assert result["created"] == []
        assert len(result["failed"]) == 1
        failure = result["failed"][0]
        assert failure["index"] == 0
        assert "Account not found" in failure["error"]
        assert failure["input"]["account_id"] == "nonexistent_account_id"

    def test_create_invalid_category_reported_per_item(self, local_provider):
        """Invalid category is reported in failed[] without raising."""
        accounts = local_provider.get_accounts()
        account_id = accounts[0]["id"]

        result = local_provider.create_transactions([
            self._input(account_id, "nonexistent_category_id", date="2026-07-01",
                        amount=-50.00, merchant_name="Bad Category"),
        ])

        assert result["success"] is False
        assert result["failure_count"] == 1
        assert "Category not found" in result["failed"][0]["error"]

    def test_create_missing_required_field_reported_per_item(self, local_provider):
        """Missing required input field is reported per-item, not raised."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        # missing "merchant_name"
        bad_item = {
            "date": "2026-10-01",
            "account_id": account_id,
            "amount": -1.00,
            "category_id": category_id,
        }
        result = local_provider.create_transactions([bad_item])

        assert result["success"] is False
        assert result["failure_count"] == 1
        assert result["failed"][0]["index"] == 0
        # KeyError repr surfaces the missing key
        assert "merchant_name" in result["failed"][0]["error"]

    def test_create_multiple_all_succeed(self, local_provider):
        """Bulk create of N valid inputs returns N created and 0 failed."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        items = [
            self._input(account_id, category_id, amount=-1.00, merchant_name="A"),
            self._input(account_id, category_id, amount=-2.00, merchant_name="B"),
            self._input(account_id, category_id, amount=-3.00, merchant_name="C"),
        ]
        result = local_provider.create_transactions(items)

        assert result["success"] is True
        assert result["success_count"] == 3
        assert result["failure_count"] == 0
        assert [e["index"] for e in result["created"]] == [0, 1, 2]
        assert [e["transaction"]["merchant"]["name"] for e in result["created"]] == ["A", "B", "C"]

    def test_create_multiple_mixed_partial_success(self, local_provider):
        """Mixed batch: successes and failures are reported independently with original positions."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        items = [
            self._input(account_id, category_id, amount=-10.00, merchant_name="Good 1"),
            self._input("bad-account", category_id, amount=-20.00, merchant_name="Bad acct"),
            self._input(account_id, category_id, amount=-30.00, merchant_name="Good 2"),
            self._input(account_id, "bad-category", amount=-40.00, merchant_name="Bad cat"),
        ]
        result = local_provider.create_transactions(items)

        assert result["success"] is False
        assert result["success_count"] == 2
        assert result["failure_count"] == 2
        assert [e["index"] for e in result["created"]] == [0, 2]
        assert [e["transaction"]["merchant"]["name"] for e in result["created"]] == ["Good 1", "Good 2"]
        assert [f["index"] for f in result["failed"]] == [1, 3]
        assert "Account not found" in result["failed"][0]["error"]
        assert "Category not found" in result["failed"][1]["error"]
        # Echoed inputs let the caller correlate failures back to source.
        assert result["failed"][0]["input"]["merchant_name"] == "Bad acct"
        assert result["failed"][1]["input"]["merchant_name"] == "Bad cat"

    def test_create_multiple_all_fail(self, local_provider):
        """All-failure batch: success_count is 0, all items in failed[]."""
        items = [
            self._input("bad-account-1", "bad-cat-1", merchant_name="A"),
            self._input("bad-account-2", "bad-cat-2", merchant_name="B"),
        ]
        result = local_provider.create_transactions(items)

        assert result["success"] is False
        assert result["success_count"] == 0
        assert result["failure_count"] == 2
        assert result["created"] == []
        assert [f["index"] for f in result["failed"]] == [0, 1]

    def test_create_empty_list(self, local_provider):
        """Empty input list yields an empty success envelope (vacuously successful)."""
        result = local_provider.create_transactions([])
        assert result["success"] is True
        assert result["success_count"] == 0
        assert result["failure_count"] == 0
        assert result["created"] == []
        assert result["failed"] == []
