"""Tests for transactions update operations."""

import pytest


class TestTransactionsUpdate:
    """Test updating transactions."""

    def test_update_transaction_notes(self, local_provider):
        """Test updating transaction notes."""
        # Get a transaction to update
        result = local_provider.get_transactions(limit=1)
        txn_id = result["results"][0]["id"]
        original_notes = result["results"][0].get("notes", "")

        # Update notes
        new_notes = "Updated by test"
        updated = local_provider.update_transaction(txn_id, notes=new_notes)

        assert updated["notes"] == new_notes

        # Verify via get
        fetched = local_provider.get_transaction(txn_id)
        assert fetched["notes"] == new_notes

    def test_update_transaction_merchant(self, local_provider):
        """Test updating transaction merchant name."""
        result = local_provider.get_transactions(limit=1)
        txn_id = result["results"][0]["id"]

        new_merchant = "Test Merchant"
        updated = local_provider.update_transaction(txn_id, merchant_name=new_merchant)

        assert updated["merchant"]["name"] == new_merchant

    def test_update_transaction_not_found(self, local_provider):
        """Test updating a non-existent transaction raises error."""
        with pytest.raises(ValueError, match="Transaction not found"):
            local_provider.update_transaction("nonexistent_id", notes="test")

    def test_update_transaction_partial(self, local_provider):
        """Test that update only changes specified fields."""
        result = local_provider.get_transactions(limit=1)
        txn_id = result["results"][0]["id"]
        original = local_provider.get_transaction(txn_id)
        original_amount = original["amount"]
        original_date = original["date"]

        # Update only notes
        local_provider.update_transaction(txn_id, notes="Partial update test")

        # Verify other fields unchanged
        updated = local_provider.get_transaction(txn_id)
        assert updated["amount"] == original_amount
        assert updated["date"] == original_date
        assert updated["notes"] == "Partial update test"

    def test_update_transaction_clear_notes(self, local_provider):
        """Test clearing notes with empty string."""
        result = local_provider.get_transactions(limit=1)
        txn_id = result["results"][0]["id"]

        # Set notes first
        local_provider.update_transaction(txn_id, notes="Some notes")

        # Clear notes
        updated = local_provider.update_transaction(txn_id, notes="")

        assert updated["notes"] == ""
