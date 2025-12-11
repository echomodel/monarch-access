# Monarch MCP Server Tools and Resources

This document describes all tools and resources exposed by the Monarch MCP Server for use by LLMs and MCP clients.

## Tools

Tools allow LLMs to query and modify your Monarch Money financial data.

### `list_accounts`

**Purpose:** Retrieve all financial accounts from Monarch Money.

**Input:** None

**Output:**
```json
{
  "accounts": [
    {
      "id": "account_id_here",
      "displayName": "Account Name",
      "type": {
        "display": "Checking"
      },
      "currentBalance": 1234.56,
      "institution": {
        "name": "Bank Name"
      }
    }
  ],
  "count": 5
}
```

**Use Cases:**
- View all connected accounts and balances
- Find account IDs for filtering transactions
- Get an overview of financial accounts

---

### `list_categories`

**Purpose:** Retrieve all transaction categories from Monarch Money.

**Input:** None

**Output:**
```json
{
  "categories": [
    {
      "id": "category_id_here",
      "name": "Groceries",
      "group": {
        "name": "Food & Drink",
        "type": "expense"
      }
    }
  ],
  "count": 50
}
```

**Use Cases:**
- Discover available categories for filtering
- Find category IDs for updating transactions
- Understand category organization

---

### `list_transactions`

**Purpose:** Retrieve transactions with optional filters.

**Input:**
- `limit` (integer, optional): Maximum transactions to return (default: 100, max: 1000)
- `start_date` (string, optional): Start date filter in YYYY-MM-DD format
- `end_date` (string, optional): End date filter in YYYY-MM-DD format
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
      "merchant": {
        "name": "Store Name"
      },
      "category": {
        "name": "Shopping"
      },
      "account": {
        "displayName": "Account Name"
      },
      "notes": "",
      "needsReview": false
    }
  ],
  "count": 100,
  "totalCount": 500
}
```

**Use Cases:**
- Review recent transactions
- Find transactions by date range
- Search for specific merchants
- Filter by account or category

---

### `get_transaction`

**Purpose:** Get details of a single transaction by ID.

**Input:**
- `transaction_id` (string, required): The ID of the transaction to retrieve

**Output:**
```json
{
  "transaction": {
    "id": "transaction_id_here",
    "amount": -127.43,
    "date": "2025-01-15",
    "merchant": {
      "name": "Store Name"
    },
    "category": {
      "name": "Shopping"
    },
    "notes": "...",
    "tags": []
  },
  "success": true
}
```

**Use Cases:**
- View full transaction details
- Check transaction before updating
- Verify transaction information

---

### `update_transaction`

**Purpose:** Update a transaction's category, merchant, notes, or status.

**Input:**
- `transaction_id` (string, required): The ID of the transaction to update
- `category_id` (string, optional): New category ID to assign
- `merchant_name` (string, optional): New merchant name
- `notes` (string, optional): Notes to add (empty string clears notes)
- `needs_review` (boolean, optional): Mark as reviewed or needing review
- `hide_from_reports` (boolean, optional): Hide from reports and budgets

**Output:**
```json
{
  "transaction": {
    "id": "transaction_id",
    ...updated fields...
  },
  "success": true,
  "message": "Transaction updated successfully"
}
```

**Use Cases:**
- Recategorize transactions
- Add notes to transactions
- Mark transactions as reviewed
- Hide transactions from reports

---

### `mark_transactions_reviewed`

**Purpose:** Mark multiple transactions as reviewed or needing review.

**Input:**
- `transaction_ids` (array of strings, required): List of transaction IDs to update
- `needs_review` (boolean, optional): false = mark as reviewed (default), true = mark as needing review

**Output:**
```json
{
  "success": true,
  "affectedCount": 5,
  "message": "Marked 5 transactions as reviewed"
}
```

**Use Cases:**
- Bulk mark transactions as reviewed after checking
- Reset review status for re-examination
- Process multiple transactions efficiently

---

### `split_transaction`

**Purpose:** Split a transaction into multiple parts with different categories.

**Input:**
- `transaction_id` (string, required): The ID of the transaction to split
- `splits` (array of objects, required): Split details
  - `amount` (number, required): Split amount (negative for expenses)
  - `categoryId` (string, required): Category ID for the split
  - `merchantName` (string, optional): Merchant name
  - `notes` (string, optional): Notes for the split

**Output:**
```json
{
  "transaction": {
    "id": "transaction_id",
    "splitTransactions": [...]
  },
  "success": true,
  "message": "Transaction split into 2 parts"
}
```

**Use Cases:**
- Split purchases across multiple categories
- Allocate shared expenses
- Categorize mixed transactions accurately

---

## Resources

Resources provide read-only access to Monarch data.

### `monarch://accounts`

**Purpose:** Get all financial accounts as a JSON resource.

**URI Pattern:** `monarch://accounts`

**Returns:** JSON string containing all accounts with their IDs, names, types, balances, and metadata.

**Use Cases:**
- Read account information without using tools
- Access account data as context for LLMs

---

### `monarch://categories`

**Purpose:** Get all transaction categories as a JSON resource.

**URI Pattern:** `monarch://categories`

**Returns:** JSON string containing all categories with their IDs, names, and group information.

**Use Cases:**
- Read category information without using tools
- Access category data as context for LLMs

---

## Discovery

The MCP protocol provides automatic discovery of tools and resources. When an MCP client connects:

1. **Discovers all tools** - Gets names, descriptions, input schemas, and output schemas
2. **Discovers all resources** - Gets URI patterns and descriptions
3. **Validates inputs** - Ensures tool calls match the defined schemas
4. **Provides documentation** - Makes tool descriptions available to LLMs

## Example Usage Flow

1. **List accounts** to see available accounts:
   ```
   list_accounts() → Get account IDs and balances
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
- Set `needs_review=false` when done reviewing transactions
- Use `split_transaction` for purchases that span multiple categories
