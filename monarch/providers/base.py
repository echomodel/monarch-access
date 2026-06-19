"""Provider protocol definitions (interfaces)."""

from typing import Optional, Protocol, runtime_checkable


@runtime_checkable
class TransactionsProvider(Protocol):
    """Interface for transaction operations."""

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
        """Get transactions with optional filters.

        Returns dict with 'totalCount' and 'results' keys.
        """
        ...

    def get_transaction(self, transaction_id: str) -> Optional[dict]:
        """Get a single transaction by ID."""
        ...

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
        ...

    def attach_transaction(
        self,
        transaction_id: str,
        file_path: str,
        filename: Optional[str] = None,
    ) -> dict:
        """Attach a local file to a transaction as a native attachment.

        Returns the created attachment record (id, filename, extension,
        sizeBytes, publicId, originalAssetUrl). Multiple attachments per
        transaction are supported.
        """
        ...

    def bulk_update_transactions(
        self,
        transaction_ids: list[str],
        needs_review: Optional[bool] = None,
        category_id: Optional[str] = None,
        hide_from_reports: Optional[bool] = None,
    ) -> dict:
        """Bulk update multiple transactions.

        Returns dict with 'success', 'affectedCount', and 'errors' keys.
        """
        ...

    def create_transactions(self, transactions: list[dict]) -> dict:
        """Create one or more manual transactions.

        Each input dict requires: date, account_id, amount, merchant_name,
        category_id. Optional: notes, update_balance.

        Returns per-item result envelope with success/failure split.
        """
        ...

    def delete_transactions(self, transaction_ids: list[str]) -> dict:
        """Delete one or more transactions by ID.

        Returns per-item result envelope with success/failure split.
        """
        ...


@runtime_checkable
class AccountsProvider(Protocol):
    """Interface for account operations."""

    def get_accounts(self, include_closed: bool = False) -> list[dict]:
        """Get all accounts. Excludes closed/deactivated by default."""
        ...

    def update_account(self, account_id: str, **kwargs) -> dict:
        """Update an account's settings (partial). Returns the updated account.

        Keyword fields: name, deactivated_at, include_in_net_worth, hidden.
        Fields not passed are left unchanged.
        """
        ...

    def close_account(self, account_id: str, close_date: Optional[str] = None) -> dict:
        """Close an account (set deactivatedAt). Defaults to today."""
        ...


@runtime_checkable
class CategoriesProvider(Protocol):
    """Interface for category operations."""

    def get_categories(self) -> list[dict]:
        """Get all transaction categories."""
        ...


@runtime_checkable
class RecurringProvider(Protocol):
    """Interface for recurring transaction operations."""

    def get_recurring_transaction_items(
        self,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """Get recurring transaction items for a date range.

        Returns list of recurring items with stream, merchant, account,
        category, and payment status details.
        """
        ...


@runtime_checkable
class HoldingsProvider(Protocol):
    """Interface for investment holdings operations."""

    def get_holdings(
        self,
        account_ids: Optional[list[str]] = None,
        as_of_date: Optional[str] = None,
    ) -> list[dict]:
        """Get security-level holdings for investment accounts.

        Pass account_ids to filter to specific accounts, or None for the
        whole portfolio. as_of_date (YYYY-MM-DD) queries a historical
        snapshot; None means today.
        """
        ...


@runtime_checkable
class BalancesProvider(Protocol):
    """Interface for account balance history operations."""

    def download_balance_history(self, account_id: str) -> list[dict]:
        """Download daily balance snapshots for an account.

        Returns a list of {"date": str, "balance": float}.
        """
        ...

    def upload_balance_history(
        self, account_id: str, snapshots: list[dict], expected_token: int
    ) -> dict:
        """Replace an account's entire balance history with the given snapshots.

        expected_token must match the digest of the account's current history
        (from download_balance_history) — a read-before-write interlock.

        Returns {success, status, uploaded_count, previous_snapshots, ...}.
        """
        ...


@runtime_checkable
class Provider(
    TransactionsProvider,
    AccountsProvider,
    CategoriesProvider,
    RecurringProvider,
    HoldingsProvider,
    BalancesProvider,
    Protocol,
):
    """Combined provider interface for all operations."""
    pass
