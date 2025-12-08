"""Monarch API provider implementation."""

import asyncio
from typing import Any, Optional

from ...client import MonarchClient, APIError
from ...queries import (
    ACCOUNTS_QUERY,
    GET_TRANSACTION_QUERY,
    TRANSACTION_CATEGORIES_QUERY,
    TRANSACTIONS_QUERY,
    UPDATE_TRANSACTION_MUTATION,
)


class APIProvider:
    """Provider that connects to the Monarch Money API."""

    def __init__(self, client: Optional[MonarchClient] = None):
        self._client = client or MonarchClient()

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
    ) -> dict:
        """Get transactions with optional filters."""
        return self._run(self._get_transactions(
            limit, offset, start_date, end_date, account_ids, category_ids, search
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
        return data.get("allTransactions", {"totalCount": 0, "results": []})

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

    def get_accounts(self) -> list[dict]:
        """Get all accounts."""
        return self._run(self._get_accounts())

    async def _get_accounts(self) -> list[dict]:
        data = await self._client._request(ACCOUNTS_QUERY)
        return data.get("accounts", [])

    def get_categories(self) -> list[dict]:
        """Get all transaction categories."""
        return self._run(self._get_categories())

    async def _get_categories(self) -> list[dict]:
        data = await self._client._request(TRANSACTION_CATEGORIES_QUERY)
        return data.get("categories", [])
