"""Tests for account balance history operations."""

from monarch.balances import parse_balance_csv, snapshots_to_csv


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


class TestUploadBalanceHistory:
    """Uploading replaces the entire history and updates currentBalance."""

    def test_upload_replaces_history(self, local_provider):
        new = [
            {"date": "2026-05-01", "balance": 5500.00},
            {"date": "2026-06-01", "balance": 6000.00},
        ]
        result = local_provider.upload_balance_history("acc_001", new)
        assert result["success"] is True
        after = local_provider.download_balance_history("acc_001")
        assert [s["date"] for s in after] == ["2026-05-01", "2026-06-01"]

    def test_upload_updates_current_balance_to_final_row(self, local_provider):
        new = [
            {"date": "2026-05-01", "balance": 5500.00},
            {"date": "2026-06-01", "balance": 6000.00},
        ]
        local_provider.upload_balance_history("acc_001", new)
        acct = next(
            a for a in local_provider.get_accounts() if a["id"] == "acc_001"
        )
        assert acct["currentBalance"] == 6000.00

    def test_upload_returns_previous_snapshots_for_rollback(self, local_provider):
        before = local_provider.download_balance_history("acc_001")
        result = local_provider.upload_balance_history(
            "acc_001", [{"date": "2026-07-01", "balance": 1.0}]
        )
        assert result["previous_snapshots"] == before

    def test_upload_then_rollback(self, local_provider):
        original = local_provider.download_balance_history("acc_001")
        result = local_provider.upload_balance_history(
            "acc_001", [{"date": "2026-07-01", "balance": 1.0}]
        )
        # Restore by uploading the captured previous snapshots back.
        local_provider.upload_balance_history("acc_001", result["previous_snapshots"])
        assert local_provider.download_balance_history("acc_001") == original

    def test_upload_reported_count(self, local_provider):
        result = local_provider.upload_balance_history(
            "acc_001",
            [{"date": "2026-05-01", "balance": 1.0}, {"date": "2026-06-01", "balance": 2.0}],
        )
        assert result["uploaded_count"] == 2


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
