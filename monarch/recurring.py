"""Recurring transaction utilities."""

import calendar
import csv
import io
from datetime import date
from typing import Any, Optional

from .queries import RECURRING_TRANSACTION_ITEMS_QUERY


async def get_recurring_transaction_items(
    client,
    start_date: str,
    end_date: str,
) -> list[dict]:
    """Get raw recurring transaction items for a date range."""
    variables: dict[str, Any] = {
        "startDate": start_date,
        "endDate": end_date,
    }

    data = await client._request(RECURRING_TRANSACTION_ITEMS_QUERY, variables)
    return data.get("recurringTransactionItems", [])


def _current_month_range() -> tuple[str, str]:
    """Return (start_date, end_date) for the current month."""
    today = date.today()
    start = today.replace(day=1).isoformat()
    last_day = calendar.monthrange(today.year, today.month)[1]
    end = today.replace(day=last_day).isoformat()
    return start, end


def _trailing_year_range() -> tuple[str, str]:
    """Return (start_date, end_date) spanning 12 months back through current month."""
    today = date.today()
    start = today.replace(year=today.year - 1, day=1).isoformat()
    last_day = calendar.monthrange(today.year, today.month)[1]
    end = today.replace(day=last_day).isoformat()
    return start, end


def collapse_to_streams(items: list[dict]) -> list[dict]:
    """Collapse recurring items into one entry per stream.

    Takes the raw recurring transaction items (which are date-specific
    occurrences) and deduplicates by stream ID, producing a stable list
    of recurring obligations.

    For each stream, tracks:
    - Current month's occurrence (due_date, is_past, transaction_id)
    - Last paid date across all items (last_paid_date)
    """
    streams: dict[str, dict] = {}

    # Sort items by date so we process in chronological order
    sorted_items = sorted(items, key=lambda i: i.get("date", ""))

    for item in sorted_items:
        stream = item.get("stream", {})
        stream_id = stream.get("id")
        if not stream_id:
            continue

        is_paid = item.get("transactionId") is not None
        item_date = item.get("date", "")

        if stream_id not in streams:
            merchant = stream.get("merchant") or {}
            streams[stream_id] = {
                "stream_id": stream_id,
                "merchant": merchant.get("name", ""),
                "merchant_id": merchant.get("id", ""),
                "amount": stream.get("amount"),
                "frequency": stream.get("frequency", ""),
                "is_approximate": stream.get("isApproximate", False),
                "category": (item.get("category") or {}).get("name", ""),
                "category_id": (item.get("category") or {}).get("id", ""),
                "account": (item.get("account") or {}).get("displayName", ""),
                "account_id": (item.get("account") or {}).get("id", ""),
                "is_past": item.get("isPast", False),
                "due_date": item_date,
                "actual_amount": item.get("amount"),
                "transaction_id": item.get("transactionId"),
                "last_paid_date": item_date if is_paid else None,
            }
        else:
            existing = streams[stream_id]

            # Track last paid date across all occurrences
            if is_paid and (existing["last_paid_date"] is None or item_date > existing["last_paid_date"]):
                existing["last_paid_date"] = item_date

            # Most recent item becomes the current occurrence
            if item_date > existing["due_date"]:
                existing["is_past"] = item.get("isPast", False)
                existing["due_date"] = item_date
                existing["actual_amount"] = item.get("amount")
                existing["transaction_id"] = item.get("transactionId")

    # Sort by merchant name for stable output
    return sorted(streams.values(), key=lambda s: s.get("merchant", "").lower())


def _display_status(s: dict) -> str:
    """Human-readable status for text/CSV display."""
    if s.get("transaction_id") is not None:
        return "PAID"
    elif s.get("is_past"):
        return "OVERDUE"
    else:
        return "UPCOMING"


def format_text(streams: list[dict]) -> str:
    """Format collapsed stream list as ASCII text table."""
    if not streams:
        return "No recurring items found."

    def fmt_money(amount) -> str:
        if amount is None:
            return ""
        amount = float(amount)
        if amount < 0:
            return f"-${abs(amount):,.2f}"
        return f"${amount:,.2f}"

    lines = []
    lines.append(f"RECURRING ({len(streams)})")

    col_widths = [24, 12, 10, 10, 10]
    alignments = ["l", "r", "l", "l", "l"]

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

    rows = [("Merchant", "Amount", "Due Date", "Last Paid", "Status")]

    for s in streams:
        rows.append((
            s.get("merchant", "")[:24],
            fmt_money(s.get("amount")),
            s.get("due_date", "")[:10],
            (s.get("last_paid_date") or "never")[:10],
            _display_status(s),
        ))

    lines.extend(make_table(rows))

    total = sum(float(s.get("amount") or 0) for s in streams)
    paid = sum(1 for s in streams if s.get("transaction_id") is not None)
    overdue = sum(1 for s in streams if s.get("is_past") and s.get("transaction_id") is None)
    upcoming = sum(1 for s in streams if not s.get("is_past") and s.get("transaction_id") is None)
    lines.append("")
    lines.append(f"Monthly total: {fmt_money(total)}  |  Paid: {paid}  Overdue: {overdue}  Upcoming: {upcoming}")

    return "\n".join(lines)


def format_csv(streams: list[dict]) -> str:
    """Format collapsed stream list as CSV."""
    if not streams:
        return ""

    output = io.StringIO()
    fieldnames = [
        "merchant", "amount", "frequency", "category", "account",
        "due_date", "last_paid_date", "is_past", "transaction_id", "stream_id",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()

    for s in streams:
        writer.writerow({
            "merchant": s.get("merchant", ""),
            "amount": s.get("amount", ""),
            "frequency": s.get("frequency", ""),
            "category": s.get("category", ""),
            "account": s.get("account", ""),
            "due_date": s.get("due_date", ""),
            "last_paid_date": s.get("last_paid_date", ""),
            "is_past": s.get("is_past", False),
            "transaction_id": s.get("transaction_id", ""),
            "stream_id": s.get("stream_id", ""),
        })

    return output.getvalue()
