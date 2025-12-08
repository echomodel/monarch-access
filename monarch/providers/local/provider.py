"""Local provider implementation using TinyDB."""

from pathlib import Path
from typing import Optional

from tinydb import TinyDB, Query


class LocalProvider:
    """Provider that uses a local JSON file as a database."""

    def __init__(self, db_path: Optional[Path] = None):
        if db_path is None:
            db_path = Path(__file__).parent / "test_data.json"
        self._db = TinyDB(db_path)
        self._transactions = self._db.table("transactions")
        self._accounts = self._db.table("accounts")
        self._categories = self._db.table("categories")

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
        all_txns = self._transactions.all()

        # Apply filters
        filtered = all_txns

        if start_date:
            filtered = [t for t in filtered if t.get("date", "") >= start_date]
        if end_date:
            filtered = [t for t in filtered if t.get("date", "") <= end_date]
        if account_ids:
            filtered = [t for t in filtered if t.get("account", {}).get("id") in account_ids]
        if category_ids:
            filtered = [t for t in filtered if t.get("category", {}).get("id") in category_ids]
        if search:
            search_lower = search.lower()
            filtered = [
                t for t in filtered
                if search_lower in (t.get("merchant", {}).get("name", "") or "").lower()
                or search_lower in (t.get("notes", "") or "").lower()
                or search_lower in (t.get("plaidName", "") or "").lower()
            ]

        # Sort by date descending (newest first)
        filtered.sort(key=lambda t: t.get("date", ""), reverse=True)

        total_count = len(filtered)
        results = filtered[offset:offset + limit]

        return {"totalCount": total_count, "results": results}

    def get_transaction(self, transaction_id: str) -> Optional[dict]:
        """Get a single transaction by ID."""
        Txn = Query()
        result = self._transactions.search(Txn.id == transaction_id)
        return result[0] if result else None

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
        Txn = Query()
        txn = self._transactions.search(Txn.id == transaction_id)
        if not txn:
            raise ValueError(f"Transaction not found: {transaction_id}")

        txn = txn[0]
        updates = {}

        if category_id is not None:
            # Look up category
            Cat = Query()
            cat = self._categories.search(Cat.id == category_id)
            if cat:
                updates["category"] = {"id": category_id, "name": cat[0].get("name", "")}
        if merchant_name is not None:
            updates["merchant"] = {
                "id": txn.get("merchant", {}).get("id", ""),
                "name": merchant_name,
            }
        if notes is not None:
            updates["notes"] = notes
        if amount is not None:
            updates["amount"] = amount
        if date is not None:
            updates["date"] = date
        if hide_from_reports is not None:
            updates["hideFromReports"] = hide_from_reports
        if needs_review is not None:
            updates["needsReview"] = needs_review

        if updates:
            self._transactions.update(updates, Txn.id == transaction_id)

        # Return updated transaction
        return self._transactions.search(Txn.id == transaction_id)[0]

    def get_accounts(self) -> list[dict]:
        """Get all accounts."""
        return self._accounts.all()

    def get_categories(self) -> list[dict]:
        """Get all transaction categories."""
        return self._categories.all()

    def close(self):
        """Close the database connection."""
        self._db.close()
