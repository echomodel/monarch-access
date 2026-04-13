"""Tests for accounts operations."""

import pytest


class TestAccountsList:
    """Test listing accounts."""

    def test_get_accounts_returns_list(self, local_provider):
        """Test that get_accounts returns a list."""
        accounts = local_provider.get_accounts()

        assert isinstance(accounts, list)
        assert len(accounts) > 0

    def test_get_accounts_has_expected_fields(self, local_provider):
        """Test that accounts have expected fields."""
        accounts = local_provider.get_accounts()
        account = accounts[0]

        expected_fields = ["id", "displayName", "type", "currentBalance", "institution"]
        for field in expected_fields:
            assert field in account, f"Missing field: {field}"

    def test_get_accounts_includes_all_types(self, local_provider):
        """Test that accounts include various types."""
        accounts = local_provider.get_accounts()
        types = {a["type"]["name"] for a in accounts}

        # Based on our seed data
        assert "checking" in types
        assert "savings" in types
        assert "credit" in types

    def test_get_accounts_has_institution_info(self, local_provider):
        """Test that accounts include institution information."""
        accounts = local_provider.get_accounts()

        for account in accounts:
            assert "institution" in account
            assert "id" in account["institution"]
            assert "name" in account["institution"]
