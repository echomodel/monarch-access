#!/usr/bin/env python3
"""Monarch Money CLI."""

import fnmatch
import json
import sys
from typing import Optional

import click

from . import accounts, net_worth, transactions
from .client import AuthenticationError, APIError
from .providers import get_provider


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """Monarch Money CLI - Access your financial data."""
    pass


@cli.group("transactions")
def transactions_group():
    """Transaction commands."""
    pass


@transactions_group.command("list")
@click.option("--format", "output_format", type=click.Choice(["text", "json", "csv"]), default="text", help="Output format")
@click.option("--account", multiple=True, help="Filter by account name (comma-separated or multiple flags)")
@click.option("--category", multiple=True, help="Filter by category name (comma-separated or multiple flags)")
@click.option("--start", "start_date", help="Start date, inclusive (YYYY-MM-DD)")
@click.option("--end", "end_date", help="End date, inclusive (YYYY-MM-DD)")
@click.option("--merchant", help="Filter by merchant name (supports * wildcards)")
@click.option("--notes", help="Filter by notes content (supports * wildcards)")
@click.option("--original-statement", "original_statement", help="Filter by original statement (supports * wildcards)")
@click.option("--limit", default=1000, help="Max transactions to fetch")
def list_transactions(
    output_format: str,
    account: tuple,
    category: tuple,
    start_date: Optional[str],
    end_date: Optional[str],
    merchant: Optional[str],
    notes: Optional[str],
    original_statement: Optional[str],
    limit: int,
):
    """List transactions with optional filters."""
    try:
        result = _list_transactions(
            output_format, account, category, start_date, end_date,
            merchant, notes, original_statement, limit
        )
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)


def _list_transactions(
    output_format: str,
    account: tuple,
    category: tuple,
    start_date: Optional[str],
    end_date: Optional[str],
    merchant: Optional[str],
    notes: Optional[str],
    original_statement: Optional[str],
    limit: int,
) -> str:
    """Implementation of list transactions."""
    provider = get_provider()

    # Parse comma-separated values from options
    account_names = _parse_multi_option(account)
    category_names = _parse_multi_option(category)

    # Get account IDs if filtering by account name
    account_ids = None
    if account_names:
        accts = provider.get_accounts()
        account_ids = [
            a["id"] for a in accts
            if any(fnmatch.fnmatch(a["displayName"].lower(), name.lower()) for name in account_names)
        ]
        if not account_ids:
            return json.dumps({"error": f"No accounts matching: {account_names}"})

    # Get category IDs if filtering by category name
    category_ids = None
    if category_names:
        cats = provider.get_categories()
        category_ids = [
            c["id"] for c in cats
            if any(fnmatch.fnmatch(c["name"].lower(), name.lower()) for name in category_names)
        ]
        if not category_ids:
            return json.dumps({"error": f"No categories matching: {category_names}"})

    # Fetch transactions
    data = provider.get_transactions(
        limit=limit,
        start_date=start_date,
        end_date=end_date,
        account_ids=account_ids,
        category_ids=category_ids,
    )

    txns = data.get("results", [])
    total_count = data.get("totalCount", 0)

    # Apply client-side filters (merchant, notes, original_statement)
    if merchant:
        txns = [t for t in txns if _wildcard_match((t.get("merchant") or {}).get("name", ""), merchant)]
    if notes:
        txns = [t for t in txns if _wildcard_match(t.get("notes") or "", notes)]
    if original_statement:
        txns = [t for t in txns if _wildcard_match(t.get("plaidName") or "", original_statement)]

    # Check if there are more results than returned
    truncated = total_count > limit

    # Format output
    if output_format == "json":
        result = {"transactions": txns, "count": len(txns), "total": total_count}
        if truncated:
            result["truncated"] = True
            result["message"] = f"Showing {limit} of {total_count} transactions. Use --limit to fetch more."
        return json.dumps(result, indent=2, default=str)
    elif output_format == "csv":
        output = transactions.format_csv(txns)
        if truncated:
            output += f"\n# Showing {limit} of {total_count} transactions. Use --limit to fetch more.\n"
        return output
    else:
        output = transactions.format_text(txns)
        if truncated:
            output += f"\n\n(Showing {limit} of {total_count} transactions. Use --limit to fetch more.)"
        return output


def _parse_multi_option(values: tuple) -> list[str]:
    """Parse comma-separated values from multiple option flags."""
    result = []
    for val in values:
        result.extend([v.strip() for v in val.split(",") if v.strip()])
    return result


def _wildcard_match(text: str, pattern: str) -> bool:
    """Match text against pattern with * wildcard support."""
    return fnmatch.fnmatch(text.lower(), pattern.lower())


@transactions_group.command("get")
@click.argument("transaction_id")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def get_transaction(transaction_id: str, output_format: str):
    """Get a single transaction by ID."""
    try:
        result = _get_transaction(transaction_id, output_format)
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)


def _get_transaction(transaction_id: str, output_format: str) -> str:
    """Implementation of get transaction."""
    provider = get_provider()
    txn = provider.get_transaction(transaction_id)

    if not txn:
        return json.dumps({"error": f"Transaction not found: {transaction_id}"})

    if output_format == "json":
        return json.dumps(txn, indent=2, default=str)
    else:
        return transactions.format_single_text(txn)


@transactions_group.command("mark-reviewed")
@click.argument("transaction_ids")
@click.option("--undo", is_flag=True, help="Mark as needing review instead")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def mark_reviewed(transaction_ids: str, undo: bool, output_format: str):
    """Mark transactions as reviewed (or needing review with --undo). Accepts comma-separated IDs."""
    try:
        result = _mark_reviewed(transaction_ids, undo, output_format)
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)


def _mark_reviewed(transaction_ids: str, undo: bool, output_format: str) -> str:
    """Implementation of mark-reviewed."""
    provider = get_provider()
    ids = [id.strip() for id in transaction_ids.split(",") if id.strip()]

    if not ids:
        return json.dumps({"error": "No transaction IDs provided"})

    needs_review = undo  # --undo means set needsReview=True
    results = []
    for tid in ids:
        try:
            provider.update_transaction(transaction_id=tid, needs_review=needs_review)
            results.append({"id": tid, "success": True})
        except APIError as e:
            results.append({"id": tid, "success": False, "error": str(e)})

    success_count = sum(1 for r in results if r["success"])
    action = "needing review" if undo else "reviewed"

    if output_format == "json":
        return json.dumps({"results": results, "success_count": success_count, "total": len(ids)}, indent=2)
    else:
        return f"Marked {success_count}/{len(ids)} transactions as {action}"


@transactions_group.command("split")
@click.argument("transaction_id")
@click.option("--splits", required=True, help='JSON array of splits: [{"amount": -10.00, "categoryId": "123", "notes": "..."}]')
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def split_transaction(transaction_id: str, splits: str, output_format: str):
    """Split a transaction into multiple parts.

    The sum of split amounts must equal the original transaction amount.
    Each split needs: amount (negative for expenses), categoryId.
    Optional: merchantName, notes.
    """
    try:
        result = _split_transaction(transaction_id, splits, output_format)
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)
    except json.JSONDecodeError as e:
        click.echo(f"Invalid JSON for splits: {e}", err=True)
        sys.exit(1)


def _split_transaction(transaction_id: str, splits: str, output_format: str) -> str:
    """Implementation of split transaction."""
    provider = get_provider()
    split_data = json.loads(splits)

    result = provider.split_transaction(transaction_id, split_data)

    if output_format == "json":
        return json.dumps(result, indent=2, default=str)
    else:
        splits_info = result.get("splitTransactions", [])
        lines = [f"Transaction {transaction_id} split into {len(splits_info)} parts:"]
        for s in splits_info:
            cat = s.get("category", {}).get("name", "Unknown")
            amt = s.get("amount", 0)
            notes = s.get("notes", "")
            lines.append(f"  ${abs(amt):.2f} -> {cat}" + (f" ({notes})" if notes else ""))
        return "\n".join(lines)


@transactions_group.command("update")
@click.argument("transaction_id")
@click.option("--category", help="Category name to set")
@click.option("--merchant", help="Merchant name to set")
@click.option("--notes", help="Notes to set (use empty string to clear)")
@click.option("--needs-review", type=bool, default=None, help="Set needs review flag (true/false)")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def update_transaction(
    transaction_id: str,
    category: Optional[str],
    merchant: Optional[str],
    notes: Optional[str],
    needs_review: Optional[bool],
    output_format: str,
):
    """Update a transaction by ID. Only specified fields are changed."""
    try:
        result = _update_transaction(
            transaction_id, category, merchant, notes, needs_review, output_format
        )
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)


@transactions_group.command("create")
@click.option("--date", required=True, help="Transaction date (YYYY-MM-DD)")
@click.option("--account", required=True, help="Account name or ID")
@click.option("--amount", required=True, type=float, help="Amount (negative for expenses)")
@click.option("--merchant", required=True, help="Merchant/payee name")
@click.option("--category", required=True, help="Category name")
@click.option("--notes", default="", help="Optional notes")
@click.option("--update-balance", is_flag=True, help="Update account balance")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def create_transaction(
    date: str,
    account: str,
    amount: float,
    merchant: str,
    category: str,
    notes: str,
    update_balance: bool,
    output_format: str,
):
    """Create a new manual transaction."""
    try:
        result = _create_transaction(
            date, account, amount, merchant, category, notes, update_balance, output_format
        )
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)


def _create_transaction(
    date: str,
    account: str,
    amount: float,
    merchant: str,
    category: str,
    notes: str,
    update_balance: bool,
    output_format: str,
) -> str:
    """Implementation of create transaction."""
    provider = get_provider()

    # Resolve account name to ID if not already an ID
    account_id = account
    if not account.isdigit():
        accts = provider.get_accounts()
        matching = [a for a in accts if a["displayName"].lower() == account.lower()]
        if not matching:
            # Try partial match
            matching = [a for a in accts if account.lower() in a["displayName"].lower()]
        if not matching:
            return json.dumps({"error": f"Account not found: {account}"})
        account_id = matching[0]["id"]

    # Resolve category name to ID
    cats = provider.get_categories()
    matching_cat = [c for c in cats if c["name"].lower() == category.lower()]
    if not matching_cat:
        # Try partial match
        matching_cat = [c for c in cats if category.lower() in c["name"].lower()]
    if not matching_cat:
        return json.dumps({"error": f"Category not found: {category}"})
    category_id = matching_cat[0]["id"]

    # Create the transaction
    created = provider.create_transaction(
        date=date,
        account_id=account_id,
        amount=amount,
        merchant_name=merchant,
        category_id=category_id,
        notes=notes,
        update_balance=update_balance,
    )

    if output_format == "json":
        return json.dumps(created, indent=2, default=str)
    else:
        return transactions.format_single_text(created)


def _update_transaction(
    transaction_id: str,
    category: Optional[str],
    merchant: Optional[str],
    notes: Optional[str],
    needs_review: Optional[bool],
    output_format: str,
) -> str:
    """Implementation of update transaction."""
    provider = get_provider()

    # Resolve category name to ID if provided
    category_id = None
    if category is not None:
        cats = provider.get_categories()
        matching = [c for c in cats if c["name"].lower() == category.lower()]
        if not matching:
            # Try partial match
            matching = [c for c in cats if category.lower() in c["name"].lower()]
        if not matching:
            return json.dumps({"error": f"Category not found: {category}"})
        category_id = matching[0]["id"]

    # Perform update
    updated = provider.update_transaction(
        transaction_id=transaction_id,
        category_id=category_id,
        merchant_name=merchant,
        notes=notes,
        needs_review=needs_review,
    )

    # Format output
    if output_format == "json":
        return json.dumps(updated, indent=2, default=str)
    else:
        return transactions.format_single_text(updated)


@cli.command("accounts")
@click.option("--format", "output_format", type=click.Choice(["text", "json", "csv"]), default="text", help="Output format")
def list_accounts(output_format: str):
    """List all accounts."""
    try:
        result = _list_accounts(output_format)
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)


def _list_accounts(output_format: str) -> str:
    """Implementation of list accounts."""
    provider = get_provider()
    accts = provider.get_accounts()

    if output_format == "json":
        return json.dumps(accts, indent=2, default=str)
    elif output_format == "csv":
        return accounts.format_csv(accts)
    else:
        return accounts.format_text(accts)


@cli.command("categories")
@click.option("--format", "output_format", type=click.Choice(["text", "json"]), default="text", help="Output format")
def list_categories(output_format: str):
    """List all transaction categories."""
    try:
        result = _list_categories(output_format)
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)


def _list_categories(output_format: str) -> str:
    """Implementation of list categories."""
    provider = get_provider()
    cats = provider.get_categories()

    if output_format == "json":
        return json.dumps(cats, indent=2, default=str)
    else:
        # Text format - group by category group
        lines = []
        lines.append(f"CATEGORIES ({len(cats)})")
        lines.append("-" * 40)

        by_group: dict[str, list] = {}
        for cat in cats:
            group_name = cat.get("group", {}).get("name", "Other")
            by_group.setdefault(group_name, []).append(cat)

        for group_name in sorted(by_group.keys()):
            group_cats = by_group[group_name]
            group_type = group_cats[0].get("group", {}).get("type", "")
            lines.append(f"\n[{group_name}] ({group_type})")
            for cat in sorted(group_cats, key=lambda c: c["name"]):
                lines.append(f"  {cat['name']}")

        return "\n".join(lines)


@cli.command("auth")
@click.argument("token")
def auth(token: str):
    """Save authentication token."""
    from .client import MonarchClient
    client = MonarchClient(token=token)
    client.save_token()
    click.echo(f"Token saved to {client._token_file}")


@cli.command("net-worth")
@click.option("--format", "output_format", type=click.Choice(["text", "json", "csv"]), default="text", help="Output format")
def net_worth_cmd(output_format: str):
    """Show net worth report with assets and liabilities."""
    try:
        result = _net_worth(output_format)
        click.echo(result)
    except AuthenticationError as e:
        click.echo(f"Authentication error: {e}", err=True)
        sys.exit(1)
    except APIError as e:
        click.echo(f"API error: {e}", err=True)
        sys.exit(1)


def _net_worth(output_format: str) -> str:
    """Implementation of net worth."""
    provider = get_provider()
    accts = provider.get_accounts()
    report = net_worth.build_report(accts)

    if output_format == "json":
        return json.dumps(report, indent=2)
    elif output_format == "csv":
        return net_worth.format_csv(report)
    else:
        return net_worth.format_text(report)


if __name__ == "__main__":
    cli()
