"""Tests for transaction file attachments.

Sociable: a complete attach operation runs through the real provider and
real temp files (no mocks). Isolation comes from tmp_path and the
LocalProvider's temp database.
"""

import pytest


def _a_transaction_id(local_provider) -> str:
    return local_provider.get_transactions(limit=1)["results"][0]["id"]


class TestTransactionsAttach:
    def test_attach_file_lands_on_transaction(self, local_provider, tmp_path):
        """Attaching a file records it on the transaction and reflects via get."""
        txn_id = _a_transaction_id(local_provider)
        f = tmp_path / "check_1008_front.png"
        f.write_bytes(b"\x89PNG\r\n" + b"x" * 500)  # 506 bytes

        att = local_provider.attach_transaction(txn_id, str(f))

        # Returned record carries real, file-derived metadata.
        assert att["filename"] == "check_1008_front"      # default = stem, no ext
        assert att["extension"] == "png"
        assert att["sizeBytes"] == 506
        assert att["id"]

        # And it is durably on the transaction.
        fetched = local_provider.get_transaction(txn_id)
        assert any(a["id"] == att["id"] for a in fetched["attachments"])

    def test_attach_custom_display_name(self, local_provider, tmp_path):
        """An explicit filename overrides the file's base name."""
        txn_id = _a_transaction_id(local_provider)
        f = tmp_path / "scan.pdf"
        f.write_bytes(b"%PDF-1.7 ...")

        att = local_provider.attach_transaction(txn_id, str(f), filename="Check 1008 back")

        assert att["filename"] == "Check 1008 back"
        assert att["extension"] == "pdf"

    def test_multiple_attachments_accumulate(self, local_provider, tmp_path):
        """Monarch allows several attachments per transaction; they accumulate."""
        txn_id = _a_transaction_id(local_provider)
        front = tmp_path / "front.png"; front.write_bytes(b"a" * 10)
        back = tmp_path / "back.png"; back.write_bytes(b"b" * 20)

        a1 = local_provider.attach_transaction(txn_id, str(front), filename="front")
        a2 = local_provider.attach_transaction(txn_id, str(back), filename="back")

        fetched = local_provider.get_transaction(txn_id)
        names = [a["filename"] for a in fetched["attachments"]]
        assert "front" in names and "back" in names
        assert a1["id"] != a2["id"]
        assert len(fetched["attachments"]) >= 2

    def test_attach_unknown_transaction_raises(self, local_provider, tmp_path):
        """Attaching to a non-existent transaction raises, attaches nothing."""
        f = tmp_path / "x.png"; f.write_bytes(b"x")
        with pytest.raises(ValueError, match="Transaction not found"):
            local_provider.attach_transaction("nonexistent_id", str(f))

    def test_attach_missing_file_raises(self, local_provider, tmp_path):
        """A missing source file raises before touching the transaction."""
        txn_id = _a_transaction_id(local_provider)
        with pytest.raises(ValueError, match="File not found"):
            local_provider.attach_transaction(txn_id, str(tmp_path / "nope.png"))
