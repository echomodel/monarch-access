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


async def list_accounts(include_closed: bool = False) -> dict[str, Any]:
    """List all financial accounts from Monarch Money.

    Returns account IDs, names, types, balances, and institution names.
    Use account IDs with list_transactions to filter by account.
    Closed/deactivated accounts are excluded by default.

    Args:
        include_closed: Include closed/deactivated accounts (default: false).
    """
    try:
        return await sdk.get_accounts(include_closed=include_closed)
    except AuthenticationError as e:
        return {"error": str(e), "accounts": [], "count": 0}
    except Exception as e:
        logger.error(f"Error listing accounts: {e}")
        return {"error": str(e), "accounts": [], "count": 0}


async def count_accounts() -> dict[str, Any]:
    """Count the user's open Monarch Money accounts.

    Returns only {"count": N}. Useful as a cheap connectivity and
    authentication check.
    """
    try:
        return await sdk.count_accounts()
    except AuthenticationError as e:
        return {"error": str(e), "count": 0}
    except Exception as e:
        logger.error(f"Error counting accounts: {e}")
        return {"error": str(e), "count": 0}


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


async def download_balance_history(
    account_id: str,
) -> dict[str, Any]:
    """Download an account's daily balance history from Monarch Money.

    Returns one snapshot per day from account creation through today, each
    {"date": "YYYY-MM-DD", "balance": float}. Liabilities carry negative
    balances. This is read-only — useful for auditing a balance curve or
    capturing it before an upload.

    The response also includes "history_token" — a digest number of the current
    history. You MUST pass that exact token to upload_balance_history to replace
    this account's history; uploading without first reading here (and capturing
    the snapshots for rollback) is blocked by design.

    Args:
        account_id: The account to read. Get IDs from list_accounts.
    """
    try:
        return await sdk.download_balance_history(account_id)
    except AuthenticationError as e:
        return {"error": str(e), "account_id": account_id, "snapshots": [], "count": 0}
    except Exception as e:
        logger.error(f"Error downloading balance history: {e}")
        return {"error": str(e), "account_id": account_id, "snapshots": [], "count": 0}


async def upload_balance_history(
    account_id: str,
    snapshots: list[dict],
    expected_token: int,
) -> dict[str, Any]:
    """Replace an account's entire balance history with the given snapshots.

    WARNING: this REPLACES all existing balance snapshots for the account and
    sets its currentBalance to the final (latest-dated) row. There is no append
    mode — the snapshots you pass become the account's whole curve. Balance
    history is independent of transactions: this creates no transactions and
    does not affect income/expense reports.

    REQUIRED read-before-write: you must first call download_balance_history for
    this account and pass its returned "history_token" as expected_token here.
    The upload re-reads the current history, recomputes the token, and refuses
    (changing nothing) if it does not match — which guarantees you have captured
    the prior history (so the replace is reversible) and that nothing changed
    underneath you. On success, the replaced history is returned under
    "previous_snapshots" for rollback.

    Use for correcting stale balances on accounts that stopped syncing,
    importing history for manual accounts, or migrating a balance curve
    between accounts (e.g. a loan servicer transfer).

    Args:
        account_id: The account whose history to overwrite. Get IDs from
            list_accounts.
        snapshots: List of {"date": "YYYY-MM-DD", "balance": float} (negative
            for liabilities). This is the COMPLETE replacement history.
        expected_token: The "history_token" from a download_balance_history call
            on this same account, just performed. Proves you read (and captured)
            the current history before replacing it.
    """
    try:
        if not snapshots:
            return {"success": False, "error": "No snapshots provided", "uploaded_count": 0}
        return await sdk.upload_balance_history(account_id, snapshots, expected_token)
    except (AuthenticationError, APIError) as e:
        return {"error": str(e), "success": False, "uploaded_count": 0}
    except Exception as e:
        logger.error(f"Error uploading balance history: {e}")
        return {"error": str(e), "success": False, "uploaded_count": 0}


async def update_account(
    account_id: str,
    name: Optional[str] = None,
    include_in_net_worth: Optional[bool] = None,
    hidden: Optional[bool] = None,
    reopen: bool = False,
) -> dict[str, Any]:
    """Update an account's settings: rename, exclude from net worth, hide, or reopen.

    Only specified fields are changed. To CLOSE an account, use close_account
    instead — closing and excluding are different operations (see close_account).

    Args:
        account_id: The account to update. Get IDs from list_accounts.
        name: New display name for the account.
        include_in_net_worth: Set false to EXCLUDE the account from net worth.
            Exclusion removes the balance from net worth retroactively across
            all history. Set true to include it again. (To stop counting an
            account going forward while keeping its history, close it instead.)
        hidden: Set true to hide the account from the accounts list.
        reopen: Set true to REOPEN a closed account — clears its deactivation
            date, restoring it to active. This is the inverse of close_account.
    """
    try:
        return await sdk.update_account(
            account_id,
            name=name,
            include_in_net_worth=include_in_net_worth,
            hidden=hidden,
            reopen=reopen,
        )
    except (AuthenticationError, APIError) as e:
        return {"error": str(e), "account": None, "success": False}
    except Exception as e:
        logger.error(f"Error updating account: {e}")
        return {"error": str(e), "account": None, "success": False}


async def close_account(
    account_id: str,
    close_date: Optional[str] = None,
) -> dict[str, Any]:
    """Close an account, preserving its balance history in net worth.

    Closing sets the account's deactivation date: its balance reads $0 from
    the close date forward, but its historical balance snapshots REMAIN in net
    worth (no retroactive change). This is the right way to retire a manual
    placeholder account once a real linked account replaces it — net worth
    neither double-counts going forward nor drops retroactively.

    This differs from excluding an account from net worth (update_account with
    include_in_net_worth=false), which removes the balance from history
    retroactively. Closing is NON-DESTRUCTIVE and fully reversible: it only sets
    a deactivation date and keeps all data. To undo, call update_account with
    reopen=true.

    Args:
        account_id: The account to close. Get IDs from list_accounts.
        close_date: Close date in YYYY-MM-DD format. Defaults to today.
    """
    try:
        return await sdk.close_account(account_id, close_date=close_date)
    except (AuthenticationError, APIError) as e:
        return {"error": str(e), "account": None, "success": False}
    except Exception as e:
        logger.error(f"Error closing account: {e}")
        return {"error": str(e), "account": None, "success": False}


async def get_holdings(
    account_ids: Optional[list[str]] = None,
    as_of_date: Optional[str] = None,
) -> dict[str, Any]:
    """Get security-level investment holdings from Monarch Money.

    Returns the positions held inside brokerage/investment accounts — the
    share-level detail that account balances alone don't expose. Each holding
    includes: ticker, name, type, quantity (shares), closing_price,
    current_value, cost_basis, is_manual, day change, and tax_lots (a list of
    {acquisition_quantity, cost_basis_per_unit} per acquisition lot).

    cost_basis may be null for synced positions where the data provider did
    not supply basis.

    Args:
        account_ids: Investment account IDs to filter by. Get IDs from
            list_accounts. Omit for the whole portfolio's aggregated holdings.
        as_of_date: YYYY-MM-DD. Returns the holdings snapshot as of that date,
            enabling historical position lookups. Defaults to today.
    """
    try:
        return await sdk.get_holdings(account_ids=account_ids, as_of_date=as_of_date)
    except AuthenticationError as e:
        return {"error": str(e), "holdings": [], "count": 0}
    except Exception as e:
        logger.error(f"Error getting holdings: {e}")
        return {"error": str(e), "holdings": [], "count": 0}


async def list_transactions(
    limit: int = 100,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    account_ids: Optional[list[str]] = None,
    category_ids: Optional[list[str]] = None,
    search: Optional[str] = None,
    is_expense: Optional[bool] = None,
    tags: Optional[list[str]] = None,
) -> dict[str, Any]:
    """List transactions from Monarch Money with optional filters.

    Filter by date range, accounts, categories, search text, or transaction direction.
    Returns transaction details including amounts, merchants, categories, and notes.

    Args:
        limit: Maximum number of transactions to return (default: 100, max: 1000).
        start_date: Start date filter, inclusive (YYYY-MM-DD format).
        end_date: End date filter, inclusive (YYYY-MM-DD format).
        account_ids: List of account IDs to filter by. Get IDs from list_accounts.
        category_ids: List of category IDs to filter by. Get IDs from list_categories.
        search: Search text to filter by merchant name, notes, or description.
        is_expense: Filter by amount sign, matching Monarch's rule terminology. True = negative amounts (charges, withdrawals, payments made). False = positive amounts (deposits, refunds, payments received). A refund on an expense category has a positive amount, so is_expense=false. Omit for all transactions.
        tags: List of tag IDs to filter by — returns transactions carrying ANY of them. Get tag IDs from list_tags. E.g. to see everything tagged "agent-reviewed", call list_tags, find its id, then pass tags=[that id].
    """
    try:
        return await sdk.get_transactions(
            limit=max(1, min(1000, limit)),
            start_date=start_date,
            end_date=end_date,
            account_ids=account_ids,
            category_ids=category_ids,
            search=search,
            is_expense=is_expense,
            tags=tags,
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


async def attach_transaction(
    transaction_id: str,
    content_base64: str,
    filename: Optional[str] = None,
) -> dict[str, Any]:
    """Attach a file (receipt, check image, statement PDF) to a transaction
    as a native Monarch attachment. Monarch supports multiple attachments per
    transaction — call once per file (e.g. check front, check back, invoice).

    The file is provided as base64-encoded bytes (content_base64).

    SECURITY — this tool deliberately does NOT accept a server-side file
    path. When this server runs over HTTP it is multi-tenant and reachable by
    untrusted callers; reading an arbitrary path off the server's filesystem
    would let a caller exfiltrate other users' data and process secrets (e.g.
    /proc/self/environ, the user data volume). The MCP surface therefore only
    accepts caller-supplied bytes. To attach a local file by path, use the
    `monarch transactions attach <transaction_id> <file_path>` CLI, which runs
    as you on your own machine where reading your own files is not a privilege
    escalation.

    Args:
        transaction_id: The ID of the transaction to attach to.
        content_base64: Base64-encoded file bytes.
        filename: Display name shown in Monarch (default: "attachment").
    """
    try:
        return await sdk.attach_transaction(
            transaction_id,
            content_base64=content_base64,
            filename=filename,
        )
    except (AuthenticationError, APIError) as e:
        return {"error": str(e), "success": False}
    except Exception as e:
        logger.error(f"Error attaching to transaction: {e}")
        return {"error": str(e), "success": False}


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
        merchant_name: New merchant name to set (created if it does not
            exist). Affects only this transaction; future transactions from
            the same payee keep their original merchant unless a rule
            reassigns them (see create_rule).
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


async def create_transactions(
    transactions: list[dict],
) -> dict[str, Any]:
    """Create one or more manually-entered transactions in Monarch Money.

    Use for transactions a linked account's sync won't produce — tracking
    gifts, loans, cash spending, or recording income events (e.g. equity
    vesting) — against ANY account, manual or synced. Manually-added
    transactions coexist with synced data and are not removed by future
    syncs. Pass a list even for a single transaction.

    Each item in the list is processed independently. Partial success is
    reported: items that fail validation or the API call are returned in
    "failed" with their original input and error message; successful items
    are returned in "created" with the new transaction. Position in the
    input list is preserved via "index" so failures can be correlated.

    Args:
        transactions: List of transaction inputs. Each item must include:
            - date (str): Transaction date in YYYY-MM-DD format.
            - account_id (str): The ID of the account — manual OR synced. Get IDs from list_accounts.
            - amount (float): Transaction amount. Negative for expenses, positive for income.
            - merchant_name (str): Name of the merchant or payee.
            - category_id (str): Category ID. Get IDs from list_categories.
            Optional:
            - notes (str): Notes or description.
            - update_balance (bool): Whether to adjust the account's balance.
              Defaults to False — the OPPOSITE of the Monarch web UI, where
              the balance-adjust toggle is on by default. Leave False to
              record an audit-trail or income entry that does NOT change the
              balance (e.g. income booked against a synced account whose
              balance the sync already maintains); pass True to move the
              balance.
    """
    try:
        if not transactions:
            return {
                "success": False,
                "success_count": 0,
                "failure_count": 0,
                "created": [],
                "failed": [],
                "error": "No transactions provided",
            }
        return await sdk.create_transactions(transactions)
    except (AuthenticationError, APIError) as e:
        return {
            "error": str(e),
            "success": False,
            "success_count": 0,
            "failure_count": len(transactions),
            "created": [],
            "failed": [],
        }
    except Exception as e:
        logger.error(f"Error creating transactions: {e}")
        return {
            "error": str(e),
            "success": False,
            "success_count": 0,
            "failure_count": len(transactions),
            "created": [],
            "failed": [],
        }


async def delete_transactions(
    transaction_ids: list[str],
) -> dict[str, Any]:
    """Delete one or more transactions from Monarch Money. This action cannot be undone.

    Pass a list even for a single transaction. Each ID is processed
    independently. Partial success is reported: successfully deleted IDs
    are returned in "deleted", failures in "failed" with the ID and error
    message. Position in the input list is preserved via "index".

    Args:
        transaction_ids: List of transaction IDs to delete.
    """
    try:
        if not transaction_ids:
            return {
                "success": False,
                "success_count": 0,
                "failure_count": 0,
                "deleted": [],
                "failed": [],
                "error": "No transaction IDs provided",
            }
        return await sdk.delete_transactions(transaction_ids)
    except (AuthenticationError, APIError) as e:
        return {
            "error": str(e),
            "success": False,
            "success_count": 0,
            "failure_count": len(transaction_ids),
            "deleted": [],
            "failed": [],
        }
    except Exception as e:
        logger.error(f"Error deleting transactions: {e}")
        return {
            "error": str(e),
            "success": False,
            "success_count": 0,
            "failure_count": len(transaction_ids),
            "deleted": [],
            "failed": [],
        }


async def list_recurring() -> dict[str, Any]:
    """List tracked recurring obligations from Monarch Money.

    Returns bills, subscriptions, loan payments, and credit card payments.
    Each item includes stream_id, merchant, merchant_id, expected amount,
    frequency, category, account, due_date, and last_paid_date.

    One merchant can have several streams (several items with the same
    merchant_id). Monarch's detection often creates duplicates (same amount
    and frequency) or keeps stale ones (old amount, no recent last_paid_date).
    Before changing a stream with update_recurring, check whether its
    merchant_id appears more than once: edits are only possible when it is
    the merchant's only stream.
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

    Takes a stream_id from list_recurring. Monarch edits recurrence settings
    per merchant, and when a merchant has several recurring streams (often
    duplicates) an edit can land on a different stream than the one asked
    for. So amount/frequency/active changes are made only when the stream is
    its merchant's only stream; otherwise an error lists the merchant's
    streams (amount, frequency, base date) with next steps and nothing is
    changed. Only works on merchant-based streams (not credit report
    liabilities).

    Workflow for a merchant with several streams:
    1. Decide with list_recurring whether the extra streams are the same
       obligation (duplicate or stale) or genuinely separate ones (for
       example two insurance policies billed by one company).
    2. Duplicates/stale: confirm with the user, remove each with
       status='removed' (irreversible), then edit the remaining stream.
    3. Separate obligations: split them into separate merchants with a
       transaction rule (see create_rule), so each obligation has its own
       merchant and stream.

    Status values:
    - active: reactivate the merchant's recurrence (reversible)
    - inactive: cancel the merchant's recurrence (reversible)
    - removed: remove exactly this one stream (irreversible); the merchant's
      other streams stay. Use this to drop duplicate or stale streams.

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
    """Permanently remove one recurring stream. Same as update_recurring with status='removed'.

    Removes only this stream; the merchant's other streams stay. Irreversible:
    there is no call that restores it, so confirm with the user first. Use it
    to clear duplicate or stale streams of a merchant before editing the one
    that remains. For a reversible change on a merchant's only stream, use
    update_recurring(status='inactive').

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


async def list_rules() -> dict[str, Any]:
    """List all transaction auto-categorization rules from Monarch Money.

    Returns rules with their criteria (merchant match, amount, account, category)
    and actions (set category, set merchant, add tags, etc.).
    Rules are applied in order to new transactions.
    """
    try:
        return await sdk.get_rules()
    except AuthenticationError as e:
        return {"error": str(e), "rules": [], "count": 0}
    except Exception as e:
        logger.error(f"Error listing rules: {e}")
        return {"error": str(e), "rules": [], "count": 0}


async def create_rule(
    set_category_action: Optional[str] = None,
    set_merchant_action: Optional[str] = None,
    merchant_criteria: Optional[list[dict]] = None,
    original_statement_criteria: Optional[list[dict]] = None,
    amount_criteria: Optional[dict] = None,
    account_ids: Optional[list[str]] = None,
    category_ids: Optional[list[str]] = None,
    add_tags_action: Optional[list[str]] = None,
    apply_to_existing: bool = False,
) -> dict[str, Any]:
    """Create a new transaction auto-categorization rule.

    Rules match transactions by criteria and apply actions. At least one
    criterion and one action are required. Monarch applies rules to new
    transactions as they arrive; apply_to_existing also applies the rule to
    matching past transactions.

    Splitting one merchant into several (e.g. separate insurance policies,
    each with its own recurring stream): renaming a transaction's merchant
    with update_transaction changes only that transaction, and future
    transactions keep arriving under the original merchant. A rule makes the
    split last: set_merchant_action to the new merchant name, matching on
    criteria that stay true for every future payment of that obligation —
    the payee (merchant_criteria or original_statement_criteria) plus the
    paying account (account_ids), and amount_criteria only if the amount is
    fixed. Do not use category_ids as a criterion when the rule (or
    Monarch's learned categorization) changes the category: new
    transactions then arrive in the new category, the rule stops matching,
    and the split silently stops. Use apply_to_existing=True to move past
    payments, and check the result with list_transactions.

    Recurring "paid" status may not follow moved payments right away: the
    old merchant's stream can keep them while the new merchant's stream
    shows unpaid. Check with list_recurring after moving payments. If the
    new stream still shows unpaid, set its amount (and frequency) to the
    current payment with update_recurring, which makes Monarch re-match
    within minutes. Small differences between payment and stream amount
    are tolerated; large ones (for example after a premium change) leave
    the payment unmatched.

    Args:
        set_category_action: Category ID to assign to matching transactions.
        set_merchant_action: Merchant name to set (string, not ID — Monarch resolves it).
        merchant_criteria: List of merchant match conditions. Each: {"operator": "contains"|"eq", "value": "search term"}.
        original_statement_criteria: List of original statement match conditions. Each: {"operator": "contains"|"eq", "value": "search term"}.
        amount_criteria: Amount filter. Example: {"operator": "gt", "is_expense": true, "value": 5.0}. Operators: "gt", "lt", "eq". For ranges: {"operator": "between", "is_expense": true, "range": {"lower": 10, "upper": 50}}.
        account_ids: Limit rule to specific account IDs.
        category_ids: Limit rule to specific source category IDs (match transactions already in these categories).
        add_tags_action: List of tag IDs to add to matching transactions.
        apply_to_existing: If true, retroactively apply to existing matching transactions.
    """
    try:
        return await sdk.create_rule(
            merchant_criteria=merchant_criteria,
            original_statement_criteria=original_statement_criteria,
            amount_criteria=amount_criteria,
            account_ids=account_ids,
            category_ids=category_ids,
            set_merchant_action=set_merchant_action,
            set_category_action=set_category_action,
            add_tags_action=add_tags_action,
            apply_to_existing=apply_to_existing,
        )
    except (AuthenticationError, APIError) as e:
        return {"error": str(e), "success": False}
    except Exception as e:
        logger.error(f"Error creating rule: {e}")
        return {"error": str(e), "success": False}


async def delete_rule(
    rule_id: str,
) -> dict[str, Any]:
    """Delete a transaction rule by ID.

    Get rule IDs from list_rules. This cannot be undone. The result's
    success/deleted reflect whether the rule is gone from the rules list
    afterwards (verified by re-reading it).

    Args:
        rule_id: The ID of the rule to delete.
    """
    try:
        return await sdk.delete_rule(rule_id)
    except (AuthenticationError, APIError) as e:
        return {"error": str(e), "success": False}
    except Exception as e:
        logger.error(f"Error deleting rule: {e}")
        return {"error": str(e), "success": False}


async def list_tags() -> dict[str, Any]:
    """List all transaction tags in the household (id, name, color).

    Use a tag's id to filter transactions by tag via list_transactions(tags=[id]).
    """
    try:
        return await sdk.list_tags()
    except AuthenticationError as e:
        return {"error": str(e), "tags": [], "count": 0}
    except Exception as e:
        logger.error(f"Error listing tags: {e}")
        return {"error": str(e), "tags": [], "count": 0}


async def add_transaction_tag(transaction_id: str, tag_name: str) -> dict[str, Any]:
    """Add a tag to a transaction WITHOUT losing its existing tags.

    Resolves the tag by name (creating it if it doesn't exist), then adds it to the
    transaction's current tags — read-union-write, so it is non-destructive and
    idempotent. Use it to mark transactions (e.g. tag everything an agent reviewed
    with "agent-reviewed"), then later filter via list_transactions(tags=[id]).

    Args:
        transaction_id: The ID of the transaction to tag.
        tag_name: The tag name to add (created if it doesn't exist yet).
    """
    try:
        return await sdk.add_transaction_tag(transaction_id, tag_name)
    except AuthenticationError as e:
        return {"error": str(e), "success": False}
    except Exception as e:
        logger.error(f"Error adding tag: {e}")
        return {"error": str(e), "success": False}


async def remove_transaction_tag(transaction_id: str, tag_name: str) -> dict[str, Any]:
    """Remove a tag from a transaction, preserving its other tags (no-op if absent).

    Args:
        transaction_id: The ID of the transaction.
        tag_name: The tag name to remove.
    """
    try:
        return await sdk.remove_transaction_tag(transaction_id, tag_name)
    except AuthenticationError as e:
        return {"error": str(e), "success": False}
    except Exception as e:
        logger.error(f"Error removing tag: {e}")
        return {"error": str(e), "success": False}
