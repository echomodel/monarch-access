# Monarch MCP Server Tools

All tools exposed by the Monarch MCP Server for use by AI assistants and MCP clients.

## Tools

### `list_accounts`

List all financial accounts from Monarch Money.

**Input:** None

**Output:**
```json
{
  "accounts": [
    {
      "id": "account_id_here",
      "displayName": "Account Name",
      "type": { "display": "Checking" },
      "currentBalance": 1234.56,
      "institution": { "name": "Bank Name" }
    }
  ],
  "count": 5
}
```

---

### `list_categories`

List all transaction categories from Monarch Money.

**Input:** None

**Output:**
```json
{
  "categories": [
    {
      "id": "category_id_here",
      "name": "Groceries",
      "group": { "name": "Food & Drink", "type": "expense" }
    }
  ],
  "count": 50
}
```

---

### `list_transactions`

List transactions with optional filters.

**Input:**
- `limit` (integer, optional): Max transactions to return (default: 100, max: 1000)
- `start_date` (string, optional): Start date filter (YYYY-MM-DD)
- `end_date` (string, optional): End date filter (YYYY-MM-DD)
- `account_ids` (array of strings, optional): Filter by account IDs
- `category_ids` (array of strings, optional): Filter by category IDs
- `search` (string, optional): Text search in merchant names and notes

**Output:**
```json
{
  "transactions": [
    {
      "id": "transaction_id_here",
      "amount": -127.43,
      "date": "2025-01-15",
      "merchant": { "name": "Store Name" },
      "category": { "name": "Shopping" },
      "account": { "displayName": "Account Name" },
      "notes": "",
      "needsReview": false
    }
  ],
  "count": 100,
  "totalCount": 500
}
```

---

### `get_transaction`

Get details of a single transaction by ID.

**Input:**
- `transaction_id` (string, required)

---

### `update_transaction`

Update a transaction's category, merchant, notes, or status.

**Input:**
- `transaction_id` (string, required)
- `category_id` (string, optional): New category ID
- `merchant_name` (string, optional): New merchant name
- `notes` (string, optional): Notes (empty string clears)
- `needs_review` (boolean, optional): Review status
- `hide_from_reports` (boolean, optional): Hide from reports/budgets

---

### `mark_transactions_reviewed`

Bulk mark transactions as reviewed or needing review.

**Input:**
- `transaction_ids` (array of strings, required)
- `needs_review` (boolean, optional): false = reviewed (default), true = needing review

---

### `split_transaction`

Split a transaction into multiple parts with different categories.

**Input:**
- `transaction_id` (string, required)
- `splits` (array of objects, required): Each with `amount` (number), `categoryId` (string), optional `merchantName`, `notes`

---

### `create_transactions`

Create one or more manual transactions. Pass a list even for a single
transaction. Each item is processed independently — partial successes are
reported.

**Input:**
- `transactions` (array of objects, required). Each item:
  - `date` (string, required): YYYY-MM-DD
  - `account_id` (string, required): Must be a manual account
  - `amount` (float, required): Negative for expenses, positive for income
  - `merchant_name` (string, required)
  - `category_id` (string, required)
  - `notes` (string, optional)
  - `update_balance` (boolean, optional): Whether to update account balance

**Output:**
```json
{
  "success": false,
  "success_count": 2,
  "failure_count": 1,
  "created": [
    {"index": 0, "input": {...}, "transaction": {...}},
    {"index": 2, "input": {...}, "transaction": {...}}
  ],
  "failed": [
    {"index": 1, "input": {...}, "error": "Category not found: ..."}
  ]
}
```

`success` is `true` only if every item succeeded. `index` matches the
position in the input list so failures can be correlated.

---

### `delete_transactions`

Delete one or more transactions. Cannot be undone. Pass a list even for a
single ID. Each ID is processed independently — partial successes are
reported.

**Input:**
- `transaction_ids` (array of strings, required)

**Output:**
```json
{
  "success": false,
  "success_count": 1,
  "failure_count": 1,
  "deleted": [
    {"index": 0, "transaction_id": "..."}
  ],
  "failed": [
    {"index": 1, "transaction_id": "...", "error": "Transaction not found"}
  ]
}
```

---

### `list_recurring`

List tracked recurring obligations (bills, subscriptions, loan payments).

**Input:** None

**Output:**
```json
{
  "recurring": [
    {
      "stream_id": "...",
      "merchant": "Netflix",
      "amount": -15.99,
      "frequency": "monthly",
      "category": "Entertainment",
      "is_active": true,
      "paid_this_month": true
    }
  ],
  "count": 12
}
```

---

### `update_recurring`

Update a recurring stream's status, amount, or frequency.

**Input:**
- `stream_id` (string, required)
- `status` (string, optional): `active`, `inactive` (reversible), or `removed` (permanent)
- `amount` (float, optional): New amount
- `frequency` (string, optional): `monthly`, `biweekly`, `weekly`, etc.

---

### `mark_as_not_recurring`

**Deprecated** — use `update_recurring` with `status='removed'` instead.

Permanently remove a recurring stream. Removes ALL streams for the merchant.

**Input:**
- `stream_id` (string, required)

---

## Example Usage Flow

1. **List accounts** to discover IDs and balances:
   ```
   list_accounts()
   ```

2. **List transactions** for a date range:
   ```
   list_transactions(start_date="2025-01-01", limit=50)
   ```

3. **Update a transaction** category:
   ```
   update_transaction(transaction_id="...", category_id="...")
   ```

4. **Mark transactions as reviewed**:
   ```
   mark_transactions_reviewed(transaction_ids=["...", "..."])
   ```

## Best Practices

- Use `list_accounts` and `list_categories` first to discover IDs
- Filter transactions by date range to avoid large result sets
- Use the `search` parameter for finding specific transactions
- Use `split_transaction` for purchases that span multiple categories
