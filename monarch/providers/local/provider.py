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
        self._recurring = self._db.table("recurring")
        self._rules = self._db.table("rules")

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
        if is_expense is not None:
            if is_expense:
                filtered = [t for t in filtered if (t.get("amount") or 0) < 0]
            else:
                filtered = [t for t in filtered if (t.get("amount") or 0) > 0]
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

    def get_accounts(self, include_closed: bool = False) -> list[dict]:
        """Get all accounts. Excludes closed/deactivated by default."""
        from ...accounts import is_closed
        accounts = self._accounts.all()
        if not include_closed:
            accounts = [a for a in accounts if not is_closed(a)]
        return accounts

    def get_categories(self) -> list[dict]:
        """Get all transaction categories."""
        return self._categories.all()

    def get_recurring_transaction_items(
        self,
        start_date: str,
        end_date: str,
    ) -> list[dict]:
        """Get recurring transaction items for a date range."""
        all_items = self._recurring.all()

        # Filter by date range
        filtered = [
            item for item in all_items
            if start_date <= item.get("date", "") <= end_date
        ]

        # Sort by date
        filtered.sort(key=lambda item: item.get("date", ""))
        return filtered

    def create_transactions(self, transactions: list[dict]) -> dict:
        """Create one or more transactions.

        Each input dict requires: date, account_id, amount, merchant_name,
        category_id. Optional: notes (default ""), update_balance (ignored
        in local provider).

        Returns a per-item result envelope so partial successes are visible:
            {
              "success": bool,           # True iff all items succeeded
              "success_count": int,
              "failure_count": int,
              "created": [{"index": int, "input": dict, "transaction": dict}],
              "failed":  [{"index": int, "input": dict, "error": str}],
            }
        """
        import uuid

        created: list[dict] = []
        failed: list[dict] = []

        for index, item in enumerate(transactions):
            try:
                date = item["date"]
                account_id = item["account_id"]
                amount = float(item["amount"])
                merchant_name = item["merchant_name"]
                category_id = item["category_id"]
                notes = item.get("notes", "") or ""

                Acct = Query()
                acct = self._accounts.search(Acct.id == account_id)
                if not acct:
                    raise ValueError(f"Account not found: {account_id}")
                acct = acct[0]

                Cat = Query()
                cat = self._categories.search(Cat.id == category_id)
                if not cat:
                    raise ValueError(f"Category not found: {category_id}")
                cat = cat[0]

                txn_id = str(uuid.uuid4().int)[:18]
                txn = {
                    "id": txn_id,
                    "amount": round(amount, 2),
                    "date": date,
                    "notes": notes,
                    "pending": False,
                    "hideFromReports": False,
                    "needsReview": False,
                    "plaidName": "",
                    "isRecurring": False,
                    "reviewStatus": None,
                    "isSplitTransaction": False,
                    "account": {
                        "id": account_id,
                        "displayName": acct.get("displayName", ""),
                    },
                    "category": {
                        "id": category_id,
                        "name": cat.get("name", ""),
                    },
                    "merchant": {
                        "id": str(uuid.uuid4().int)[:18],
                        "name": merchant_name,
                    },
                    "tags": [],
                }
                self._transactions.insert(txn)
                created.append({"index": index, "input": item, "transaction": txn})
            except (KeyError, ValueError, TypeError) as e:
                failed.append({"index": index, "input": item, "error": str(e)})

        return {
            "success": len(failed) == 0,
            "success_count": len(created),
            "failure_count": len(failed),
            "created": created,
            "failed": failed,
        }

    def delete_transactions(self, transaction_ids: list[str]) -> dict:
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
        deleted: list[dict] = []
        failed: list[dict] = []

        Txn = Query()
        for index, txn_id in enumerate(transaction_ids):
            try:
                existing = self._transactions.search(Txn.id == txn_id)
                if not existing:
                    raise ValueError(f"Transaction not found: {txn_id}")
                self._transactions.remove(Txn.id == txn_id)
                deleted.append({"index": index, "transaction_id": txn_id})
            except (ValueError, TypeError) as e:
                failed.append({"index": index, "transaction_id": txn_id, "error": str(e)})

        return {
            "success": len(failed) == 0,
            "success_count": len(deleted),
            "failure_count": len(failed),
            "deleted": deleted,
            "failed": failed,
        }

    def get_rules(self) -> list[dict]:
        """Get all transaction rules."""
        rules = self._rules.all()
        rules.sort(key=lambda r: r.get("order", 0))
        return rules

    def delete_rule(self, rule_id: str) -> dict:
        """Delete a rule by ID."""
        Rule = Query()
        result = self._rules.search(Rule.id == rule_id)
        if not result:
            raise ValueError(f"Rule not found: {rule_id}")
        self._rules.remove(Rule.id == rule_id)
        return {"deleted": True}

    def create_rule(
        self,
        merchant_criteria: Optional[list[dict]] = None,
        original_statement_criteria: Optional[list[dict]] = None,
        amount_criteria: Optional[dict] = None,
        account_ids: Optional[list[str]] = None,
        category_ids: Optional[list[str]] = None,
        set_merchant_action: Optional[str] = None,
        set_category_action: Optional[str] = None,
        add_tags_action: Optional[list[str]] = None,
        apply_to_existing: bool = False,
    ) -> dict:
        """Create a new transaction auto-categorization rule.

        Returns the same shape Monarch's API does: the new rule object,
        appended to the end of the rules list. `apply_to_existing` is
        accepted for parity with the real API but doesn't retroactively
        run the rule against transactions in the local store.
        """
        import uuid

        Cat = Query()
        Acct = Query()

        # Order is "last in the list" — Monarch's API uses 0-based ordering.
        existing_orders = [r.get("order", 0) for r in self._rules.all()]
        next_order = (max(existing_orders) + 1) if existing_orders else 0

        # Resolve set_category_action (a category id) to {id, name, icon}.
        set_cat = None
        if set_category_action:
            cat = self._categories.search(Cat.id == set_category_action)
            if not cat:
                raise ValueError(f"Category not found: {set_category_action}")
            set_cat = {"id": cat[0].get("id"), "name": cat[0].get("name"), "icon": cat[0].get("icon")}

        # Resolve accountIds to display names for the joined view.
        accounts_resolved = []
        for aid in account_ids or []:
            acct = self._accounts.search(Acct.id == aid)
            if acct:
                accounts_resolved.append({"id": aid, "displayName": acct[0].get("displayName", "")})

        rule_id = f"rule_{str(uuid.uuid4().int)[:12]}"
        rule = {
            "id": rule_id,
            "order": next_order,
            "merchantCriteriaUseOriginalStatement": False,
            "merchantCriteria": merchant_criteria,
            "originalStatementCriteria": original_statement_criteria,
            "merchantNameCriteria": None,
            "amountCriteria": amount_criteria,
            "categoryIds": category_ids,
            "accountIds": account_ids,
            "categories": [],
            "accounts": accounts_resolved,
            "setMerchantAction": set_merchant_action,
            "setCategoryAction": set_cat,
            "addTagsAction": add_tags_action,
            "linkGoalAction": None,
            "reviewStatusAction": None,
            "setHideFromReportsAction": False,
            "sendNotificationAction": False,
            "splitTransactionsAction": None,
            "recentApplicationCount": 0,
            "lastAppliedAt": None,
        }
        self._rules.insert(rule)
        return {"rule": rule, "success": True}

    def bulk_mark_reviewed(
        self, transaction_ids: list[str], needs_review: bool = False
    ) -> dict:
        """Bulk update the needsReview flag on a list of transactions.

        Mirrors the real API's bulk update: only the explicit field is
        changed; other transaction fields are preserved. Returns the
        shape Monarch's `bulkUpdateTransactions` mutation returns.
        """
        Txn = Query()
        affected = 0
        for txn_id in transaction_ids:
            existing = self._transactions.search(Txn.id == txn_id)
            if existing:
                self._transactions.update({"needsReview": needs_review}, Txn.id == txn_id)
                affected += 1
        status = "needing review" if needs_review else "reviewed"
        return {
            "success": True,
            "affectedCount": affected,
            "message": f"Marked {affected} transactions as {status}",
        }

    def split_transaction(
        self, transaction_id: str, split_data: list[dict]
    ) -> dict:
        """Split a transaction across multiple categories.

        Validates that the sum of split amounts equals the original's
        amount (Monarch enforces this). Marks the original as split and
        records the splits on it. Returns the updated transaction.
        """
        import uuid

        Txn = Query()
        existing = self._transactions.search(Txn.id == transaction_id)
        if not existing:
            raise ValueError(f"Transaction not found: {transaction_id}")
        original = existing[0]

        if split_data:
            # Sum must equal (within rounding) the original amount.
            split_sum = round(sum(float(s.get("amount", 0)) for s in split_data), 2)
            original_amount = round(float(original.get("amount", 0)), 2)
            if split_sum != original_amount:
                raise ValueError(
                    f"Split sum {split_sum} does not equal original amount {original_amount}"
                )

        Cat = Query()
        materialized_splits = []
        for s in split_data:
            cat_id = s.get("categoryId")
            cat = self._categories.search(Cat.id == cat_id) if cat_id else []
            if cat_id and not cat:
                raise ValueError(f"Category not found: {cat_id}")
            materialized_splits.append({
                "id": str(uuid.uuid4().int)[:18],
                "amount": round(float(s.get("amount", 0)), 2),
                "category": {"id": cat_id, "name": cat[0].get("name", "")} if cat else None,
                "merchant": {"name": s.get("merchantName")} if s.get("merchantName") else None,
                "notes": s.get("notes", ""),
            })

        self._transactions.update(
            {"isSplitTransaction": bool(split_data), "splits": materialized_splits},
            Txn.id == transaction_id,
        )
        updated = self._transactions.search(Txn.id == transaction_id)[0]
        return {
            "transaction": updated,
            "success": True,
            "message": f"Transaction {transaction_id} split into {len(split_data)} parts",
        }

    def mark_not_recurring(self, stream_id: str) -> dict:
        """Remove a recurring stream from the catalog.

        Mirrors Monarch's `markStreamAsNotRecurring` mutation: removes
        all items with the given stream id from the recurring table.
        """
        Item = Query()
        before = len(self._recurring.search(Item.stream.id == stream_id))
        if before == 0:
            raise ValueError(f"Stream not found: {stream_id}")
        self._recurring.remove(Item.stream.id == stream_id)
        return {
            "success": True,
            "result": {"streamId": stream_id, "removed": before},
        }

    def update_recurring(
        self,
        stream_id: str,
        status: Optional[str] = None,
        amount: Optional[float] = None,
        frequency: Optional[str] = None,
    ) -> dict:
        """Update fields on a recurring stream.

        Updates the nested `stream` object on every item carrying that
        stream id. Status (`active`/`inactive`/`removed`) maps to
        merchant recurrence state in the real API; here we just record
        it on the stream object. `removed` short-circuits to
        `mark_not_recurring` for behavior parity.
        """
        if status == "removed":
            return self.mark_not_recurring(stream_id)

        Item = Query()
        items = self._recurring.search(Item.stream.id == stream_id)
        if not items:
            raise ValueError(f"Stream not found: {stream_id}")

        for item in items:
            new_stream = dict(item.get("stream", {}))
            if amount is not None:
                new_stream["amount"] = round(float(amount), 2)
            if frequency is not None:
                new_stream["frequency"] = frequency
            if status is not None:
                new_stream["status"] = status
            self._recurring.update({"stream": new_stream}, Item.stream.id == stream_id)

        return {
            "success": True,
            "result": {
                "streamId": stream_id,
                "status": status,
                "amount": amount,
                "frequency": frequency,
            },
        }

    def close(self):
        """Close the database connection."""
        self._db.close()
