"""Tests for account management (update_account / close_account)."""

import pytest


class TestCloseAccount:
    """Closing sets deactivatedAt and drops the account from the default list."""

    def test_close_sets_deactivated_at(self, local_provider):
        acct = local_provider.close_account("acc_009", close_date="2026-05-29")
        assert acct["deactivatedAt"] == "2026-05-29"

    def test_close_defaults_to_today(self, local_provider):
        acct = local_provider.close_account("acc_009")
        assert acct["deactivatedAt"]  # some date string was set

    def test_closed_account_leaves_default_list(self, local_provider):
        assert any(a["id"] == "acc_009" for a in local_provider.get_accounts())
        local_provider.close_account("acc_009", close_date="2026-05-29")
        assert all(a["id"] != "acc_009" for a in local_provider.get_accounts())

    def test_closed_account_visible_with_include_closed(self, local_provider):
        local_provider.close_account("acc_009", close_date="2026-05-29")
        ids = [a["id"] for a in local_provider.get_accounts(include_closed=True)]
        assert "acc_009" in ids

    def test_close_retains_balance_history(self, local_provider):
        """Closing keeps the account record and its balance (history retained)."""
        before = next(a for a in local_provider.get_accounts() if a["id"] == "acc_009")
        balance = before["currentBalance"]
        local_provider.close_account("acc_009", close_date="2026-05-29")
        after = next(
            a for a in local_provider.get_accounts(include_closed=True) if a["id"] == "acc_009"
        )
        assert after["currentBalance"] == balance


class TestReopenAccount:
    """Clearing deactivatedAt reopens a closed account."""

    def test_reopen_clears_deactivated_at(self, local_provider):
        local_provider.close_account("acc_009", close_date="2026-05-29")
        reopened = local_provider.update_account("acc_009", deactivated_at=None)
        assert not reopened["deactivatedAt"]

    def test_reopened_account_returns_to_default_list(self, local_provider):
        local_provider.close_account("acc_009", close_date="2026-05-29")
        assert all(a["id"] != "acc_009" for a in local_provider.get_accounts())
        local_provider.update_account("acc_009", deactivated_at=None)
        assert any(a["id"] == "acc_009" for a in local_provider.get_accounts())


class TestUpdateAccount:
    """Partial updates change only the provided fields."""

    def test_rename(self, local_provider):
        acct = local_provider.update_account("acc_009", name="Brokerage (Old)")
        assert acct["displayName"] == "Brokerage (Old)"

    def test_rename_leaves_other_fields(self, local_provider):
        before = next(a for a in local_provider.get_accounts() if a["id"] == "acc_009")
        balance = before["currentBalance"]
        acct = local_provider.update_account("acc_009", name="Renamed")
        assert acct["currentBalance"] == balance

    def test_exclude_from_net_worth(self, local_provider):
        acct = local_provider.update_account("acc_009", include_in_net_worth=False)
        assert acct["includeInNetWorth"] is False
        # Excluding does NOT remove it from the accounts list (distinct from closing).
        assert any(a["id"] == "acc_009" for a in local_provider.get_accounts())

    def test_hide_removes_from_default_list(self, local_provider):
        local_provider.update_account("acc_009", hidden=True)
        assert all(a["id"] != "acc_009" for a in local_provider.get_accounts())
        ids = [a["id"] for a in local_provider.get_accounts(include_closed=True)]
        assert "acc_009" in ids

    def test_no_op_update_preserves_account(self, local_provider):
        """Calling update with no fields leaves the account unchanged."""
        before = next(a for a in local_provider.get_accounts() if a["id"] == "acc_009")
        after = local_provider.update_account("acc_009")
        assert after["displayName"] == before["displayName"]

    def test_update_unknown_account_raises(self, local_provider):
        with pytest.raises(ValueError, match="Account not found"):
            local_provider.update_account("acc_nonexistent", name="X")
