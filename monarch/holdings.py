"""Investment holdings operations.

Reads security-level positions inside investment/brokerage accounts via
Monarch's `Web_GetHoldings` portfolio query. Account balances answer "how
much is this account worth"; holdings answer "which securities, how many
shares, and at what cost basis".
"""

import csv
import io
from datetime import date

from .queries import HOLDINGS_QUERY


def normalize_holding(node: dict) -> dict:
    """Flatten one aggregateHoldings node into a documented holdings model.

    A node is Monarch's per-security aggregate. It carries the rolled-up
    quantity/cost/value plus a `security` descriptor and a `holdings[]` array
    of the underlying lots/positions. Each lot can carry `taxLots[]`
    (acquisition quantity + cost basis per unit). We surface the aggregate
    figures alongside a flattened `tax_lots` list pulled from every lot.

    `cost_basis` may be null: synced positions where the data provider did
    not supply basis come back without it.
    """
    security = node.get("security") or {}
    sub_holdings = node.get("holdings") or []

    tax_lots: list[dict] = []
    is_manual = False
    for h in sub_holdings:
        if h.get("isManual"):
            is_manual = True
        for lot in h.get("taxLots") or []:
            tax_lots.append({
                "acquisition_quantity": lot.get("acquisitionQuantity"),
                "cost_basis_per_unit": lot.get("costBasisPerUnit"),
            })

    return {
        "id": node.get("id"),
        "ticker": security.get("ticker"),
        "name": security.get("name"),
        "type": security.get("typeDisplay") or security.get("type"),
        "quantity": node.get("quantity"),
        "closing_price": security.get("closingPrice"),
        "current_price": security.get("currentPrice"),
        "current_value": node.get("totalValue"),
        "cost_basis": node.get("costBasis"),
        "day_change_dollars": node.get("securityPriceChangeDollars"),
        "day_change_percent": node.get("securityPriceChangePercent"),
        "is_manual": is_manual,
        "last_synced_at": node.get("lastSyncedAt"),
        "tax_lots": tax_lots,
    }


def normalize_portfolio(data: dict) -> list[dict]:
    """Normalize the raw Web_GetHoldings response into a flat holdings list."""
    portfolio = data.get("portfolio") or {}
    aggregate = portfolio.get("aggregateHoldings") or {}
    edges = aggregate.get("edges") or []
    return [normalize_holding(edge["node"]) for edge in edges if edge.get("node")]


async def get_holdings(
    client,
    account_ids: list[str] | None = None,
    as_of_date: str | None = None,
) -> list[dict]:
    """Get security-level holdings for one or more investment accounts.

    Args:
        account_ids: Investment account IDs to filter by. Omit (or pass None)
            to return the whole portfolio's aggregated holdings.
        as_of_date: YYYY-MM-DD. When given, queries that date's snapshot via
            the PortfolioInput date range, enabling historical position
            lookups. Defaults to today.

    Returns a list of normalized holdings (see `normalize_holding`).
    """
    snapshot_date = as_of_date or date.today().isoformat()
    portfolio_input: dict = {
        "includeHiddenHoldings": True,
        "startDate": snapshot_date,
        "endDate": snapshot_date,
        "topMoversLimit": 4,
    }
    if account_ids:
        portfolio_input["accountIds"] = account_ids

    data = await client._request(HOLDINGS_QUERY, {"input": portfolio_input})
    return normalize_portfolio(data)


def format_csv(holdings: list[dict]) -> str:
    """Format holdings as CSV."""
    output = io.StringIO()
    fieldnames = [
        "ticker", "name", "type", "quantity", "closing_price",
        "current_value", "cost_basis", "is_manual", "tax_lots",
    ]
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for h in holdings:
        writer.writerow({
            "ticker": h.get("ticker", ""),
            "name": h.get("name", ""),
            "type": h.get("type", ""),
            "quantity": h.get("quantity", ""),
            "closing_price": h.get("closing_price", ""),
            "current_value": h.get("current_value", ""),
            "cost_basis": h.get("cost_basis", ""),
            "is_manual": h.get("is_manual", False),
            "tax_lots": len(h.get("tax_lots") or []),
        })
    return output.getvalue()


def format_text(holdings: list[dict]) -> str:
    """Format holdings as an ASCII table."""
    if not holdings:
        return "No holdings found."

    def fmt_money(amount) -> str:
        if amount is None:
            return ""
        amount = float(amount)
        if amount < 0:
            return f"-${abs(amount):,.2f}"
        return f"${amount:,.2f}"

    def fmt_qty(qty) -> str:
        if qty is None:
            return ""
        return f"{float(qty):,.4f}".rstrip("0").rstrip(".")

    lines = [f"HOLDINGS ({len(holdings)})"]

    col_widths = [8, 24, 12, 14, 14]
    alignments = ["l", "l", "r", "r", "r"]

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

    rows = [("Ticker", "Name", "Quantity", "Value", "Cost Basis")]
    for h in sorted(holdings, key=lambda x: -(float(x.get("current_value") or 0))):
        rows.append((
            h.get("ticker") or "",
            h.get("name") or "",
            fmt_qty(h.get("quantity")),
            fmt_money(h.get("current_value")),
            fmt_money(h.get("cost_basis")),
        ))

    lines.extend(make_table(rows))

    total_value = sum(float(h.get("current_value") or 0) for h in holdings)
    total_basis = sum(float(h.get("cost_basis") or 0) for h in holdings)
    lines.append("")
    lines.append(f"Total value: {fmt_money(total_value)}  |  Total cost basis: {fmt_money(total_basis)}")

    return "\n".join(lines)
