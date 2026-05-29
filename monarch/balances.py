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
import io

from .queries import (
    PARSE_BALANCE_HISTORY_MUTATION,
    UPLOAD_BALANCE_HISTORY_SESSION_QUERY,
)


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


async def upload_balance_history(
    client,
    account_id: str,
    snapshots: list[dict],
    *,
    poll_interval: float = 0.5,
    max_polls: int = 20,
) -> dict:
    """Replace an account's entire balance history with the given snapshots.

    WARNING: this REPLACES all existing balance snapshots for the account and
    sets its currentBalance to the final row. The existing history is
    downloaded and returned under "previous_snapshots" first, so the prior
    state can be restored by uploading it back.

    Handles the full workflow: multipart upload → parse mutation → poll the
    session until processing completes (typically < 2s).

    Args:
        account_id: The account whose history to overwrite.
        snapshots: List of {"date": "YYYY-MM-DD", "balance": float}.

    Returns:
        {success, status, session_key, uploaded_count, previous_snapshots}.
    """
    from .client import APIError

    # Cache existing history for rollback before overwriting.
    try:
        previous = await download_balance_history(client, account_id)
    except Exception:
        previous = None

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
