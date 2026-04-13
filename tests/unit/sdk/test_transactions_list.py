"""Tests for transactions list operations."""

import pytest


class TestTransactionsListByDateRange:
    """Test transaction listing with date range filters."""

    def test_transactions_list_by_date_range(self, local_provider):
        """Test filtering transactions by start and end date."""
        # Get transactions within a specific date range
        result = local_provider.get_transactions(
            start_date="2025-06-01",
            end_date="2025-06-30",
            limit=1000,
        )

        assert "totalCount" in result
        assert "results" in result

        # All returned transactions should be within the date range
        for txn in result["results"]:
            assert txn["date"] >= "2025-06-01"
            assert txn["date"] <= "2025-06-30"

    def test_transactions_list_start_date_only(self, local_provider):
        """Test filtering with only start date."""
        result = local_provider.get_transactions(
            start_date="2025-10-01",
            limit=1000,
        )

        for txn in result["results"]:
            assert txn["date"] >= "2025-10-01"

    def test_transactions_list_end_date_only(self, local_provider):
        """Test filtering with only end date."""
        result = local_provider.get_transactions(
            end_date="2025-03-31",
            limit=1000,
        )

        for txn in result["results"]:
            assert txn["date"] <= "2025-03-31"

    def test_transactions_list_returns_sorted_descending(self, local_provider):
        """Test that transactions are sorted by date descending."""
        result = local_provider.get_transactions(limit=100)

        dates = [txn["date"] for txn in result["results"]]
        assert dates == sorted(dates, reverse=True)

    def test_transactions_list_respects_limit(self, local_provider):
        """Test that limit parameter is respected."""
        result = local_provider.get_transactions(limit=10)

        assert len(result["results"]) <= 10

    def test_transactions_list_total_count_independent_of_limit(self, local_provider):
        """Test that totalCount reflects all matching transactions."""
        result_small = local_provider.get_transactions(limit=5)
        result_large = local_provider.get_transactions(limit=1000)

        # totalCount should be the same regardless of limit
        assert result_small["totalCount"] == result_large["totalCount"]
