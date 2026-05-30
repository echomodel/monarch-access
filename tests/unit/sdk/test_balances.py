"""Tests for account balance history operations."""

import pytest

from monarch.balances import (
    BalanceHistoryTokenMismatch,
    history_token,
    parse_balance_csv,
    snapshots_to_csv,
)


def _token(provider, account_id):
    """The current history token for an account (what a real caller would read
    from download_balance_history before uploading)."""
    return history_token(provider.download_balance_history(account_id))


class TestDownloadBalanceHistory:
    """Reading balance snapshots via the local provider."""

    def test_download_returns_snapshots(self, local_provider):
        snapshots = local_provider.download_balance_history("acc_001")
        assert len(snapshots) == 4
        assert snapshots[0] == {"date": "2026-01-01", "balance": 5000.00}

    def test_download_sorted_by_date(self, local_provider):
        snapshots = local_provider.download_balance_history("acc_001")
        dates = [s["date"] for s in snapshots]
        assert dates == sorted(dates)

    def test_download_liability_negative_balances(self, local_provider):
        snapshots = local_provider.download_balance_history("acc_004")
        assert all(s["balance"] < 0 for s in snapshots)

    def test_download_unknown_account_empty(self, local_provider):
        assert local_provider.download_balance_history("acc_nonexistent") == []


class TestHistoryToken:
    """The read-before-write interlock token."""

    def test_token_is_stable_for_same_history(self, local_provider):
        a = _token(local_provider, "acc_001")
        b = _token(local_provider, "acc_001")
        assert a == b

    def test_token_independent_of_input_order(self):
        ordered = [
            {"date": "2026-01-01", "balance": 1.0},
            {"date": "2026-02-01", "balance": 2.0},
        ]
        shuffled = list(reversed(ordered))
        assert history_token(ordered) == history_token(shuffled)

    def test_token_changes_when_history_changes(self, local_provider):
        before = _token(local_provider, "acc_001")
        local_provider.upload_balance_history(
            "acc_001", [{"date": "2026-09-01", "balance": 9.0}], before
        )
        after = _token(local_provider, "acc_001")
        assert before != after

    def test_empty_history_has_a_token(self):
        # A fresh account (no history) still yields a stable token, so uploading
        # to it still requires reading first.
        assert isinstance(history_token([]), int)


class TestUploadBalanceHistory:
    """Uploading replaces the entire history and updates currentBalance."""

    def test_upload_replaces_history(self, local_provider):
        token = _token(local_provider, "acc_001")
        new = [
            {"date": "2026-05-01", "balance": 5500.00},
            {"date": "2026-06-01", "balance": 6000.00},
        ]
        result = local_provider.upload_balance_history("acc_001", new, token)
        assert result["success"] is True
        after = local_provider.download_balance_history("acc_001")
        assert [s["date"] for s in after] == ["2026-05-01", "2026-06-01"]

    def test_upload_updates_current_balance_to_final_row(self, local_provider):
        token = _token(local_provider, "acc_001")
        new = [
            {"date": "2026-05-01", "balance": 5500.00},
            {"date": "2026-06-01", "balance": 6000.00},
        ]
        local_provider.upload_balance_history("acc_001", new, token)
        acct = next(a for a in local_provider.get_accounts() if a["id"] == "acc_001")
        assert acct["currentBalance"] == 6000.00

    def test_upload_returns_previous_snapshots_for_rollback(self, local_provider):
        before = local_provider.download_balance_history("acc_001")
        token = history_token(before)
        result = local_provider.upload_balance_history(
            "acc_001", [{"date": "2026-07-01", "balance": 1.0}], token
        )
        assert result["previous_snapshots"] == before

    def test_upload_then_rollback(self, local_provider):
        original = local_provider.download_balance_history("acc_001")
        token = history_token(original)
        result = local_provider.upload_balance_history(
            "acc_001", [{"date": "2026-07-01", "balance": 1.0}], token
        )
        # Restore by uploading the captured previous snapshots back. The token
        # must be re-read because the history just changed.
        new_token = _token(local_provider, "acc_001")
        local_provider.upload_balance_history("acc_001", result["previous_snapshots"], new_token)
        assert local_provider.download_balance_history("acc_001") == original

    def test_upload_reported_count(self, local_provider):
        token = _token(local_provider, "acc_001")
        result = local_provider.upload_balance_history(
            "acc_001",
            [{"date": "2026-05-01", "balance": 1.0}, {"date": "2026-06-01", "balance": 2.0}],
            token,
        )
        assert result["uploaded_count"] == 2


class TestUploadTokenInterlock:
    """The token guard: upload refuses without a matching, fresh token."""

    def test_wrong_token_is_rejected(self, local_provider):
        with pytest.raises(BalanceHistoryTokenMismatch):
            local_provider.upload_balance_history(
                "acc_001", [{"date": "2026-05-01", "balance": 1.0}], 999999
            )

    def test_rejected_upload_changes_nothing(self, local_provider):
        before = local_provider.download_balance_history("acc_001")
        with pytest.raises(BalanceHistoryTokenMismatch):
            local_provider.upload_balance_history(
                "acc_001", [{"date": "2026-05-01", "balance": 1.0}], 999999
            )
        assert local_provider.download_balance_history("acc_001") == before

    def test_stale_token_is_rejected(self, local_provider):
        """A token read before an intervening change no longer validates."""
        stale = _token(local_provider, "acc_001")
        # An intervening upload changes the history (and the token).
        local_provider.upload_balance_history(
            "acc_001", [{"date": "2026-08-01", "balance": 8.0}], stale
        )
        # Reusing the now-stale token must fail.
        with pytest.raises(BalanceHistoryTokenMismatch):
            local_provider.upload_balance_history(
                "acc_001", [{"date": "2026-09-01", "balance": 9.0}], stale
            )


class TestBalanceCsv:
    """CSV parse/format helpers (the on-the-wire representation)."""

    def test_parse_monarch_download_format(self):
        """Parses the Date,Balance,Account columns Monarch's download returns."""
        csv_text = "Date,Balance,Account\n2026-01-01,5000.00,Fairview Checking\n2026-02-01,5200.00,Fairview Checking\n"
        snapshots = parse_balance_csv(csv_text)
        assert snapshots == [
            {"date": "2026-01-01", "balance": 5000.00},
            {"date": "2026-02-01", "balance": 5200.00},
        ]

    def test_parse_skips_blank_rows(self):
        csv_text = "Date,Balance\n2026-01-01,100.0\n,\n"
        assert parse_balance_csv(csv_text) == [{"date": "2026-01-01", "balance": 100.0}]

    def test_snapshots_to_csv_header_and_rows(self):
        csv_text = snapshots_to_csv([{"date": "2026-01-01", "balance": -50.0}])
        lines = csv_text.strip().splitlines()
        assert lines[0] == "Date,Balance"
        assert lines[1] == "2026-01-01,-50.0"

    def test_csv_round_trip(self):
        snapshots = [
            {"date": "2026-01-01", "balance": 100.0},
            {"date": "2026-02-01", "balance": -200.5},
        ]
        assert parse_balance_csv(snapshots_to_csv(snapshots)) == snapshots
