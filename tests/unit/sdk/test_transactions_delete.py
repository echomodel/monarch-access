"""Tests for transactions delete operations.

The SDK exposes a plural-only delete_transactions that takes a list of
transaction IDs and returns a per-item result envelope (deleted[], failed[],
counts).
"""

import pytest


class TestTransactionsDelete:
    """Test deleting transactions via the plural API."""

    def _create_one(self, local_provider, merchant_name="To Delete"):
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        result = local_provider.create_transactions([{
            "date": "2026-01-15",
            "account_id": accounts[0]["id"],
            "amount": -1.00,
            "merchant_name": merchant_name,
            "category_id": categories[0]["id"],
            "notes": "",
        }])
        return result["created"][0]["transaction"]["id"]

    def test_delete_single_basic(self, local_provider):
        """Deleting one transaction returns success envelope."""
        txn_id = self._create_one(local_provider, "Solo")

        result = local_provider.delete_transactions([txn_id])

        assert result["success"] is True
        assert result["success_count"] == 1
        assert result["failure_count"] == 0
        assert result["failed"] == []
        assert result["deleted"] == [{"index": 0, "transaction_id": txn_id}]

        # Verify the transaction is gone
        assert local_provider.get_transaction(txn_id) is None

    def test_delete_nonexistent_reported_per_item(self, local_provider):
        """Deleting a missing ID is reported in failed[] without raising."""
        result = local_provider.delete_transactions(["does-not-exist"])

        assert result["success"] is False
        assert result["success_count"] == 0
        assert result["failure_count"] == 1
        assert result["deleted"] == []
        assert len(result["failed"]) == 1
        failure = result["failed"][0]
        assert failure["index"] == 0
        assert failure["transaction_id"] == "does-not-exist"
        assert "Transaction not found" in failure["error"]

    def test_delete_multiple_all_succeed(self, local_provider):
        """Bulk delete of N valid IDs returns N deleted and 0 failed."""
        ids = [
            self._create_one(local_provider, "A"),
            self._create_one(local_provider, "B"),
            self._create_one(local_provider, "C"),
        ]

        result = local_provider.delete_transactions(ids)

        assert result["success"] is True
        assert result["success_count"] == 3
        assert result["failure_count"] == 0
        assert [e["index"] for e in result["deleted"]] == [0, 1, 2]
        assert [e["transaction_id"] for e in result["deleted"]] == ids
        for tid in ids:
            assert local_provider.get_transaction(tid) is None

    def test_delete_multiple_mixed_partial_success(self, local_provider):
        """Mixed batch: real IDs succeed, fake IDs fail; positions preserved."""
        real_a = self._create_one(local_provider, "Real A")
        real_b = self._create_one(local_provider, "Real B")

        ids = [real_a, "nope-1", real_b, "nope-2"]
        result = local_provider.delete_transactions(ids)

        assert result["success"] is False
        assert result["success_count"] == 2
        assert result["failure_count"] == 2
        assert [e["index"] for e in result["deleted"]] == [0, 2]
        assert [e["transaction_id"] for e in result["deleted"]] == [real_a, real_b]
        assert [f["index"] for f in result["failed"]] == [1, 3]
        assert [f["transaction_id"] for f in result["failed"]] == ["nope-1", "nope-2"]
        for f in result["failed"]:
            assert "Transaction not found" in f["error"]

        # Real ones are gone; fakes never existed.
        assert local_provider.get_transaction(real_a) is None
        assert local_provider.get_transaction(real_b) is None

    def test_delete_multiple_all_fail(self, local_provider):
        """All-failure batch: success_count is 0, all items in failed[]."""
        result = local_provider.delete_transactions(["x", "y", "z"])

        assert result["success"] is False
        assert result["success_count"] == 0
        assert result["failure_count"] == 3
        assert result["deleted"] == []
        assert [f["transaction_id"] for f in result["failed"]] == ["x", "y", "z"]
        assert [f["index"] for f in result["failed"]] == [0, 1, 2]

    def test_delete_empty_list(self, local_provider):
        """Empty input list yields an empty success envelope."""
        result = local_provider.delete_transactions([])
        assert result["success"] is True
        assert result["success_count"] == 0
        assert result["failure_count"] == 0
        assert result["deleted"] == []
        assert result["failed"] == []

    def test_delete_then_redelete_fails(self, local_provider):
        """Deleting the same ID twice: first succeeds, second is a per-item failure."""
        txn_id = self._create_one(local_provider, "Once")

        first = local_provider.delete_transactions([txn_id])
        assert first["success"] is True

        second = local_provider.delete_transactions([txn_id])
        assert second["success"] is False
        assert second["failure_count"] == 1
        assert "Transaction not found" in second["failed"][0]["error"]
