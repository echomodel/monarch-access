"""Tests for transactions create operations."""

import pytest


class TestTransactionsCreate:
    """Test creating transactions."""

    def test_create_transaction_basic(self, local_provider):
        """Test creating a basic transaction."""
        # Get a valid account and category
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()

        assert len(accounts) > 0, "Need at least one account for test"
        assert len(categories) > 0, "Need at least one category for test"

        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        # Create transaction
        created = local_provider.create_transaction(
            date="2026-01-15",
            account_id=account_id,
            amount=-100.50,
            merchant_name="Test Merchant",
            category_id=category_id,
            notes="Test transaction notes",
        )

        # Verify returned transaction
        assert created["id"] is not None
        assert created["amount"] == -100.50
        assert created["date"] == "2026-01-15"
        assert created["notes"] == "Test transaction notes"
        assert created["merchant"]["name"] == "Test Merchant"
        assert created["account"]["id"] == account_id
        assert created["category"]["id"] == category_id

    def test_create_transaction_can_be_retrieved(self, local_provider):
        """Test that created transaction can be retrieved."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        created = local_provider.create_transaction(
            date="2026-02-01",
            account_id=account_id,
            amount=-50.00,
            merchant_name="Retrievable Merchant",
            category_id=category_id,
        )

        # Retrieve by ID
        fetched = local_provider.get_transaction(created["id"])
        assert fetched is not None
        assert fetched["id"] == created["id"]
        assert fetched["amount"] == -50.00
        assert fetched["merchant"]["name"] == "Retrievable Merchant"

    def test_create_transaction_appears_in_list(self, local_provider):
        """Test that created transaction appears in list results."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        # Get initial count
        initial_result = local_provider.get_transactions(limit=1000)
        initial_count = initial_result["totalCount"]

        # Create transaction
        created = local_provider.create_transaction(
            date="2026-03-01",
            account_id=account_id,
            amount=-75.00,
            merchant_name="List Test Merchant",
            category_id=category_id,
        )

        # Verify count increased
        after_result = local_provider.get_transactions(limit=1000)
        assert after_result["totalCount"] == initial_count + 1

        # Verify transaction in results
        ids = [t["id"] for t in after_result["results"]]
        assert created["id"] in ids

    def test_create_transaction_positive_amount(self, local_provider):
        """Test creating a transaction with positive amount (income)."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        created = local_provider.create_transaction(
            date="2026-04-01",
            account_id=account_id,
            amount=500.00,
            merchant_name="Income Source",
            category_id=category_id,
            notes="Income transaction",
        )

        assert created["amount"] == 500.00

    def test_create_transaction_rounds_amount(self, local_provider):
        """Test that amount is rounded to 2 decimal places."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        created = local_provider.create_transaction(
            date="2026-05-01",
            account_id=account_id,
            amount=-99.999,
            merchant_name="Rounding Test",
            category_id=category_id,
        )

        assert created["amount"] == -100.00

    def test_create_transaction_invalid_account(self, local_provider):
        """Test creating transaction with invalid account raises error."""
        categories = local_provider.get_categories()
        category_id = categories[0]["id"]

        with pytest.raises(ValueError, match="Account not found"):
            local_provider.create_transaction(
                date="2026-06-01",
                account_id="nonexistent_account_id",
                amount=-50.00,
                merchant_name="Test",
                category_id=category_id,
            )

    def test_create_transaction_invalid_category(self, local_provider):
        """Test creating transaction with invalid category raises error."""
        accounts = local_provider.get_accounts()
        account_id = accounts[0]["id"]

        with pytest.raises(ValueError, match="Category not found"):
            local_provider.create_transaction(
                date="2026-07-01",
                account_id=account_id,
                amount=-50.00,
                merchant_name="Test",
                category_id="nonexistent_category_id",
            )

    def test_create_transaction_empty_notes(self, local_provider):
        """Test creating transaction with empty notes."""
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        created = local_provider.create_transaction(
            date="2026-08-01",
            account_id=account_id,
            amount=-25.00,
            merchant_name="No Notes Merchant",
            category_id=category_id,
            notes="",
        )

        assert created["notes"] == ""

    def test_create_transaction_default_fields(self, local_provider):
        """Test that created transaction has correct default field values.

        Verified against live API behavior for manually created transactions.
        """
        accounts = local_provider.get_accounts()
        categories = local_provider.get_categories()
        account_id = accounts[0]["id"]
        category_id = categories[0]["id"]

        created = local_provider.create_transaction(
            date="2026-09-01",
            account_id=account_id,
            amount=-10.00,
            merchant_name="Defaults Test",
            category_id=category_id,
        )

        # These defaults match live API behavior for manual transactions
        assert created["pending"] is False
        assert created["hideFromReports"] is False
        assert created["needsReview"] is False  # Confirmed: live API returns false
        assert created["isSplitTransaction"] is False
        assert created["tags"] == []
