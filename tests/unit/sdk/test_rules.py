"""Tests for transaction rule operations."""

from monarch.rules import format_rule


class TestListRules:
    """Test rule listing via local provider."""

    def test_list_rules_returns_all(self, local_provider):
        """All seed rules are returned."""
        rules = local_provider.get_rules()
        assert len(rules) == 3

    def test_list_rules_sorted_by_order(self, local_provider):
        """Rules come back in execution order."""
        rules = local_provider.get_rules()
        orders = [r["order"] for r in rules]
        assert orders == sorted(orders)

    def test_rule_has_expected_fields(self, local_provider):
        """Raw rule has the fields Monarch's API returns."""
        rules = local_provider.get_rules()
        rule = rules[0]
        assert "id" in rule
        assert "order" in rule
        assert "merchantCriteria" in rule or "amountCriteria" in rule
        assert "setCategoryAction" in rule or "setMerchantAction" in rule


class TestFormatRule:
    """Test format_rule transforms raw API shape to clean output."""

    def test_format_merchant_criteria(self, local_provider):
        """Merchant criteria are flattened to operator/value dicts."""
        rules = local_provider.get_rules()
        # rule_001 has merchantCriteria: contains "whole foods"
        formatted = format_rule(rules[0])
        assert "merchant" in formatted["criteria"]
        mc = formatted["criteria"]["merchant"]
        assert mc[0]["operator"] == "contains"
        assert mc[0]["value"] == "whole foods"

    def test_format_amount_criteria(self, local_provider):
        """Amount criteria includes operator, is_expense, and value."""
        rules = local_provider.get_rules()
        formatted = format_rule(rules[0])
        ac = formatted["criteria"]["amount"]
        assert ac["operator"] == "gt"
        assert ac["is_expense"] is True
        assert ac["value"] == 0

    def test_format_account_filter(self, local_provider):
        """Account filter includes IDs and resolved names."""
        rules = local_provider.get_rules()
        formatted = format_rule(rules[0])
        assert "account_ids" in formatted["criteria"]
        assert "acc_001" in formatted["criteria"]["account_ids"]
        assert formatted["criteria"]["accounts"][0]["name"] == "Fairview Checking"

    def test_format_set_category_action(self, local_provider):
        """Set category action includes id and name."""
        rules = local_provider.get_rules()
        formatted = format_rule(rules[0])
        cat = formatted["actions"]["set_category"]
        assert cat["id"] == "cat_001"
        assert cat["name"] == "Groceries"

    def test_format_add_tags_action(self, local_provider):
        """Tags action includes id and name."""
        rules = local_provider.get_rules()
        # rule_002 has addTagsAction
        formatted = format_rule(rules[1])
        assert "add_tags" in formatted["actions"]
        assert formatted["actions"]["add_tags"][0]["name"] == "Subscription"

    def test_format_set_merchant_action(self, local_provider):
        """Set merchant action is a plain name string."""
        rules = local_provider.get_rules()
        # rule_003 has setMerchantAction
        formatted = format_rule(rules[2])
        assert formatted["actions"]["set_merchant"] == "Credit Card AutoPay"

    def test_format_original_statement_criteria(self, local_provider):
        """Original statement criteria are extracted."""
        rules = local_provider.get_rules()
        formatted = format_rule(rules[2])
        os_c = formatted["criteria"]["original_statement"]
        assert os_c[0]["operator"] == "contains"
        assert os_c[0]["value"] == "AUTOPAY"

    def test_format_null_last_applied(self, local_provider):
        """Rule with no applications has null last_applied_at."""
        rules = local_provider.get_rules()
        formatted = format_rule(rules[2])
        assert formatted["last_applied_at"] is None
        assert formatted["recent_application_count"] == 0

    def test_format_stats(self, local_provider):
        """Application stats are preserved."""
        rules = local_provider.get_rules()
        formatted = format_rule(rules[1])
        assert formatted["recent_application_count"] == 12
        assert formatted["last_applied_at"] is not None


class TestDeleteRule:
    """Test rule deletion via local provider."""

    def test_delete_existing_rule(self, local_provider):
        """Deleting an existing rule removes it."""
        assert len(local_provider.get_rules()) == 3
        result = local_provider.delete_rule("rule_002")
        assert result["deleted"] is True
        remaining = local_provider.get_rules()
        assert len(remaining) == 2
        assert all(r["id"] != "rule_002" for r in remaining)

    def test_delete_nonexistent_rule_raises(self, local_provider):
        """Deleting a missing rule raises ValueError."""
        import pytest
        with pytest.raises(ValueError, match="Rule not found"):
            local_provider.delete_rule("rule_nonexistent")

    def test_delete_does_not_affect_other_rules(self, local_provider):
        """Deleting one rule leaves others intact."""
        local_provider.delete_rule("rule_001")
        remaining = local_provider.get_rules()
        assert len(remaining) == 2
        ids = [r["id"] for r in remaining]
        assert "rule_002" in ids
        assert "rule_003" in ids
