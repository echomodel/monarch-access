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


@runtime_checkable
class AccountsProvider(Protocol):
    """Interface for account operations."""

    def get_accounts(self) -> list[dict]:
        """Get all accounts."""
        ...


@runtime_checkable
class CategoriesProvider(Protocol):
    """Interface for category operations."""

    def get_categories(self) -> list[dict]:
        """Get all transaction categories."""
        ...


@runtime_checkable
class Provider(TransactionsProvider, AccountsProvider, CategoriesProvider, Protocol):
    """Combined provider interface for all operations."""
    pass
