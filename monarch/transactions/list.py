"""List transactions."""

import csv
import io
from typing import Any, Optional

from ..queries import TRANSACTIONS_QUERY


async def get_transactions(
    client,
    limit: int = 100,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    account_ids: Optional[list[str]] = None,
    category_ids: Optional[list[str]] = None,
    search: Optional[str] = None,
    is_expense: Optional[bool] = None,
) -> dict:
    """Get transactions with optional filters.

    Args:
        is_expense: Filter by amount sign, matching Monarch's rule terminology.
            True = negative amounts (charges, withdrawals, payments made).
            False = positive amounts (deposits, refunds, payments received).
            None = all transactions.
            Note: this filters on amount sign, not category type. A refund
            on an expense category has a positive amount, so is_expense=False.
    """
    variables: dict[str, Any] = {
        "limit": limit,
        "offset": offset,
        "filters": {
            "accounts": account_ids or [],
            "categories": category_ids or [],
        }
    }

    if search:
        variables["filters"]["search"] = search

    # Add date filters if provided
    if start_date:
        variables["filters"]["startDate"] = start_date
    if end_date:
        variables["filters"]["endDate"] = end_date

    data = await client._request(TRANSACTIONS_QUERY, variables)
    result = data.get("allTransactions", {"totalCount": 0, "results": []})

    if is_expense is not None:
        results = result.get("results", [])
        if is_expense:
            results = [t for t in results if (t.get("amount") or 0) < 0]
        else:
            results = [t for t in results if (t.get("amount") or 0) > 0]
        result = {
            "totalCount": result.get("totalCount", 0),
            "results": results,
        }

    return result


def format_csv(transactions: list[dict]) -> str:
    """Format transactions as CSV."""
    if not transactions:
        return ""

    output = io.StringIO()
    fieldnames = ["date", "account", "merchant", "category", "amount", "notes", "original_statement"]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for t in transactions:
        writer.writerow({
            "date": t.get("date", ""),
            "account": t.get("account", {}).get("displayName", ""),
            "merchant": t.get("merchant", {}).get("name", ""),
            "category": t.get("category", {}).get("name", ""),
            "amount": t.get("amount", 0),
            "notes": t.get("notes", ""),
            "original_statement": t.get("plaidName", ""),
        })

    return output.getvalue()


def format_text(transactions: list[dict]) -> str:
    """Format transactions as ASCII text with table."""
    if not transactions:
        return "No transactions found."

    def fmt_money(amount: float) -> str:
        if amount is None:
            return "$0.00"
        if amount < 0:
            return f"-${abs(amount):,.2f}"
        return f"${amount:,.2f}"

    lines = []
    lines.append(f"TRANSACTIONS ({len(transactions)})")

    col_widths = [10, 24, 20, 12]
    alignments = ["l", "l", "l", "r"]

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

    rows = [("Date", "Merchant", "Category", "Amount")]

    for t in transactions:
        date = t.get("date", "")
        merchant = (t.get("merchant") or {}).get("name", "") or t.get("plaidName", "")[:24]
        category = (t.get("category") or {}).get("name", "")
        amount = t.get("amount", 0) or 0
        rows.append((date, merchant[:24], category[:20], fmt_money(amount)))

    lines.extend(make_table(rows))

    total = sum(t.get("amount", 0) or 0 for t in transactions)
    lines.append("")
    lines.append(f"Total: {fmt_money(total)}")

    return "\n".join(lines)
