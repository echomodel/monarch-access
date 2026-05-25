"""Tests for splitting a transaction across multiple categories."""

import pytest


class TestSplitTransaction:
    """Test split_transaction via local provider."""

    def _first_txn(self, local_provider):
        result = local_provider.get_transactions(limit=1)
        return result["results"][0]

    def test_split_marks_original_as_split(self, local_provider):
        """After split_transaction, the original is flagged isSplitTransaction."""
        original = self._first_txn(local_provider)
        txn_id = original["id"]
        cats = local_provider.get_categories()

        amount = original["amount"]
        half = round(amount / 2, 2)
        # Make the two splits sum exactly to amount (handle the +/-0.01 case).
        splits = [
            {"amount": half, "categoryId": cats[0]["id"]},
            {"amount": round(amount - half, 2), "categoryId": cats[1]["id"]},
        ]

        result = local_provider.split_transaction(txn_id, splits)
        assert result["success"] is True

        fetched = local_provider.get_transaction(txn_id)
        assert fetched["isSplitTransaction"] is True
        assert len(fetched["splits"]) == 2

    def test_split_stores_per_split_category_and_amount(self, local_provider):
        """Each materialized split carries the requested category and amount."""
        original = self._first_txn(local_provider)
        cats = local_provider.get_categories()

        amount = original["amount"]
        a = round(amount * 0.4, 2)
        b = round(amount - a, 2)
        splits = [
            {"amount": a, "categoryId": cats[0]["id"], "notes": "first half"},
            {"amount": b, "categoryId": cats[1]["id"], "notes": "second half"},
        ]

        result = local_provider.split_transaction(original["id"], splits)
        stored = result["transaction"]["splits"]
        assert stored[0]["amount"] == a
        assert stored[0]["category"]["id"] == cats[0]["id"]
        assert stored[0]["notes"] == "first half"
        assert stored[1]["amount"] == b
        assert stored[1]["category"]["id"] == cats[1]["id"]

    def test_split_with_merchant_name_recorded(self, local_provider):
        """Optional merchantName on a split is preserved."""
        original = self._first_txn(local_provider)
        cats = local_provider.get_categories()

        splits = [{
            "amount": original["amount"],
            "categoryId": cats[0]["id"],
            "merchantName": "Split Merchant",
        }]
        result = local_provider.split_transaction(original["id"], splits)
        stored = result["transaction"]["splits"][0]
        assert stored["merchant"]["name"] == "Split Merchant"

    def test_split_sum_mismatch_raises(self, local_provider):
        """Splits whose sum doesn't equal the original raise ValueError."""
        original = self._first_txn(local_provider)
        cats = local_provider.get_categories()

        # Deliberately wrong: total off by $1.
        splits = [
            {"amount": round(original["amount"] / 2, 2), "categoryId": cats[0]["id"]},
            {"amount": round(original["amount"] / 2, 2) + 1.0, "categoryId": cats[1]["id"]},
        ]
        with pytest.raises(ValueError, match="does not equal"):
            local_provider.split_transaction(original["id"], splits)

    def test_split_unknown_category_raises(self, local_provider):
        """A split referencing a missing category raises ValueError."""
        original = self._first_txn(local_provider)
        with pytest.raises(ValueError, match="Category not found"):
            local_provider.split_transaction(
                original["id"],
                [{"amount": original["amount"], "categoryId": "cat_nonexistent"}],
            )

    def test_split_unknown_transaction_raises(self, local_provider):
        """Splitting a missing transaction raises ValueError."""
        with pytest.raises(ValueError, match="Transaction not found"):
            local_provider.split_transaction(
                "txn_nonexistent",
                [{"amount": 1.00, "categoryId": "cat_001"}],
            )

    def test_split_empty_list_clears_split_state(self, local_provider):
        """Passing [] removes the split — original is no longer flagged as split."""
        original = self._first_txn(local_provider)
        cats = local_provider.get_categories()

        # First, actually split it.
        amount = original["amount"]
        local_provider.split_transaction(
            original["id"],
            [
                {"amount": round(amount / 2, 2), "categoryId": cats[0]["id"]},
                {"amount": round(amount - round(amount / 2, 2), 2),
                 "categoryId": cats[1]["id"]},
            ],
        )
        assert local_provider.get_transaction(original["id"])["isSplitTransaction"] is True

        # Then clear.
        local_provider.split_transaction(original["id"], [])
        cleared = local_provider.get_transaction(original["id"])
        assert cleared["isSplitTransaction"] is False
        assert cleared["splits"] == []
