"""Monarch Money API client."""

import json as _json
from typing import Optional

import aiohttp

API_BASE = "https://api.monarch.com"
GRAPHQL_URL = f"{API_BASE}/graphql"

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

    def __init__(self, token: str):
        self._token = token

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    async def _request(self, query: str, variables: Optional[dict] = None) -> dict:
        if not self._token:
            raise AuthenticationError(
                "No Monarch token configured. Set up auth with:\n"
                "  monarch-admin connect local\n"
                "  monarch-admin users add local --token $MONARCH_SESSION_TOKEN"
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

    def _auth_headers(self, *, content_type: Optional[str] = "json") -> dict:
        """Build authorized headers. Pass content_type=None for multipart
        (aiohttp sets the boundary-bearing Content-Type itself)."""
        headers = {**HEADERS, "Authorization": f"Token {self._token}"}
        if content_type is None:
            headers.pop("Content-Type", None)
        return headers

    async def _download_balances(self, account_ids: list[str]) -> str:
        """POST /download-balances/ and return the CSV body (Date,Balance,Account)."""
        if not self._token:
            raise AuthenticationError("No Monarch token configured.")
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/download-balances/",
                json={"account_ids": account_ids},
                headers=self._auth_headers(),
            ) as resp:
                text = await resp.text()
                if resp.status == 401:
                    raise AuthenticationError("Invalid or expired token")
                if resp.status != 200:
                    raise APIError(f"HTTP {resp.status}: {text[:200]}")
                return text

    async def cloudinary_upload(
        self, path: str, request_params: dict, file_bytes: bytes, filename: str
    ) -> dict:
        """Upload a file to Cloudinary using the signed params returned by
        ``getTransactionAttachmentUploadInfo``. This call is authorized by
        the ``signature`` param, NOT the Monarch token — so no Monarch auth
        header is sent. Returns Cloudinary's JSON (public_id, format, bytes,
        secure_url, ...)."""
        url = f"https://api.cloudinary.com{path}"
        form = aiohttp.FormData()
        form.add_field("file", file_bytes, filename=filename,
                       content_type="application/octet-stream")
        for key in ("timestamp", "folder", "signature", "api_key", "upload_preset"):
            val = request_params.get(key)
            if val is not None:
                form.add_field(key, str(val))
        async with aiohttp.ClientSession() as session:
            async with session.post(url, data=form) as resp:
                text = await resp.text()
                if resp.status not in (200, 201):
                    raise APIError(f"Cloudinary HTTP {resp.status}: {text[:200]}")
                return _json.loads(text)

    async def _upload_balances(self, csv_text: str, account_id: str, filename: str) -> dict:
        """POST a balance-history CSV to /account-balance-history/upload/.

        Returns the upload response, including the session_key used to finalize
        processing via the parse mutation + session poll.
        """
        if not self._token:
            raise AuthenticationError("No Monarch token configured.")
        form = aiohttp.FormData()
        form.add_field("files", csv_text.encode(), filename=filename, content_type="text/csv")
        form.add_field("account_files_mapping", _json.dumps({filename: account_id}))
        form.add_field("files_column_mapping", _json.dumps({filename: {"date": 0, "balance": 1}}))
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{API_BASE}/account-balance-history/upload/",
                data=form,
                headers=self._auth_headers(content_type=None),
            ) as resp:
                if resp.status == 401:
                    raise AuthenticationError("Invalid or expired token")
                if resp.status not in (200, 201):
                    text = await resp.text()
                    raise APIError(f"HTTP {resp.status}: {text[:200]}")
                return await resp.json()


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
    async def update_account(
        cls,
        account_id: str,
        name: Optional[str] = None,
        include_in_net_worth: Optional[bool] = None,
        hidden: Optional[bool] = None,
        reopen: bool = False,
    ) -> dict:
        from . import accounts
        client = cls._client()
        kwargs: dict = {}
        if name is not None:
            kwargs["name"] = name
        if include_in_net_worth is not None:
            kwargs["include_in_net_worth"] = include_in_net_worth
        if hidden is not None:
            kwargs["hidden"] = hidden
        if reopen:
            kwargs["deactivated_at"] = None
        acct = await accounts.update_account(client, account_id, **kwargs)
        return {"account": acct, "success": True}

    @classmethod
    async def close_account(cls, account_id: str, close_date: Optional[str] = None) -> dict:
        from . import accounts
        client = cls._client()
        acct = await accounts.close_account(client, account_id, close_date=close_date)
        return {"account": acct, "success": True}

    @classmethod
    async def get_holdings(cls, account_ids: Optional[list[str]] = None, as_of_date: Optional[str] = None) -> dict:
        from . import holdings
        client = cls._client()
        items = await holdings.get_holdings(client, account_ids=account_ids, as_of_date=as_of_date)
        return {"holdings": items, "count": len(items)}

    @classmethod
    async def download_balance_history(cls, account_id: str) -> dict:
        from . import balances
        client = cls._client()
        snapshots = await balances.download_balance_history(client, account_id)
        return {
            "account_id": account_id,
            "snapshots": snapshots,
            "count": len(snapshots),
            "history_token": balances.history_token(snapshots),
        }

    @classmethod
    async def upload_balance_history(
        cls, account_id: str, snapshots: list[dict], expected_token: int
    ) -> dict:
        from . import balances
        client = cls._client()
        return await balances.upload_balance_history(client, account_id, snapshots, expected_token)

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
    async def attach_transaction(
        cls, transaction_id: str, file_path: Optional[str] = None,
        content_base64: Optional[str] = None, filename: Optional[str] = None,
    ) -> dict:
        """Attach a file to a transaction as a native Monarch attachment.

        Provide the bytes one of two ways:
          - ``file_path``: a path the server can read (local/stdio).
          - ``content_base64``: base64 bytes (works over any transport;
            required when the server can't see the local filesystem).
        ``filename`` is the display name shown in Monarch.
        """
        from .transactions.attach import attach_transaction_bytes, attach_transaction_file
        client = cls._client()
        if content_base64 is not None:
            import base64
            data = base64.b64decode(content_base64)
            upload_name = filename or "attachment"
            attachment = await attach_transaction_bytes(
                client, transaction_id, data, upload_name, filename
            )
        elif file_path is not None:
            attachment = await attach_transaction_file(
                client, transaction_id, file_path, filename
            )
        else:
            return {"success": False, "error": "Provide file_path or content_base64."}
        return {
            "attachment": attachment,
            "success": True,
            "message": f"Attached '{attachment.get('filename')}' to transaction {transaction_id}",
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
    async def create_transactions(cls, transactions: list[dict]) -> dict:
        """Create one or more manual transactions.

        Each input dict requires: date, account_id, amount, merchant_name,
        category_id. Optional: notes (default ""), update_balance (default
        False).

        Returns a per-item result envelope so partial successes are visible:
            {
              "success": bool,           # True iff all items succeeded
              "success_count": int,
              "failure_count": int,
              "created": [{"index": int, "input": dict, "transaction": dict}],
              "failed":  [{"index": int, "input": dict, "error": str}],
            }
        """
        from .queries import CREATE_TRANSACTION_MUTATION
        client = cls._client()

        created: list[dict] = []
        failed: list[dict] = []

        for index, item in enumerate(transactions):
            try:
                variables = {
                    "input": {
                        "date": item["date"],
                        "accountId": item["account_id"],
                        "amount": round(float(item["amount"]), 2),
                        "merchantName": item["merchant_name"],
                        "categoryId": item["category_id"],
                        "notes": item.get("notes", "") or "",
                        "shouldUpdateBalance": bool(item.get("update_balance", False)),
                    }
                }
                data = await client._request(CREATE_TRANSACTION_MUTATION, variables)
                result = data.get("createTransaction", {})
                if result.get("errors"):
                    errors = result["errors"]
                    msg = errors.get("message") or str(errors.get("fieldErrors", []))
                    raise APIError(msg)
                txn = result.get("transaction", {})
                created.append({"index": index, "input": item, "transaction": txn})
            except (KeyError, APIError, ValueError, TypeError) as e:
                failed.append({"index": index, "input": item, "error": str(e)})

        return {
            "success": len(failed) == 0,
            "success_count": len(created),
            "failure_count": len(failed),
            "created": created,
            "failed": failed,
        }

    @classmethod
    async def delete_transactions(cls, transaction_ids: list[str]) -> dict:
        """Delete one or more transactions by ID.

        Returns a per-item result envelope so partial successes are visible:
            {
              "success": bool,           # True iff all items succeeded
              "success_count": int,
              "failure_count": int,
              "deleted": [{"index": int, "transaction_id": str}],
              "failed":  [{"index": int, "transaction_id": str, "error": str}],
            }
        """
        from .queries import DELETE_TRANSACTION_MUTATION
        client = cls._client()

        deleted: list[dict] = []
        failed: list[dict] = []

        for index, txn_id in enumerate(transaction_ids):
            try:
                variables = {"input": {"transactionId": txn_id}}
                data = await client._request(DELETE_TRANSACTION_MUTATION, variables)
                result = data.get("deleteTransaction", {})
                if result.get("errors"):
                    errors = result["errors"]
                    msg = errors.get("message") or str(errors.get("fieldErrors", []))
                    raise APIError(msg)
                if not result.get("deleted", False):
                    raise APIError("API reported transaction was not deleted")
                deleted.append({"index": index, "transaction_id": txn_id})
            except (APIError, ValueError, TypeError) as e:
                failed.append({"index": index, "transaction_id": txn_id, "error": str(e)})

        return {
            "success": len(failed) == 0,
            "success_count": len(deleted),
            "failure_count": len(failed),
            "deleted": deleted,
            "failed": failed,
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

    @classmethod
    async def get_rules(cls) -> dict:
        from .rules import get_rules, format_rule
        client = cls._client()
        rules = await get_rules(client)
        formatted = [format_rule(r) for r in rules]
        return {"rules": formatted, "count": len(formatted)}

    @classmethod
    async def create_rule(cls, **kwargs) -> dict:
        from .rules import create_rule
        client = cls._client()
        return await create_rule(client, **kwargs)

    @classmethod
    async def delete_rule(cls, rule_id: str) -> dict:
        from .rules import delete_rule
        client = cls._client()
        return await delete_rule(client, rule_id)
