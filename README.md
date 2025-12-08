# Monarch Access

Lightweight CLI and Python SDK for accessing [Monarch Money](https://www.monarchmoney.com/) financial data.

```
$ monarch accounts
ACCOUNTS (5)
+--------------------------------+--------------------+----------------+
| Account                        | Institution        |        Balance |
+--------------------------------+--------------------+----------------+
| [Checking]                     |                    |      $8,434.56 |
|   Primary Checking             | First National     |      $5,234.56 |
|   Joint Checking               | First National     |      $3,200.00 |
| [Credit Card]                  |                    |     -$3,148.06 |
|   Rewards Card                 | Premium Credit     |     -$2,345.67 |
|   Store Card                   | Target             |       -$802.39 |
| [Savings]                      |                    |     $12,500.00 |
|   Emergency Fund               | First National     |     $12,500.00 |
+--------------------------------+--------------------+----------------+
```

```
$ monarch transactions list --start 2025-01-01 --limit 5
TRANSACTIONS (5)
+------------+--------------------------+----------------------+--------------+
| Date       | Merchant                 | Category             |       Amount |
+------------+--------------------------+----------------------+--------------+
| 2025-01-15 | Amazon                   | Shopping             |     -$127.43 |
| 2025-01-14 | Whole Foods              | Groceries            |      -$89.23 |
| 2025-01-13 | Shell                    | Gas                  |      -$45.00 |
| 2025-01-12 | Netflix                  | Entertainment        |      -$15.99 |
| 2025-01-10 | Employer Payroll         | Salary               |    $3,500.00 |
+------------+--------------------------+----------------------+--------------+

Total: $3,222.35
```

## Installation

```bash
pip install git+https://github.com/krisrowe/monarch-access.git
```

Or clone and install locally:

```bash
git clone https://github.com/krisrowe/monarch-access.git
cd monarch-access
pip install .
```

This installs the `monarch` command globally.

## Requirements

- Python 3.10+
- A Monarch Money account

## Authentication

Monarch Money doesn't have a public API, so you need to grab your session token from the browser:

1. Go to https://app.monarchmoney.com/ and log in
2. Open DevTools (F12) → Console tab
3. Paste and run:
   ```javascript
   JSON.parse(JSON.parse(localStorage.getItem("persist:root")).user).token
   ```
4. Copy the token string
5. Save it:
   ```bash
   monarch auth "YOUR_TOKEN_HERE"
   ```

The token is saved to `~/.config/monarch/token` and typically lasts several months. You'll need to repeat this when it expires.

## CLI Usage

All commands default to text format with ASCII tables. Use `--format json` or `--format csv` for machine-readable output.

### List Transactions

```bash
# Transactions since a date
monarch transactions list --start 2025-12-01

# Date range (both inclusive)
monarch transactions list --start 2025-01-01 --end 2025-12-31

# Filter by account (supports wildcards)
monarch transactions list --start 2025-01-01 --account "Chase*"

# Filter by category (comma-separated)
monarch transactions list --start 2025-01-01 --category "Shopping,Groceries"

# Filter by merchant (supports wildcards)
monarch transactions list --start 2025-01-01 --merchant "*amazon*"

# Output as JSON or CSV
monarch transactions list --start 2025-01-01 --format json
monarch transactions list --start 2025-01-01 --format csv

# Limit results (default 1000)
monarch transactions list --start 2025-01-01 --limit 50
```

### Get a Single Transaction

```bash
monarch transactions get TRANSACTION_ID
monarch transactions get TRANSACTION_ID --format json
```

### Update a Transaction

```bash
# Update notes
monarch transactions update TRANSACTION_ID --notes "New note"

# Update category (by name)
monarch transactions update TRANSACTION_ID --category "Groceries"

# Update merchant
monarch transactions update TRANSACTION_ID --merchant "Amazon"

# Clear notes (use empty string)
monarch transactions update TRANSACTION_ID --notes ""
```

### List Accounts

```bash
monarch accounts
monarch accounts --format json
monarch accounts --format csv
```

### Net Worth Report

```bash
monarch net-worth
monarch net-worth --format json
monarch net-worth --format csv
```

Shows assets and liabilities grouped by category with totals.

## Python SDK Usage

```python
import asyncio
from monarch.client import MonarchClient
from monarch import accounts, categories
from monarch.transactions import list as txn_list, get as txn_get, update as txn_update

async def main():
    client = MonarchClient()

    # Get all accounts
    accts = await accounts.get_accounts(client)

    # Get transactions
    data = await txn_list.get_transactions(
        client,
        limit=100,
        start_date="2025-01-01",
        end_date="2025-12-31",
    )
    txns = data["results"]

    # Get a single transaction
    txn = await txn_get.get_transaction(client, "some-transaction-id")

    # Update a transaction
    updated = await txn_update.update_transaction(
        client,
        transaction_id="some-transaction-id",
        notes="Updated via SDK",
    )

    # Get categories
    cats = await categories.get_categories(client)

asyncio.run(main())
```

## Future Enhancements

- **User configuration** (`~/.config/monarch/config.yaml`): Store user preferences like default columns for transaction lists, default output format, etc.
  - `monarch config set transactions.columns "date,merchant,amount,category"`
  - `monarch config get transactions.columns`
- **MCP server**: Expose Monarch data to AI assistants via Model Context Protocol

## License

MIT
