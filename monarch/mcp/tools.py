"""MCP tools for Monarch Money financial data access.

Plain async functions — discovered and registered by mcp-app.
Function names become tool names, docstrings become descriptions,
type hints become schemas. All business logic lives in MonarchSDK.
"""

import logging
from typing import Any, Optional

from ..client import MonarchSDK, AuthenticationError, APIError

logger = logging.getLogger(__name__)
sdk = MonarchSDK


async def list_accounts() -> dict[str, Any]:
    """List all financial accounts from Monarch Money.

    Returns account IDs, names, types, balances, and institution names.
    Use account IDs with list_transactions to filter by account.
    """
    try:
        return await sdk.get_accounts()
    except AuthenticationError as e:
        return {"error": str(e), "accounts": [], "count": 0}
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        return {"error": str(e), "accounts": [], "count": 0}


async def list_categories() -> dict[str, Any]:
    """List all transaction categories from Monarch Money.

    Returns category IDs, names, and group information.
    Use category IDs with list_transactions to filter or update_transaction to recategorize.
    """
    try:
        return await sdk.get_categories()
    except AuthenticationError as e:
        return {"error": str(e), "categories": [], "count": 0}
    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        return {"error": str(e), "categories": [], "count": 0}


async def list_transactions(
    limit: int = 100,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    account_ids: Optional[list[str]] = None,
    category_ids: Optional[list[str]] = None,
    search: Optional[str] = None,
) -> dict[str, Any]:
    """List transactions from Monarch Money with optional filters.

    Filter by date range, accounts, categories, or search text.
    Returns transaction details including amounts, merchants, categories, and notes.

    Args:
        limit: Maximum number of transactions to return (default: 100, max: 1000).
        start_date: Start date filter, inclusive (YYYY-MM-DD format).
        end_date: End date filter, inclusive (YYYY-MM-DD format).
        account_ids: List of account IDs to filter by. Get IDs from list_accounts.
        category_ids: List of category IDs to filter by. Get IDs from list_categories.
        search: Search text to filter by merchant name, notes, or description.
    """
    try:
        return await sdk.get_transactions(
            limit=max(1, min(1000, limit)),
            start_date=start_date,
            end_date=end_date,
            account_ids=account_ids,
            category_ids=category_ids,
            search=search,
        )
    except AuthenticationError as e:
        return {"error": str(e), "transactions": [], "count": 0, "totalCount": 0}
    except Exception as e:
        logger.error(f"Error listing transactions: {e}")
        return {"error": str(e), "transactions": [], "count": 0, "totalCount": 0}


async def get_transaction(
    transaction_id: str,
) -> dict[str, Any]:
    """Get details of a single transaction by ID.

    Returns full transaction data including amount, merchant, category,
    account, notes, and tags.

    Args:
        transaction_id: The ID of the transaction to retrieve.
    """
    try:
        return await sdk.get_transaction(transaction_id)
    except AuthenticationError as e:
        return {"error": str(e), "transaction": None, "success": False}
    except Exception as e:
        logger.error(f"Error getting transaction: {e}")
        return {"error": str(e), "transaction": None, "success": False}


async def update_transaction(
    transaction_id: str,
    category_id: Optional[str] = None,
    merchant_name: Optional[str] = None,
    notes: Optional[str] = None,
    needs_review: Optional[bool] = None,
    hide_from_reports: Optional[bool] = None,
) -> dict[str, Any]:
    """Update a transaction's category, merchant name, notes, or review status.

    Only specified fields are updated; others remain unchanged.

    Args:
        transaction_id: The ID of the transaction to update.
        category_id: New category ID to assign. Get IDs from list_categories.
        merchant_name: New merchant name to set.
        notes: Notes to add or update. Use empty string to clear notes.
        needs_review: Set to true to mark as needing review, false to mark as reviewed.
        hide_from_reports: Set to true to hide from reports/budgets, false to include.
    """
    try:
        return await sdk.update_transaction(
            transaction_id,
            category_id=category_id,
            merchant_name=merchant_name,
            notes=notes,
            needs_review=needs_review,
            hide_from_reports=hide_from_reports,
        )
    except (AuthenticationError, APIError) as e:
        return {"error": str(e), "transaction": None, "success": False}
    except Exception as e:
        logger.error(f"Error updating transaction: {e}")
        return {"error": str(e), "transaction": None, "success": False}


async def mark_transactions_reviewed(
    transaction_ids: list[str],
    needs_review: bool = False,
) -> dict[str, Any]:
    """Mark one or more transactions as reviewed (or needing review).

    Useful for bulk operations after reviewing transactions.

    Args:
        transaction_ids: List of transaction IDs to update.
        needs_review: Set to false (default) to mark as reviewed, true to mark as needing review.
    """
    try:
        if not transaction_ids:
            return {"success": False, "error": "No transaction IDs provided", "affectedCount": 0}
        return await sdk.bulk_mark_reviewed(transaction_ids, needs_review)
    except (AuthenticationError, APIError) as e:
        return {"error": str(e), "success": False, "affectedCount": 0}
    except Exception as e:
        logger.error(f"Error marking transactions: {e}")
        return {"error": str(e), "success": False, "affectedCount": 0}


async def split_transaction(
    transaction_id: str,
    splits: list[dict],
) -> dict[str, Any]:
    """Split a transaction into multiple parts with different categories.

    The sum of split amounts must equal the original transaction amount.

    Args:
        transaction_id: The ID of the transaction to split.
        splits: Array of split objects. Each must have "amount" (float, negative for expenses) and "categoryId" (string). Optional: "merchantName", "notes".
    """
    try:
        return await sdk.split_transaction(transaction_id, splits)
    except (AuthenticationError, APIError) as e:
        return {"error": str(e), "transaction": None, "success": False}
    except Exception as e:
        logger.error(f"Error splitting transaction: {e}")
        return {"error": str(e), "transaction": None, "success": False}


async def create_transaction(
    date: str,
    account_id: str,
    amount: float,
    merchant_name: str,
    category_id: str,
    notes: Optional[str] = "",
    update_balance: bool = False,
) -> dict[str, Any]:
    """Create a new manual transaction in Monarch Money.

    Use for adding transactions to manual accounts like tracking gifts,
    loans, or other financial events not captured by linked accounts.

    Args:
        date: Transaction date in YYYY-MM-DD format.
        account_id: The ID of the account. Must be a manual account. Get IDs from list_accounts.
        amount: Transaction amount. Negative for expenses, positive for income.
        merchant_name: Name of the merchant or payee.
        category_id: Category ID. Get IDs from list_categories.
        notes: Optional notes or description.
        update_balance: Whether to update the account balance.
    """
    try:
        return await sdk.create_transaction(
            date=date,
            account_id=account_id,
            amount=amount,
            merchant_name=merchant_name,
            category_id=category_id,
            notes=notes or "",
            update_balance=update_balance,
        )
    except (AuthenticationError, APIError) as e:
        return {"error": str(e), "transaction": None, "success": False}
    except Exception as e:
        logger.error(f"Error creating transaction: {e}")
        return {"error": str(e), "transaction": None, "success": False}


async def delete_transaction(
    transaction_id: str,
) -> dict[str, Any]:
    """Delete a transaction from Monarch Money. This action cannot be undone.

    Args:
        transaction_id: The ID of the transaction to delete.
    """
    try:
        return await sdk.delete_transaction(transaction_id)
    except (AuthenticationError, APIError) as e:
        return {"error": str(e), "deleted": False, "success": False}
    except Exception as e:
        logger.error(f"Error deleting transaction: {e}")
        return {"error": str(e), "deleted": False, "success": False}


async def list_recurring() -> dict[str, Any]:
    """List tracked recurring obligations from Monarch Money.

    Returns bills, subscriptions, loan payments, and credit card payments.
    Each item includes merchant, expected amount, frequency, category,
    account, and whether this month's payment has been made.
    """
    try:
        return await sdk.get_recurring()
    except AuthenticationError as e:
        return {"error": str(e), "recurring": [], "count": 0}
    except Exception as e:
        logger.error(f"Error listing recurring items: {e}")
        return {"error": str(e), "recurring": [], "count": 0}


async def update_recurring(
    stream_id: str,
    status: Optional[str] = None,
    amount: Optional[float] = None,
    frequency: Optional[str] = None,
) -> dict[str, Any]:
    """Update a recurring stream's status, amount, or frequency.

    Takes a stream_id from list_recurring and updates the underlying
    merchant's recurring settings. Only works on merchant-based streams
    (not credit report liabilities).

    Status values:
    - active: reactivate a previously deactivated stream (reversible)
    - inactive: deactivate the stream (reversible)
    - removed: permanently remove ALL streams for this merchant (irreversible)

    Args:
        stream_id: The stream_id from list_recurring.
        status: active, inactive, or removed.
        amount: New recurring amount (negative for expenses).
        frequency: New frequency: monthly, biweekly, weekly, etc.
    """
    try:
        return await sdk.update_recurring(stream_id, status=status, amount=amount, frequency=frequency)
    except AuthenticationError as e:
        return {"error": str(e), "success": False}
    except Exception as e:
        logger.error(f"Error updating recurring stream: {e}")
        return {"error": str(e), "success": False}


async def mark_as_not_recurring(
    stream_id: str,
) -> dict[str, Any]:
    """Permanently remove a recurring stream. DEPRECATED — use update_recurring with status='removed' instead.

    This is a nuclear option that removes ALL streams for the merchant.
    Prefer update_recurring(status='inactive') for reversible deactivation.

    Args:
        stream_id: The stream_id from list_recurring to mark as not recurring.
    """
    try:
        return await sdk.mark_not_recurring(stream_id)
    except AuthenticationError as e:
        return {"error": str(e), "success": False}
    except Exception as e:
        logger.error(f"Error marking stream as not recurring: {e}")
        return {"error": str(e), "success": False}
