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


class TestMarkNotRecurring:
    """Test removing a recurring stream from the catalog."""

    def _streams_in_provider(self, local_provider):
        today = date.today()
        items = local_provider.get_recurring_transaction_items(
            start_date=(today - timedelta(days=365)).isoformat(),
            end_date=(today + timedelta(days=365)).isoformat(),
        )
        return {item["stream"]["id"] for item in items}

    def test_mark_not_recurring_removes_target_stream(self, local_provider):
        """Stream disappears from recurring after mark_not_recurring."""
        ids_before = self._streams_in_provider(local_provider)
        assert "stream_001" in ids_before

        result = local_provider.mark_not_recurring("stream_001")
        assert result["success"] is True

        ids_after = self._streams_in_provider(local_provider)
        assert "stream_001" not in ids_after

    def test_mark_not_recurring_leaves_other_streams_intact(self, local_provider):
        """Removing one stream does not affect others."""
        ids_before = self._streams_in_provider(local_provider)
        target = "stream_001"
        others_before = ids_before - {target}

        local_provider.mark_not_recurring(target)

        ids_after = self._streams_in_provider(local_provider)
        assert ids_after == others_before

    def test_mark_not_recurring_unknown_stream_raises(self, local_provider):
        """Unknown stream id surfaces a clear error rather than silent no-op."""
        import pytest
        with pytest.raises(ValueError, match="Stream not found"):
            local_provider.mark_not_recurring("stream_nonexistent")


class TestUpdateRecurring:
    """Test updating fields on a recurring stream."""

    def _stream_by_id(self, local_provider, stream_id):
        today = date.today()
        items = local_provider.get_recurring_transaction_items(
            start_date=(today - timedelta(days=365)).isoformat(),
            end_date=(today + timedelta(days=365)).isoformat(),
        )
        for item in items:
            if item["stream"]["id"] == stream_id:
                return item["stream"]
        return None

    def test_update_recurring_changes_amount(self, local_provider):
        """Updating amount writes through to the stream object."""
        result = local_provider.update_recurring("stream_001", amount=-2750.00)
        assert result["success"] is True

        stream = self._stream_by_id(local_provider, "stream_001")
        assert stream is not None
        assert stream["amount"] == -2750.00

    def test_update_recurring_changes_frequency(self, local_provider):
        """Updating frequency writes through to the stream object."""
        local_provider.update_recurring("stream_001", frequency="biweekly")
        stream = self._stream_by_id(local_provider, "stream_001")
        assert stream["frequency"] == "biweekly"

    def test_update_recurring_partial_preserves_other_fields(self, local_provider):
        """An amount-only update leaves frequency untouched."""
        before = self._stream_by_id(local_provider, "stream_001")
        original_frequency = before["frequency"]

        local_provider.update_recurring("stream_001", amount=-9999.99)

        after = self._stream_by_id(local_provider, "stream_001")
        assert after["amount"] == -9999.99
        assert after["frequency"] == original_frequency

    def test_update_recurring_status_removed_removes_stream(self, local_provider):
        """status='removed' is equivalent to mark_not_recurring."""
        result = local_provider.update_recurring("stream_001", status="removed")
        assert result["success"] is True

        today = date.today()
        items = local_provider.get_recurring_transaction_items(
            start_date=(today - timedelta(days=365)).isoformat(),
            end_date=(today + timedelta(days=365)).isoformat(),
        )
        assert all(item["stream"]["id"] != "stream_001" for item in items)

    def test_update_recurring_unknown_stream_raises(self, local_provider):
        """Unknown stream id surfaces a clear error."""
        import pytest
        with pytest.raises(ValueError, match="Stream not found"):
            local_provider.update_recurring("stream_nonexistent", amount=-1)
