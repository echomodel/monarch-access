"""Tests for bulk marking transactions reviewed / needing review."""


class TestBulkMarkReviewed:
    """Test bulk_mark_reviewed via local provider."""

    def _first_n_ids(self, local_provider, n):
        result = local_provider.get_transactions(limit=n)
        return [t["id"] for t in result["results"][:n]]

    def test_bulk_mark_reviewed_sets_needs_review_false(self, local_provider):
        """Default call marks selected transactions as reviewed (needsReview=False)."""
        ids = self._first_n_ids(local_provider, 3)

        # Force them to needsReview=True so the bulk update is observable.
        for tid in ids:
            local_provider.update_transaction(tid, needs_review=True)

        result = local_provider.bulk_mark_reviewed(ids)
        assert result["success"] is True
        assert result["affectedCount"] == 3

        for tid in ids:
            assert local_provider.get_transaction(tid)["needsReview"] is False

    def test_bulk_mark_reviewed_can_set_needs_review_true(self, local_provider):
        """Explicit needs_review=True flips the flag the other way."""
        ids = self._first_n_ids(local_provider, 2)
        for tid in ids:
            local_provider.update_transaction(tid, needs_review=False)

        result = local_provider.bulk_mark_reviewed(ids, needs_review=True)
        assert result["affectedCount"] == 2
        for tid in ids:
            assert local_provider.get_transaction(tid)["needsReview"] is True

    def test_bulk_mark_reviewed_does_not_affect_other_transactions(self, local_provider):
        """Transactions not in the list are unchanged."""
        all_ids = [t["id"] for t in local_provider.get_transactions(limit=1000)["results"]]
        target_ids = all_ids[:2]
        untouched_ids = all_ids[2:]

        # Seed: everyone needsReview=True
        for tid in all_ids:
            local_provider.update_transaction(tid, needs_review=True)

        local_provider.bulk_mark_reviewed(target_ids, needs_review=False)

        for tid in untouched_ids:
            assert local_provider.get_transaction(tid)["needsReview"] is True

    def test_bulk_mark_reviewed_preserves_other_fields(self, local_provider):
        """Bulk review only touches needsReview — amount/notes/category unchanged."""
        tid = self._first_n_ids(local_provider, 1)[0]
        before = local_provider.get_transaction(tid)

        local_provider.bulk_mark_reviewed([tid], needs_review=True)

        after = local_provider.get_transaction(tid)
        assert after["needsReview"] is True
        assert after["amount"] == before["amount"]
        assert after["notes"] == before["notes"]
        assert after["category"]["id"] == before["category"]["id"]

    def test_bulk_mark_reviewed_ignores_unknown_ids(self, local_provider):
        """Unknown IDs are skipped silently — affectedCount reflects real hits."""
        real_ids = self._first_n_ids(local_provider, 2)
        mixed = real_ids + ["txn_nonexistent_1", "txn_nonexistent_2"]

        result = local_provider.bulk_mark_reviewed(mixed)
        assert result["success"] is True
        assert result["affectedCount"] == 2

    def test_bulk_mark_reviewed_empty_list_no_op(self, local_provider):
        """Empty input is a clean no-op — success with zero affected."""
        result = local_provider.bulk_mark_reviewed([])
        assert result["success"] is True
        assert result["affectedCount"] == 0
