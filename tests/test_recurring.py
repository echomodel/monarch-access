"""Tests for recurring transaction operations."""

from datetime import date, timedelta

from monarch.recurring import collapse_to_streams


class TestRecurringRawItems:
    """Test the raw recurring transaction items from the provider."""

    def test_get_recurring_returns_list(self, local_provider):
        """Test that get_recurring_transaction_items returns a list."""
        today = date.today()
        start = (today - timedelta(days=365)).isoformat()
        end = (today + timedelta(days=365)).isoformat()

        items = local_provider.get_recurring_transaction_items(
            start_date=start,
            end_date=end,
        )

        assert isinstance(items, list)
        assert len(items) > 0

    def test_recurring_items_have_expected_fields(self, local_provider):
        """Test that recurring items have the expected structure."""
        today = date.today()
        start = (today - timedelta(days=365)).isoformat()
        end = (today + timedelta(days=365)).isoformat()

        items = local_provider.get_recurring_transaction_items(
            start_date=start,
            end_date=end,
        )

        item = items[0]
        assert "stream" in item
        assert "date" in item
        assert "isPast" in item
        assert "amount" in item
        assert "category" in item
        assert "account" in item

    def test_recurring_date_filter_excludes(self, local_provider):
        """Test that date filtering excludes items outside range."""
        items = local_provider.get_recurring_transaction_items(
            start_date="2020-01-01",
            end_date="2020-01-02",
        )

        assert isinstance(items, list)
        assert len(items) == 0


class TestRecurringCollapse:
    """Test collapsing raw items into deduplicated obligation list."""

    def test_collapse_deduplicates_by_stream(self, local_provider):
        """Test that collapse produces one entry per recurring obligation."""
        today = date.today()
        start = (today - timedelta(days=365)).isoformat()
        end = (today + timedelta(days=365)).isoformat()

        items = local_provider.get_recurring_transaction_items(
            start_date=start,
            end_date=end,
        )
        streams = collapse_to_streams(items)

        # Seed has 4 recurring obligations
        assert len(streams) == 4

        # Each should be unique by stream_id
        stream_ids = [s["stream_id"] for s in streams]
        assert len(stream_ids) == len(set(stream_ids))

    def test_collapsed_items_have_expected_fields(self, local_provider):
        """Test that collapsed items have the right structure."""
        today = date.today()
        start = (today - timedelta(days=365)).isoformat()
        end = (today + timedelta(days=365)).isoformat()

        items = local_provider.get_recurring_transaction_items(
            start_date=start,
            end_date=end,
        )
        streams = collapse_to_streams(items)

        for s in streams:
            assert "stream_id" in s
            assert "merchant" in s
            assert "amount" in s
            assert "frequency" in s
            assert "category" in s
            assert "account" in s
            assert "is_past" in s
            assert isinstance(s["is_past"], bool)
            assert "due_date" in s
            assert "transaction_id" in s
            assert "last_paid_date" in s

    def test_collapsed_sorted_by_merchant(self, local_provider):
        """Test that collapsed list is sorted by merchant name."""
        today = date.today()
        start = (today - timedelta(days=365)).isoformat()
        end = (today + timedelta(days=365)).isoformat()

        items = local_provider.get_recurring_transaction_items(
            start_date=start,
            end_date=end,
        )
        streams = collapse_to_streams(items)

        merchants = [s["merchant"].lower() for s in streams]
        assert merchants == sorted(merchants)

    def test_collapsed_has_known_merchants(self, local_provider):
        """Test that seed data merchants appear in collapsed list."""
        today = date.today()
        start = (today - timedelta(days=365)).isoformat()
        end = (today + timedelta(days=365)).isoformat()

        items = local_provider.get_recurring_transaction_items(
            start_date=start,
            end_date=end,
        )
        streams = collapse_to_streams(items)

        merchant_names = {s["merchant"] for s in streams}
        assert "Netflix" in merchant_names
        assert "Spotify" in merchant_names
        assert "Fairview Bank Mortgage" in merchant_names
        assert "AutoFinance Co" in merchant_names

    def test_collapse_empty_list(self):
        """Test that collapsing empty list returns empty."""
        assert collapse_to_streams([]) == []
