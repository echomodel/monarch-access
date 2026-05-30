"""Account balance history operations.

Monarch exposes balance history as CSV over REST: a download endpoint that
returns one row per day from account creation through today, and an upload
endpoint that REPLACES the entire history for an account. Upload is finalized
through two GraphQL steps (parse mutation + session poll).

Balance history is independent of transactions: uploading snapshots does not
create transactions and does not affect income/expense reports — it only sets
the account's balance curve and updates its currentBalance to the final row.
"""

import asyncio
import csv
import hashlib
import io
import json

from .queries import (
    PARSE_BALANCE_HISTORY_MUTATION,
    UPLOAD_BALANCE_HISTORY_SESSION_QUERY,
)


def history_token(snapshots: list[dict]) -> int:
    """Derive a stable digest number from a balance-history snapshot list.

    Upload is a full-history REPLACE, so it is destructive to whatever is
    currently stored. This token is the safety interlock: a caller must read
    the current history (download_balance_history), which returns this token,
    and pass it back to upload_balance_history. Upload recomputes the token
    from the live history and refuses unless they match.

    Two properties this guarantees:
      1. The caller actually read the current history before replacing it — so
         the prior state is captured (in an agent's context, a CSV, etc.) and
         the replace is reversible.
      2. The history hasn't changed since it was read (optimistic concurrency) —
         a stale token is rejected rather than silently clobbering newer data.

    The digest is independent of input ordering (snapshots are sorted) and
    depends only on (date, balance-to-the-cent) pairs. An empty history has its
    own stable token, so uploading to a fresh account still requires a read
    first.
    """
    canonical = [
        [s["date"], round(float(s["balance"]), 2)]
        for s in sorted(snapshots, key=lambda x: x.get("date", ""))
    ]
    blob = json.dumps(canonical, separators=(",", ":"))
    # 48-bit digest — comfortably within JSON-safe integer range, ample for an
    # accidental-change interlock (a read-before-write guard, not cryptographic
    # authentication of the payload).
    return int(hashlib.sha256(blob.encode()).hexdigest()[:12], 16)


def parse_balance_csv(csv_text: str) -> list[dict]:
    """Parse a Monarch balances CSV (Date,Balance,Account) into snapshots.

    Returns a list of {"date": str, "balance": float}. The Account column, if
    present, is ignored — snapshots are per the account the upload targets.
    """
    snapshots: list[dict] = []
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        # Tolerate either capitalized (download) or lowercase headers.
        date_val = row.get("Date") or row.get("date")
        balance_val = row.get("Balance") or row.get("balance")
        if date_val is None or balance_val in (None, ""):
            continue
        snapshots.append({"date": date_val, "balance": float(balance_val)})
    return snapshots


def snapshots_to_csv(snapshots: list[dict]) -> str:
    """Render snapshots as a Date,Balance CSV suitable for upload."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Balance"])
    for s in snapshots:
        writer.writerow([s["date"], s["balance"]])
    return output.getvalue()


async def download_balance_history(client, account_id: str) -> list[dict]:
    """Download the daily balance history for an account.

    Returns a list of {"date": str, "balance": float}, one per day from account
    creation through today. Liabilities carry negative balances.
    """
    csv_text = await client._download_balances([account_id])
    return parse_balance_csv(csv_text)


class BalanceHistoryTokenMismatch(Exception):
    """Raised when the expected_token does not match the account's current history.

    Signals that the caller did not read the current history immediately before
    uploading (or it changed since). The replace is refused so nothing is
    clobbered without the prior state having been captured.
    """


async def upload_balance_history(
    client,
    account_id: str,
    snapshots: list[dict],
    expected_token: int,
    *,
    poll_interval: float = 0.5,
    max_polls: int = 20,
) -> dict:
    """Replace an account's entire balance history with the given snapshots.

    WARNING: this REPLACES all existing balance snapshots for the account and
    sets its currentBalance to the final (latest-dated) row. There is no append
    mode — the upload is the account's whole curve.

    Safety interlock: `expected_token` must equal the digest of the account's
    CURRENT history (the number returned by download_balance_history). This
    forces a read-before-write — the prior state is captured and the replace is
    reversible — and rejects a stale token if the history changed since it was
    read. On mismatch, raises BalanceHistoryTokenMismatch and uploads nothing.

    Handles the full workflow: re-read current → verify token → multipart
    upload → parse mutation → poll the session until processing completes
    (typically < 2s).

    Args:
        account_id: The account whose history to overwrite.
        snapshots: List of {"date": "YYYY-MM-DD", "balance": float}.
        expected_token: The history_token from a prior download_balance_history
            of this same account. Obtain it by reading the current history first.

    Returns:
        {success, status, session_key, uploaded_count, previous_snapshots}.
        previous_snapshots is the replaced history, for rollback.
    """
    from .client import APIError

    # Read current history, verify the caller saw it (token), keep for rollback.
    previous = await download_balance_history(client, account_id)
    actual_token = history_token(previous)
    if expected_token != actual_token:
        raise BalanceHistoryTokenMismatch(
            f"expected_token {expected_token} does not match the account's current "
            f"balance-history token {actual_token}. Call download_balance_history "
            f"for this account to read its current history and obtain the up-to-date "
            f"token, then retry the upload. Nothing was changed."
        )

    csv_text = snapshots_to_csv(snapshots)
    filename = f"balance-history-{account_id}.csv"
    upload_resp = await client._upload_balances(csv_text, account_id, filename)
    session_key = upload_resp.get("session_key")
    if not session_key:
        raise APIError("Balance upload did not return a session_key")

    # Kick off processing.
    await client._request(PARSE_BALANCE_HISTORY_MUTATION, {"input": {"sessionKey": session_key}})

    # Poll until completed.
    status = None
    for _ in range(max_polls):
        data = await client._request(
            UPLOAD_BALANCE_HISTORY_SESSION_QUERY, {"sessionKey": session_key}
        )
        session = data.get("uploadBalanceHistorySession") or {}
        status = session.get("status")
        if status == "completed":
            break
        await asyncio.sleep(poll_interval)

    return {
        "success": status == "completed",
        "status": status,
        "session_key": session_key,
        "uploaded_count": len(snapshots),
        "previous_snapshots": previous,
    }
