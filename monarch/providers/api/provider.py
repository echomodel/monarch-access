"""Monarch API provider implementation."""

import asyncio
from typing import Any, Optional

from ...client import MonarchClient, APIError, AuthenticationError
from ...queries import (
    ACCOUNTS_QUERY,
    BULK_UPDATE_TRANSACTIONS_MUTATION,
    CREATE_TRANSACTION_MUTATION,
    GET_TRANSACTION_QUERY,
    RECURRING_TRANSACTION_ITEMS_QUERY,
    SPLIT_TRANSACTION_MUTATION,
    TRANSACTION_CATEGORIES_QUERY,
    TRANSACTIONS_QUERY,
    UPDATE_TRANSACTION_MUTATION,
)


def _load_token() -> str:
    """Load the Monarch session token from the mcp-app local user store."""
    from mcp_app import FileSystemUserDataStore
    store = FileSystemUserDataStore("monarch")
    user_data = store.load("local", "user")
    if user_data and isinstance(user_data, dict):
        profile = user_data.get("profile") or {}
        token = profile.get("token")
        if token:
            return token

    raise AuthenticationError(
        "No Monarch token configured. Set up auth with:\n"
        "  monarch-admin connect local\n"
        "  monarch-admin users add local --token $MONARCH_SESSION_TOKEN"
    )


class APIProvider:
    """Provider that connects to the Monarch Money API."""

    def __init__(self, client: Optional[MonarchClient] = None):
        self._client = client or MonarchClient(token=_load_token())

    def _run(self, coro):
        """Run async coroutine synchronously."""
        return asyncio.run(coro)

    def get_transactions(
        self,
        limit: int = 100,
        offset: int = 0,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        account_ids: Optional[list[str]] = None,
        category_ids: Optional[list[str]] = None,
        search: Optional[str] = None,
        is_expense: Optional[bool] = None,
    ) -> dict:
        """Get transactions with optional filters."""
        return self._run(self._get_transactions(
            limit, offset, start_date, end_date, account_ids, category_ids, search, is_expense
        ))

    async def _get_transactions(
        self,
        limit: int,
        offset: int,
        start_date: Optional[str],
        end_date: Optional[str],
        account_ids: Optional[list[str]],
        category_ids: Optional[list[str]],
        search: Optional[str],
        is_expense: Optional[bool] = None,
    ) -> dict:
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

        data = await self._client._request(TRANSACTIONS_QUERY, variables)
        result = data.get("allTransactions", {"totalCount": 0, "results": []})

        if is_expense is not None:
            results = result.get("results", [])
            if is_expense:
                results = [t for t in results if (t.get("amount") or 0) < 0]
            else:
                results = [t for t in results if (t.get("amount") or 0) > 0]
            result = {"totalCount": result.get("totalCount", 0), "results": results}

        return result

    def get_transaction(self, transaction_id: str) -> Optional[dict]:
        """Get a single transaction by ID."""
        return self._run(self._get_transaction(transaction_id))

    async def _get_transaction(self, transaction_id: str) -> Optional[dict]:
        data = await self._client._request(GET_TRANSACTION_QUERY, {"id": transaction_id})
        return data.get("getTransaction")

    def update_transaction(
        self,
        transaction_id: str,
        category_id: Optional[str] = None,
        merchant_name: Optional[str] = None,
        notes: Optional[str] = None,
        amount: Optional[float] = None,
        date: Optional[str] = None,
        hide_from_reports: Optional[bool] = None,
        needs_review: Optional[bool] = None,
    ) -> dict:
        """Update a transaction. Only provided fields are updated."""
        return self._run(self._update_transaction(
            transaction_id, category_id, merchant_name, notes,
            amount, date, hide_from_reports, needs_review
        ))

    async def _update_transaction(
        self,
        transaction_id: str,
        category_id: Optional[str],
        merchant_name: Optional[str],
        notes: Optional[str],
        amount: Optional[float],
        date: Optional[str],
        hide_from_reports: Optional[bool],
        needs_review: Optional[bool],
    ) -> dict:
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

        data = await self._client._request(UPDATE_TRANSACTION_MUTATION, variables)
        result = data.get("updateTransaction", {})

        if result.get("errors"):
            errors = result["errors"]
            msg = errors.get("message") or str(errors.get("fieldErrors", []))
            raise APIError(f"Update failed: {msg}")

        return result.get("transaction", {})

    def bulk_update_transactions(
        self,
        transaction_ids: list[str],
        needs_review: Optional[bool] = None,
        category_id: Optional[str] = None,
        hide_from_reports: Optional[bool] = None,
    ) -> dict:
        """Bulk update multiple transactions."""
        return self._run(self._bulk_update_transactions(
            transaction_ids, needs_review, category_id, hide_from_reports
        ))

    async def _bulk_update_transactions(
        self,
        transaction_ids: list[str],
        needs_review: Optional[bool],
        category_id: Optional[str],
        hide_from_reports: Optional[bool],
    ) -> dict:
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

        data = await self._client._request(BULK_UPDATE_TRANSACTIONS_MUTATION, variables)
        result = data.get("bulkUpdateTransactions", {})

        if result.get("errors"):
            errors = result["errors"]
            msg = errors[0].get("message") if errors else "Unknown error"
            raise APIError(f"Bulk update failed: {msg}")

        return result

    def get_accounts(self, include_closed: bool = False) -> list[dict]:
        """Get all accounts. Excludes closed/deactivated by default."""
        from ...accounts import is_closed
        accounts = self._run(self._get_accounts())
        if not include_closed:
            accounts = [a for a in accounts if not is_closed(a)]
        return accounts

    async def _get_accounts(self) -> list[dict]:
        data = await self._client._request(ACCOUNTS_QUERY)
        return data.get("accounts", [])

    def get_categories(self) -> list[dict]:
        """Get all transaction categories."""
        return self._run(self._get_categories())

    async def _get_categories(self) -> list[dict]:
        data = await self._client._request(TRANSACTION_CATEGORIES_QUERY)
        return data.get("categories", [])

    def split_transaction(
        self,
        transaction_id: str,
        split_data: list[dict],
    ) -> dict:
        """Split a transaction into multiple parts.

        Args:
            transaction_id: The transaction to split
            split_data: List of splits, each with:
                - amount: float (negative for expenses)
                - categoryId: str
                - merchantName: str (optional)
                - notes: str (optional)

        The sum of split amounts must equal the original transaction amount.
        Pass empty list to remove all splits.
        """
        return self._run(self._split_transaction(transaction_id, split_data))

    async def _split_transaction(
        self,
        transaction_id: str,
        split_data: list[dict],
    ) -> dict:
        variables = {
            "input": {
                "transactionId": transaction_id,
                "splitData": split_data,
            }
        }

        data = await self._client._request(SPLIT_TRANSACTION_MUTATION, variables)
        result = data.get("updateTransactionSplit", {})

        if result.get("errors"):
            errors = result["errors"]
            msg = errors.get("message") or str(errors.get("fieldErrors", []))
            raise APIError(f"Split failed: {msg}")

        return result.get("transaction", {})

    def get_recurring_transaction_items(
        self,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """Get recurring transaction items for a date range."""
        return self._run(self._get_recurring_transaction_items(start_date, end_date))

    async def _get_recurring_transaction_items(
        self,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        variables = {
            "startDate": start_date,
            "endDate": end_date,
        }

        data = await self._client._request(RECURRING_TRANSACTION_ITEMS_QUERY, variables)
        return data.get("recurringTransactionItems", [])

    def update_recurring(self, stream_id: str, *, status=None, amount=None, frequency=None) -> dict:
        """Update a recurring stream's status, amount, or frequency."""
        return self._run(self._update_recurring(stream_id, status=status, amount=amount, frequency=frequency))

    async def _update_recurring(self, stream_id: str, **kwargs) -> dict:
        from monarch.recurring import update_recurring
        return await update_recurring(self._client, stream_id, **kwargs)

    def mark_as_not_recurring(self, stream_id: str) -> dict:
        """Mark a recurring stream as not recurring."""
        return self._run(self._mark_as_not_recurring(stream_id))

    async def _mark_as_not_recurring(self, stream_id: str) -> dict:
        from monarch.recurring import mark_as_not_recurring
        return await mark_as_not_recurring(self._client, stream_id)

    def create_transaction(
        self,
        date: str,
        account_id: str,
        amount: float,
        merchant_name: str,
        category_id: str,
        notes: str = "",
        update_balance: bool = False,
    ) -> dict:
        """Create a new manual transaction.

        Args:
            date: Transaction date in YYYY-MM-DD format
            account_id: The account ID for this transaction
            amount: Transaction amount (negative for expenses)
            merchant_name: Name of the merchant/payee
            category_id: Category ID for this transaction
            notes: Optional notes
            update_balance: Whether to update account balance
        """
        return self._run(self._create_transaction(
            date, account_id, amount, merchant_name, category_id, notes, update_balance
        ))

    async def _create_transaction(
        self,
        date: str,
        account_id: str,
        amount: float,
        merchant_name: str,
        category_id: str,
        notes: str,
        update_balance: bool,
    ) -> dict:
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

        data = await self._client._request(CREATE_TRANSACTION_MUTATION, variables)
        result = data.get("createTransaction", {})

        if result.get("errors"):
            errors = result["errors"]
            msg = errors.get("message") or str(errors.get("fieldErrors", []))
            raise APIError(f"Create transaction failed: {msg}")

        return result.get("transaction", {})
