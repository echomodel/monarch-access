"""Tests for transaction tag operations: non-destructive add/remove and tag filtering.

Sociable: complete tag transactions run through the local provider's real code
paths (no mocks). The key properties under test are non-destructiveness (adding a
tag never drops an existing one), idempotency, and tag-based filtering.
"""


class TestTransactionTags:
    def _a_txn_id(self, provider):
        return provider.get_transactions(limit=1)["results"][0]["id"]

    def test_add_tag_then_transaction_carries_it(self, local_provider):
        txn_id = self._a_txn_id(local_provider)
        updated = local_provider.add_transaction_tag(txn_id, "agent-reviewed")
        names = [t["name"] for t in updated.get("tags", [])]
        assert "agent-reviewed" in names

    def test_add_tag_preserves_existing_tags(self, local_provider):
        """Adding a second tag must not drop the first (read-union-write)."""
        txn_id = self._a_txn_id(local_provider)
        local_provider.add_transaction_tag(txn_id, "first")
        updated = local_provider.add_transaction_tag(txn_id, "second")
        names = {t["name"] for t in updated.get("tags", [])}
        assert names == {"first", "second"}

    def test_adding_same_tag_twice_is_idempotent(self, local_provider):
        txn_id = self._a_txn_id(local_provider)
        local_provider.add_transaction_tag(txn_id, "agent-reviewed")
        updated = local_provider.add_transaction_tag(txn_id, "agent-reviewed")
        names = [t["name"] for t in updated.get("tags", [])]
        assert names.count("agent-reviewed") == 1

    def test_remove_tag_preserves_other_tags(self, local_provider):
        txn_id = self._a_txn_id(local_provider)
        local_provider.add_transaction_tag(txn_id, "keep")
        local_provider.add_transaction_tag(txn_id, "drop")
        updated = local_provider.remove_transaction_tag(txn_id, "drop")
        names = {t["name"] for t in updated.get("tags", [])}
        assert names == {"keep"}

    def test_removing_absent_tag_is_noop(self, local_provider):
        txn_id = self._a_txn_id(local_provider)
        local_provider.add_transaction_tag(txn_id, "keep")
        updated = local_provider.remove_transaction_tag(txn_id, "never-applied")
        names = {t["name"] for t in updated.get("tags", [])}
        assert names == {"keep"}

    def test_list_tags_includes_a_created_tag(self, local_provider):
        txn_id = self._a_txn_id(local_provider)
        local_provider.add_transaction_tag(txn_id, "agent-reviewed")
        names = [t["name"] for t in local_provider.list_tags()]
        assert "agent-reviewed" in names

    def test_filter_by_tag_returns_only_tagged_transactions(self, local_provider):
        all_ids = [t["id"] for t in local_provider.get_transactions(limit=100)["results"]]
        assert len(all_ids) > 1, "need >1 seed transaction to prove exclusion"
        tagged = all_ids[0]
        local_provider.add_transaction_tag(tagged, "agent-reviewed")
        tag_id = next(t["id"] for t in local_provider.list_tags()
                      if t["name"] == "agent-reviewed")
        result = local_provider.get_transactions(tags=[tag_id], limit=100)
        assert {t["id"] for t in result["results"]} == {tagged}
