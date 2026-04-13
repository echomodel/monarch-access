"""Monarch Money API client."""

from pathlib import Path
from typing import Optional

import aiohttp

from .config import get_token, get_token_file

GRAPHQL_URL = "https://api.monarch.com/graphql"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://app.monarch.com",
    "Referer": "https://app.monarch.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class MonarchClientError(Exception):
    """Base exception for Monarch client errors."""
    pass


class AuthenticationError(MonarchClientError):
    """Raised when authentication fails."""
    pass


class APIError(MonarchClientError):
    """Raised when API request fails."""
    pass


class MonarchClient:
    """Lightweight client for Monarch Money API."""

    def __init__(
        self,
        token: Optional[str] = None,
    ):
        self._token = token or get_token()
        self._token_file = get_token_file()

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    async def _request(self, query: str, variables: Optional[dict] = None) -> dict:
        if not self._token:
            raise AuthenticationError(
                "Not authenticated. Get token from browser:\n"
                "1. Login to https://app.monarch.com/\n"
                "2. DevTools (F12) -> Console\n"
                "3. Run: JSON.parse(JSON.parse(localStorage.getItem('persist:root')).user).token"
            )

        headers = {**HEADERS, "Authorization": f"Token {self._token}"}
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with aiohttp.ClientSession() as session:
            async with session.post(GRAPHQL_URL, json=payload, headers=headers) as resp:
                if resp.status == 401:
                    raise AuthenticationError("Invalid or expired token")
                if resp.status != 200:
                    text = await resp.text()
                    raise APIError(f"HTTP {resp.status}: {text[:200]}")

                data = await resp.json()
                if "errors" in data:
                    raise APIError(f"GraphQL error: {data['errors']}")

                return data.get("data", {})


class MonarchSDK:
    """Stateless facade for MCP tools — classmethods that get the client
    from mcp-app's current_user context and delegate to SDK modules."""

    @classmethod
    def _client(cls) -> MonarchClient:
        from mcp_app.context import current_user
        user = current_user.get()
        return MonarchClient(token=user.profile.token)

    @classmethod
    async def get_accounts(cls, include_closed: bool = False) -> dict:
        from . import accounts
        client = cls._client()
        accts = await accounts.get_accounts(client, include_closed=include_closed)
        return {"accounts": accts, "count": len(accts)}

    @classmethod
    async def get_categories(cls) -> dict:
        from . import categories
        client = cls._client()
        cats = await categories.get_categories(client)
        return {"categories": cats, "count": len(cats)}

    @classmethod
    async def get_transactions(cls, **kwargs) -> dict:
        from .transactions.list import get_transactions
        client = cls._client()
        data = await get_transactions(client, **kwargs)
        transactions = data.get("results", [])
        total_count = data.get("totalCount", len(transactions))
        return {
            "transactions": transactions,
            "count": len(transactions),
            "totalCount": total_count,
        }

    @classmethod
    async def get_transaction(cls, transaction_id: str) -> dict:
        from .transactions.get import get_transaction
        client = cls._client()
        txn = await get_transaction(client, transaction_id)
        if txn:
            return {"transaction": txn, "success": True}
        return {"transaction": None, "success": False, "error": "Transaction not found"}

    @classmethod
    async def update_transaction(cls, transaction_id: str, **kwargs) -> dict:
        from .transactions.update import update_transaction
        client = cls._client()
        updated = await update_transaction(client, transaction_id=transaction_id, **kwargs)
        return {
            "transaction": updated,
            "success": True,
            "message": f"Transaction {transaction_id} updated successfully",
        }

    @classmethod
    async def bulk_mark_reviewed(cls, transaction_ids: list[str], needs_review: bool = False) -> dict:
        from .queries import BULK_UPDATE_TRANSACTIONS_MUTATION
        client = cls._client()
        variables = {
            "selectedTransactionIds": transaction_ids,
            "excludedTransactionIds": [],
            "allSelected": False,
            "expectedAffectedTransactionCount": len(transaction_ids),
            "updates": {"needsReview": needs_review},
        }
        data = await client._request(BULK_UPDATE_TRANSACTIONS_MUTATION, variables)
        result = data.get("bulkUpdateTransactions", {})
        if result.get("errors"):
            errors = result["errors"]
            msg = errors[0].get("message") if errors else "Unknown error"
            raise APIError(f"Bulk update failed: {msg}")
        status = "needing review" if needs_review else "reviewed"
        return {
            "success": True,
            "affectedCount": result.get("affectedCount", len(transaction_ids)),
            "message": f"Marked {len(transaction_ids)} transactions as {status}",
        }

    @classmethod
    async def split_transaction(cls, transaction_id: str, split_data: list[dict]) -> dict:
        from .queries import SPLIT_TRANSACTION_MUTATION
        client = cls._client()
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
        return {
            "transaction": result.get("transaction", {}),
            "success": True,
            "message": f"Transaction {transaction_id} split into {len(split_data)} parts",
        }

    @classmethod
    async def create_transaction(cls, date: str, account_id: str, amount: float,
                                 merchant_name: str, category_id: str,
                                 notes: str = "", update_balance: bool = False) -> dict:
        from .queries import CREATE_TRANSACTION_MUTATION
        client = cls._client()
        variables = {
            "input": {
                "date": date,
                "accountId": account_id,
                "amount": round(amount, 2),
                "merchantName": merchant_name,
                "categoryId": category_id,
                "notes": notes,
                "shouldUpdateBalance": update_balance,
            }
        }
        data = await client._request(CREATE_TRANSACTION_MUTATION, variables)
        result = data.get("createTransaction", {})
        if result.get("errors"):
            errors = result["errors"]
            msg = errors.get("message") or str(errors.get("fieldErrors", []))
            raise APIError(f"Create transaction failed: {msg}")
        txn = result.get("transaction", {})
        return {
            "transaction": txn,
            "success": True,
            "message": f"Transaction created with ID {txn.get('id', 'unknown')}",
        }

    @classmethod
    async def delete_transaction(cls, transaction_id: str) -> dict:
        from .queries import DELETE_TRANSACTION_MUTATION
        client = cls._client()
        variables = {"input": {"transactionId": transaction_id}}
        data = await client._request(DELETE_TRANSACTION_MUTATION, variables)
        result = data.get("deleteTransaction", {})
        if result.get("errors"):
            errors = result["errors"]
            msg = errors.get("message") or str(errors.get("fieldErrors", []))
            raise APIError(f"Delete failed: {msg}")
        deleted = result.get("deleted", False)
        return {
            "deleted": deleted,
            "success": deleted,
            "message": f"Transaction {transaction_id} deleted" if deleted else f"Failed to delete {transaction_id}",
        }

    @classmethod
    async def get_recurring(cls) -> dict:
        from .recurring import _trailing_year_range, collapse_to_streams
        from .queries import RECURRING_TRANSACTION_ITEMS_QUERY
        client = cls._client()
        start_date, end_date = _trailing_year_range()
        data = await client._request(
            RECURRING_TRANSACTION_ITEMS_QUERY,
            {"startDate": start_date, "endDate": end_date},
        )
        items = data.get("recurringTransactionItems", [])
        streams = collapse_to_streams(items)
        return {"recurring": streams, "count": len(streams)}

    @classmethod
    async def update_recurring(cls, stream_id: str, **kwargs) -> dict:
        from .recurring import update_recurring
        client = cls._client()
        result = await update_recurring(client, stream_id, **kwargs)
        return {"success": True, "result": result}

    @classmethod
    async def mark_not_recurring(cls, stream_id: str) -> dict:
        from .recurring import mark_as_not_recurring
        client = cls._client()
        result = await mark_as_not_recurring(client, stream_id)
        return {"success": True, "result": result}
