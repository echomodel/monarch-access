"""Tests for transactions get operations."""

import pytest


class TestTransactionsGet:
    """Test getting a single transaction."""

    def test_get_transaction_by_id(self, local_provider):
        """Test fetching a transaction by its ID."""
        # First get a transaction to know a valid ID
        result = local_provider.get_transactions(limit=1)
        assert len(result["results"]) > 0
        txn_id = result["results"][0]["id"]

        # Now fetch by ID
        txn = local_provider.get_transaction(txn_id)

        assert txn is not None
        assert txn["id"] == txn_id
        assert "amount" in txn
        assert "date" in txn
        assert "merchant" in txn
        assert "category" in txn
        assert "account" in txn

    def test_get_transaction_not_found(self, local_provider):
        """Test fetching a non-existent transaction returns None."""
        txn = local_provider.get_transaction("nonexistent_id_12345")

        assert txn is None

    def test_get_transaction_has_expected_fields(self, local_provider):
        """Test that returned transaction has all expected fields."""
        result = local_provider.get_transactions(limit=1)
        txn_id = result["results"][0]["id"]

        txn = local_provider.get_transaction(txn_id)

        expected_fields = [
            "id", "amount", "date", "pending", "notes",
            "merchant", "category", "account", "hideFromReports",
            "needsReview", "isRecurring"
        ]
        for field in expected_fields:
            assert field in txn, f"Missing field: {field}"
