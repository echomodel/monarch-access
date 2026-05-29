"""Account operations."""

import csv
import io
from datetime import date

from .queries import ACCOUNTS_QUERY, UPDATE_ACCOUNT_MUTATION

# Sentinel distinguishing "field not provided" (skip it) from an explicit
# None (set the field to null — e.g. clearing deactivatedAt to reopen an
# account). update_account sends only the fields that differ from UNSET.
UNSET = object()


def is_closed(account: dict) -> bool:
    """Check if an account is closed/deactivated."""
    return bool(account.get("deactivatedAt")) or bool(account.get("isHidden"))


async def get_accounts(client, include_closed: bool = False) -> list[dict]:
    """Get all accounts, excluding closed/deactivated by default."""
    data = await client._request(ACCOUNTS_QUERY)
    accounts = data.get("accounts", [])
    if not include_closed:
        accounts = [a for a in accounts if not is_closed(a)]
    return accounts


async def update_account(
    client,
    account_id: str,
    *,
    name=UNSET,
    deactivated_at=UNSET,
    include_in_net_worth=UNSET,
    hidden=UNSET,
) -> dict:
    """Update an account's settings. Partial — only provided fields change.

    Args:
        account_id: The account to update.
        name: New display name.
        deactivated_at: Close date (YYYY-MM-DD) to close the account, or None
            to reopen it. CLOSING keeps historical balance snapshots in net
            worth and reads $0 from the close date forward; it does NOT
            retroactively remove the account from net worth. Prefer
            close_account() for the common case.
        include_in_net_worth: Set False to EXCLUDE the account from net worth.
            Unlike closing, exclusion removes the balance from net worth
            retroactively, across all of history. Set True to include.
        hidden: Set True to hide the account from the accounts list.

    Returns the updated account.
    """
    from .client import APIError

    input_data: dict = {"id": account_id}
    if name is not UNSET:
        input_data["displayName"] = name
    if deactivated_at is not UNSET:
        input_data["deactivatedAt"] = deactivated_at
    if include_in_net_worth is not UNSET:
        input_data["includeInNetWorth"] = include_in_net_worth
    if hidden is not UNSET:
        input_data["isHidden"] = hidden

    data = await client._request(UPDATE_ACCOUNT_MUTATION, {"input": input_data})
    result = data.get("updateAccount", {})
    if result.get("errors"):
        errors = result["errors"]
        msg = errors.get("message") or str(errors.get("fieldErrors", []))
        raise APIError(f"Update account failed: {msg}")
    return result.get("account", {})


async def close_account(client, account_id: str, close_date: str | None = None) -> dict:
    """Close an account by setting its deactivation date.

    Closing preserves the account's historical balance curve in net worth
    while zeroing its balance from the close date forward — so net worth
    neither double-counts the account going forward nor drops retroactively.
    This is distinct from excluding the account from net worth (see
    update_account's include_in_net_worth), which removes the balance from
    history. Reversible: reopen with update_account(deactivated_at=None).

    Args:
        account_id: The account to close.
        close_date: Close date (YYYY-MM-DD). Defaults to today.

    Returns the updated account.
    """
    return await update_account(
        client, account_id, deactivated_at=close_date or date.today().isoformat()
    )


def format_csv(accounts: list[dict]) -> str:
    """Format accounts as CSV."""
    output = io.StringIO()
    fieldnames = ["id", "name", "type", "balance", "institution", "mask", "status"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for a in accounts:
        writer.writerow({
            "id": a.get("id", ""),
            "name": a.get("displayName", ""),
            "type": (a.get("type") or {}).get("display", ""),
            "balance": a.get("currentBalance", 0),
            "institution": (a.get("institution") or {}).get("name", ""),
            "mask": a.get("mask", ""),
            "status": "closed" if is_closed(a) else "active",
        })
    return output.getvalue()


def format_text(accounts: list[dict]) -> str:
    """Format accounts as ASCII text with table."""
    if not accounts:
        return "No accounts found."

    def fmt_money(amount: float) -> str:
        if amount is None:
            return "$0.00"
        if amount < 0:
            return f"-${abs(amount):,.2f}"
        return f"${amount:,.2f}"

    # Group by type
    by_type: dict[str, list[dict]] = {}
    for acc in accounts:
        acc_type = acc.get("type", {}).get("display", "Other")
        by_type.setdefault(acc_type, []).append(acc)

    lines = []
    lines.append(f"ACCOUNTS ({len(accounts)})")

    col_widths = [30, 18, 14]
    alignments = ["l", "l", "r"]

    def make_table(rows: list[tuple]) -> list[str]:
        result = []
        separator = "+" + "+".join("-" * (w + 2) for w in col_widths) + "+"
        result.append(separator)
        for i, row in enumerate(rows):
            cells = []
            for val, width, align in zip(row, col_widths, alignments):
                text = str(val)[:width]
                if align == "r":
                    cells.append(f" {text:>{width}} ")
                else:
                    cells.append(f" {text:<{width}} ")
            result.append("|" + "|".join(cells) + "|")
            if i == 0:
                result.append(separator)
        result.append(separator)
        return result

    rows = [("Account", "Institution", "Balance")]

    for acc_type in sorted(by_type.keys()):
        accts = by_type[acc_type]
        type_total = sum(a.get("currentBalance", 0) or 0 for a in accts)
        rows.append((f"[{acc_type}]", "", fmt_money(type_total)))
        for acc in sorted(accts, key=lambda x: -abs(x.get("currentBalance", 0) or 0)):
            name = acc.get("displayName", "Unknown")
            if is_closed(acc):
                name = f"  {name} [CLOSED]"
            else:
                name = f"  {name}"
            inst = (acc.get("institution") or {}).get("name", "")
            balance = acc.get("currentBalance", 0) or 0
            rows.append((name, inst[:18], fmt_money(balance)))

    lines.extend(make_table(rows))

    total = sum(a.get("currentBalance", 0) or 0 for a in accounts)
    lines.append("")
    lines.append(f"Total: {fmt_money(total)}")

    return "\n".join(lines)
