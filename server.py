"""MCP Server for Monarch Money financial data access.

This server exposes Monarch Money data via the Model Context Protocol (MCP),
making it consumable by LLMs like Claude Desktop, Gemini CLI, and other MCP clients.

Uses async functions directly (like ticktick-access) to avoid event loop conflicts.
"""

import json
import logging
import os
from typing import Any, Optional

from mcp.server.fastmcp import FastMCP
from pydantic import Field

from monarch.client import MonarchClient, AuthenticationError, APIError
from monarch.queries import (
    ACCOUNTS_QUERY,
    BULK_UPDATE_TRANSACTIONS_MUTATION,
    GET_TRANSACTION_QUERY,
    SPLIT_TRANSACTION_MUTATION,
    TRANSACTION_CATEGORIES_QUERY,
    TRANSACTIONS_QUERY,
    UPDATE_TRANSACTION_MUTATION,
)

# Initialize logging
log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=log_level, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("monarch")


def _get_client() -> MonarchClient:
    """Get MonarchClient instance.

    Supports MONARCH_TOKEN environment variable for Docker/container usage.
    Falls back to token file (~/.config/monarch/token) if env var not set.
    """
    token = os.getenv("MONARCH_TOKEN")
    if token:
        logger.info("Using MONARCH_TOKEN from environment variable")
        return MonarchClient(token=token)
    return MonarchClient()


# --- Async API helpers ---


async def get_accounts(client: MonarchClient) -> list[dict]:
    """Get all accounts."""
    data = await client._request(ACCOUNTS_QUERY)
    return data.get("accounts", [])


async def get_categories(client: MonarchClient) -> list[dict]:
    """Get all transaction categories."""
    data = await client._request(TRANSACTION_CATEGORIES_QUERY)
    return data.get("categories", [])


async def get_transactions(
    client: MonarchClient,
    limit: int = 100,
    offset: int = 0,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    account_ids: Optional[list[str]] = None,
    category_ids: Optional[list[str]] = None,
    search: Optional[str] = None,
) -> dict:
    """Get transactions with optional filters."""
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
    if start_date:
        variables["filters"]["startDate"] = start_date
    if end_date:
        variables["filters"]["endDate"] = end_date

    data = await client._request(TRANSACTIONS_QUERY, variables)
    return data.get("allTransactions", {"totalCount": 0, "results": []})


async def get_transaction(client: MonarchClient, transaction_id: str) -> Optional[dict]:
    """Get a single transaction by ID."""
    data = await client._request(GET_TRANSACTION_QUERY, {"id": transaction_id})
    return data.get("getTransaction")


async def update_transaction(
    client: MonarchClient,
    transaction_id: str,
    category_id: Optional[str] = None,
    merchant_name: Optional[str] = None,
    notes: Optional[str] = None,
    amount: Optional[float] = None,
    date: Optional[str] = None,
    hide_from_reports: Optional[bool] = None,
    needs_review: Optional[bool] = None,
) -> dict:
    """Update a transaction."""
    variables: dict[str, Any] = {
        "input": {
            "id": transaction_id,
        }
    }

    if category_id is not None:
        variables["input"]["category"] = category_id
    if merchant_name is not None:
        variables["input"]["name"] = merchant_name
    if notes is not None:
        variables["input"]["notes"] = notes
    if amount is not None:
        variables["input"]["amount"] = amount
    if date is not None:
        variables["input"]["date"] = date
    if hide_from_reports is not None:
        variables["input"]["hideFromReports"] = hide_from_reports
    if needs_review is not None:
        variables["input"]["needsReview"] = needs_review

    data = await client._request(UPDATE_TRANSACTION_MUTATION, variables)
    result = data.get("updateTransaction", {})

    if result.get("errors"):
        errors = result["errors"]
        msg = errors.get("message") or str(errors.get("fieldErrors", []))
        raise APIError(f"Update failed: {msg}")

    return result.get("transaction", {})


async def bulk_update_transactions(
    client: MonarchClient,
    transaction_ids: list[str],
    needs_review: Optional[bool] = None,
    category_id: Optional[str] = None,
    hide_from_reports: Optional[bool] = None,
) -> dict:
    """Bulk update multiple transactions."""
    updates: dict[str, Any] = {}
    if needs_review is not None:
        updates["needsReview"] = needs_review
    if category_id is not None:
        updates["categoryId"] = category_id
    if hide_from_reports is not None:
        updates["hide"] = hide_from_reports

    variables = {
        "selectedTransactionIds": transaction_ids,
        "excludedTransactionIds": [],
        "allSelected": False,
        "expectedAffectedTransactionCount": len(transaction_ids),
        "updates": updates,
    }

    data = await client._request(BULK_UPDATE_TRANSACTIONS_MUTATION, variables)
    result = data.get("bulkUpdateTransactions", {})

    if result.get("errors"):
        errors = result["errors"]
        msg = errors[0].get("message") if errors else "Unknown error"
        raise APIError(f"Bulk update failed: {msg}")

    return result


async def split_transaction(
    client: MonarchClient,
    transaction_id: str,
    split_data: list[dict],
) -> dict:
    """Split a transaction into multiple parts."""
    variables = {
        "input": {
            "transactionId": transaction_id,
            "splitData": split_data,
        }
    }

    data = await client._request(SPLIT_TRANSACTION_MUTATION, variables)
    result = data.get("updateTransactionSplit", {})

    if result.get("errors"):
        errors = result["errors"]
        msg = errors.get("message") or str(errors.get("fieldErrors", []))
        raise APIError(f"Split failed: {msg}")

    return result.get("transaction", {})


# --- Resource Definitions ---


@mcp.resource("monarch://accounts")
async def get_accounts_resource() -> str:
    """
    Get all financial accounts from Monarch Money.

    Returns account data including: account IDs, display names, types
    (checking, savings, credit card, etc.), current balances, institution
    names, and other metadata.
    """
    try:
        client = _get_client()
        accounts = await get_accounts(client)
        return json.dumps(accounts, indent=2, default=str)
    except AuthenticationError as e:
        return json.dumps({"error": str(e), "hint": "Ensure MONARCH_TOKEN is set"})
    except Exception as e:
        logger.error(f"Error getting accounts: {e}")
        return json.dumps({"error": str(e)})


@mcp.resource("monarch://categories")
async def get_categories_resource() -> str:
    """
    Get all transaction categories from Monarch Money.

    Returns category data including: category IDs, names, group names,
    and group types (income, expense, transfer).
    """
    try:
        client = _get_client()
        categories = await get_categories(client)
        return json.dumps(categories, indent=2, default=str)
    except AuthenticationError as e:
        return json.dumps({"error": str(e), "hint": "Ensure MONARCH_TOKEN is set"})
    except Exception as e:
        logger.error(f"Error getting categories: {e}")
        return json.dumps({"error": str(e)})


# --- Tool Definitions ---


@mcp.tool(
    name="list_accounts",
    description="List all financial accounts from Monarch Money. Returns account IDs, names, types, balances, and institution names. Use account IDs with list_transactions to filter by account.",
)
async def list_accounts_tool() -> dict[str, Any]:
    """Retrieve all financial accounts from Monarch Money."""
    try:
        client = _get_client()
        accounts = await get_accounts(client)
        return {"accounts": accounts, "count": len(accounts)}
    except AuthenticationError as e:
        return {"error": str(e), "accounts": [], "count": 0}
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        return {"error": str(e), "accounts": [], "count": 0}


@mcp.tool(
    name="list_categories",
    description="List all transaction categories from Monarch Money. Returns category IDs, names, and group information. Use category IDs with list_transactions to filter or update_transaction to recategorize.",
)
async def list_categories_tool() -> dict[str, Any]:
    """Retrieve all transaction categories from Monarch Money."""
    try:
        client = _get_client()
        categories = await get_categories(client)
        return {"categories": categories, "count": len(categories)}
    except AuthenticationError as e:
        return {"error": str(e), "categories": [], "count": 0}
    except Exception as e:
        logger.error(f"Error listing categories: {e}")
        return {"error": str(e), "categories": [], "count": 0}


@mcp.tool(
    name="list_transactions",
    description="List transactions from Monarch Money with optional filters. Filter by date range, accounts, categories, or search text. Returns transaction details including amounts, merchants, categories, and notes.",
)
async def list_transactions_tool(
    limit: int = Field(
        default=100,
        description="Maximum number of transactions to return (default: 100, max: 1000).",
    ),
    start_date: Optional[str] = Field(
        default=None,
        description="Start date filter, inclusive (YYYY-MM-DD format). Example: '2025-01-01'",
    ),
    end_date: Optional[str] = Field(
        default=None,
        description="End date filter, inclusive (YYYY-MM-DD format). Example: '2025-12-31'",
    ),
    account_ids: Optional[list[str]] = Field(
        default=None,
        description="List of account IDs to filter by. Get IDs from list_accounts tool.",
    ),
    category_ids: Optional[list[str]] = Field(
        default=None,
        description="List of category IDs to filter by. Get IDs from list_categories tool.",
    ),
    search: Optional[str] = Field(
        default=None,
        description="Search text to filter transactions by merchant name, notes, or description.",
    ),
) -> dict[str, Any]:
    """Retrieve transactions from Monarch Money with optional filters."""
    try:
        client = _get_client()

        # Clamp limit
        limit = max(1, min(1000, limit))

        data = await get_transactions(
            client,
            limit=limit,
            start_date=start_date,
            end_date=end_date,
            account_ids=account_ids,
            category_ids=category_ids,
            search=search,
        )

        transactions = data.get("results", [])
        total_count = data.get("totalCount", len(transactions))

        return {
            "transactions": transactions,
            "count": len(transactions),
            "totalCount": total_count,
        }
    except AuthenticationError as e:
        return {"error": str(e), "transactions": [], "count": 0, "totalCount": 0}
    except Exception as e:
        logger.error(f"Error listing transactions: {e}")
        return {"error": str(e), "transactions": [], "count": 0, "totalCount": 0}


@mcp.tool(
    name="get_transaction",
    description="Get details of a single transaction by ID. Returns full transaction data including amount, merchant, category, account, notes, and tags.",
)
async def get_transaction_tool(
    transaction_id: str = Field(
        description="The ID of the transaction to retrieve. Get IDs from list_transactions.",
    ),
) -> dict[str, Any]:
    """Retrieve a single transaction by its ID."""
    try:
        client = _get_client()
        txn = await get_transaction(client, transaction_id)

        if txn:
            return {"transaction": txn, "success": True}
        return {"transaction": None, "success": False, "error": "Transaction not found"}
    except AuthenticationError as e:
        return {"error": str(e), "transaction": None, "success": False}
    except Exception as e:
        logger.error(f"Error getting transaction: {e}")
        return {"error": str(e), "transaction": None, "success": False}


@mcp.tool(
    name="update_transaction",
    description="Update a transaction's category, merchant name, notes, or review status. Only specified fields are updated; others remain unchanged.",
)
async def update_transaction_tool(
    transaction_id: str = Field(
        description="The ID of the transaction to update. Get IDs from list_transactions.",
    ),
    category_id: Optional[str] = Field(
        default=None,
        description="New category ID to assign. Get IDs from list_categories tool.",
    ),
    merchant_name: Optional[str] = Field(
        default=None,
        description="New merchant name to set.",
    ),
    notes: Optional[str] = Field(
        default=None,
        description="Notes to add or update. Use empty string '' to clear notes.",
    ),
    needs_review: Optional[bool] = Field(
        default=None,
        description="Set to true to mark as needing review, false to mark as reviewed.",
    ),
    hide_from_reports: Optional[bool] = Field(
        default=None,
        description="Set to true to hide from reports/budgets, false to include.",
    ),
) -> dict[str, Any]:
    """Update a transaction in Monarch Money."""
    try:
        client = _get_client()

        updated = await update_transaction(
            client,
            transaction_id=transaction_id,
            category_id=category_id,
            merchant_name=merchant_name,
            notes=notes,
            needs_review=needs_review,
            hide_from_reports=hide_from_reports,
        )

        return {
            "transaction": updated,
            "success": True,
            "message": f"Transaction {transaction_id} updated successfully",
        }
    except AuthenticationError as e:
        return {"error": str(e), "transaction": None, "success": False}
    except APIError as e:
        return {"error": str(e), "transaction": None, "success": False}
    except Exception as e:
        logger.error(f"Error updating transaction: {e}")
        return {"error": str(e), "transaction": None, "success": False}


@mcp.tool(
    name="mark_transactions_reviewed",
    description="Mark one or more transactions as reviewed (or needing review). Useful for bulk operations after reviewing transactions.",
)
async def mark_transactions_reviewed_tool(
    transaction_ids: list[str] = Field(
        description="List of transaction IDs to update. Get IDs from list_transactions.",
    ),
    needs_review: bool = Field(
        default=False,
        description="Set to false (default) to mark as reviewed, true to mark as needing review.",
    ),
) -> dict[str, Any]:
    """Mark multiple transactions as reviewed or needing review."""
    try:
        client = _get_client()

        if not transaction_ids:
            return {"success": False, "error": "No transaction IDs provided", "affectedCount": 0}

        result = await bulk_update_transactions(
            client,
            transaction_ids=transaction_ids,
            needs_review=needs_review,
        )

        status = "needing review" if needs_review else "reviewed"
        return {
            "success": True,
            "affectedCount": result.get("affectedCount", len(transaction_ids)),
            "message": f"Marked {len(transaction_ids)} transactions as {status}",
        }
    except AuthenticationError as e:
        return {"error": str(e), "success": False, "affectedCount": 0}
    except APIError as e:
        return {"error": str(e), "success": False, "affectedCount": 0}
    except Exception as e:
        logger.error(f"Error marking transactions: {e}")
        return {"error": str(e), "success": False, "affectedCount": 0}


@mcp.tool(
    name="split_transaction",
    description="Split a transaction into multiple parts with different categories. The sum of split amounts must equal the original transaction amount.",
)
async def split_transaction_tool(
    transaction_id: str = Field(
        description="The ID of the transaction to split. Get IDs from list_transactions.",
    ),
    splits: list[dict] = Field(
        description='Array of split objects. Each split must have "amount" (float, negative for expenses) and "categoryId" (string). Optional: "merchantName" (string), "notes" (string). Example: [{"amount": -50.00, "categoryId": "cat123"}, {"amount": -25.00, "categoryId": "cat456"}]',
    ),
) -> dict[str, Any]:
    """Split a transaction into multiple parts with different categories."""
    try:
        client = _get_client()

        result = await split_transaction(client, transaction_id, splits)

        return {
            "transaction": result,
            "success": True,
            "message": f"Transaction {transaction_id} split into {len(splits)} parts",
        }
    except AuthenticationError as e:
        return {"error": str(e), "transaction": None, "success": False}
    except APIError as e:
        return {"error": str(e), "transaction": None, "success": False}
    except Exception as e:
        logger.error(f"Error splitting transaction: {e}")
        return {"error": str(e), "transaction": None, "success": False}


# ASGI application for HTTP transport (uvicorn)
mcp_app = mcp.streamable_http_app()

# Stdio transport support
if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "--stdio":
        mcp.run(transport="stdio")
