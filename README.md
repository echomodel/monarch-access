# Monarch Access

Lightweight CLI and Python SDK for accessing [Monarch Money](https://www.monarch.com/) financial data.

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
pipx install git+https://github.com/krisrowe/monarch-access.git
```

This installs three commands:
- **`monarch`** - The CLI tool for direct command-line use
- **`monarch-mcp`** - The MCP server for AI assistant integration (see [MCP Server](#mcp-server-for-ai-assistants))
- **`monarch-admin`** - User management for MCP server (local and cloud)

## Requirements

- Python 3.10+
- A Monarch Money account

## Authentication

Monarch doesn't have a public API, so you need to grab your session token from the browser:

1. Go to https://app.monarch.com/ and log in
2. Open DevTools (F12) → Console tab
3. Paste and run:
   ```javascript
   JSON.parse(JSON.parse(localStorage.getItem("persist:root")).user).token
   ```
4. Copy the token string
5. Register it:
   ```bash
   monarch-admin connect local
   monarch-admin users add local --token $MONARCH_SESSION_TOKEN
   ```

The token is stored in the local user store and used by both the CLI and MCP server. Tokens typically last several months — rotate yours with:

```bash
monarch-admin users update-profile local token $MONARCH_SESSION_TOKEN
```

## CLI Usage

All commands default to text format with ASCII tables. Use `--format json` or `--format csv` for machine-readable output.

### List Transactions

```bash
# Transactions since a date
monarch transactions list --start 2025-12-01

# Date range (both inclusive)
monarch transactions list --start 2025-01-01 --end 2025-12-31

# Filter by account (supports wildcards)
monarch transactions list --start 2025-01-01 --account "MyBank*"

# Filter by category (comma-separated)
monarch transactions list --start 2025-01-01 --category "Shopping,Groceries"

# Filter by merchant (supports wildcards)
monarch transactions list --start 2025-01-01 --merchant "*amazon*"

# Filter by tag (comma-separated or repeated; combine with other filters)
monarch transactions list --tag "agent-reviewed"
monarch transactions list --tag "agent-reviewed" --account "MyBank*"

# Manage tags (non-destructive add/remove; tag created on first use)
monarch transactions tags
monarch transactions tag-add <transaction_id> "agent-reviewed"
monarch transactions tag-remove <transaction_id> "agent-reviewed"

# Output as JSON or CSV
monarch transactions list --start 2025-01-01 --format json
monarch transactions list --start 2025-01-01 --format csv

# Limit results (default 1000)
monarch transactions list --start 2025-01-01 --limit 50
```

JSON output example:

```
$ monarch transactions list --start 2025-01-01 --limit 1 --format json
{
  "transactions": [
    {
      "id": "311447260750935400",
      "amount": -127.43,
      "pending": false,
      "date": "2025-01-15",
      "hideFromReports": false,
      "needsReview": false,
      "plaidName": "AMAZON #7491",
      "notes": "",
      "isRecurring": false,
      "account": {
        "id": "acc_004",
        "displayName": "Rewards Card"
      },
      "merchant": {
        "id": "merch_amazon",
        "name": "Amazon"
      },
      "category": {
        "id": "cat_005",
        "name": "Shopping"
      },
      "tags": []
    }
  ],
  "count": 1,
  "total": 147
}
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

### Manage Accounts

```bash
# Close an account — keeps its balance history in net worth, zeros it forward
monarch account close <account_id>
monarch account close <account_id> --date 2025-06-30

# Reopen a closed account
monarch account update <account_id> --reopen

# Rename
monarch account update <account_id> --name "New Name"

# Exclude from / include in net worth (retroactive — removes balance from history)
monarch account update <account_id> --exclude-net-worth
monarch account update <account_id> --include-net-worth

# Hide / unhide from the accounts list
monarch account update <account_id> --hide
monarch account update <account_id> --unhide
```

**Close vs. exclude.** *Closing* (`account close`) keeps the account's
historical balance snapshots in net worth and reads $0 from the close date
forward — the right way to retire a manual placeholder once a real account
links, so net worth neither double-counts nor drops retroactively. *Excluding*
(`--exclude-net-worth`) removes the balance from net worth across all of
history. Closing is reversible with `--reopen`.

### Balance History

```bash
# Download an account's daily balance history as CSV (Date,Balance)
monarch balances download <account_id>
monarch balances download <account_id> -o history.csv

# Replace an account's balance history from a CSV file
monarch balances upload <account_id> history.csv

# Back up the current history before replacing, and skip the prompt
monarch balances upload <account_id> history.csv -o backup.csv --yes
```

**Upload replaces the entire balance history** (there is no append mode) and
sets the account's current balance to the final row. Balance history is
independent of transactions — uploading creates no transactions and doesn't
affect income/expense reports. Useful for correcting stale balances on accounts
that stopped syncing, importing history for manual accounts, or migrating a
balance curve between accounts.

Because the replace is destructive, uploads are guarded by a **read-before-write
interlock**:

- The **CLI** reads the current history first, shows what will be replaced,
  optionally writes it to a backup CSV (`-o`), and prompts for confirmation
  (`--yes` to skip).
- The **SDK and MCP tool** require an `expected_token` — a digest number of the
  current history returned by `download_balance_history`. The upload re-reads
  the live history, recomputes the token, and refuses (changing nothing) unless
  it matches. This guarantees the prior history was read (so the change is
  reversible) and that nothing changed underneath. On success, the replaced
  history is returned under `previous_snapshots` for rollback.

### Net Worth Report

```bash
monarch net-worth
monarch net-worth --format json
monarch net-worth --format csv
```

Shows assets and liabilities grouped by category with totals.

### Investment Holdings

```bash
# All holdings across investment accounts
monarch holdings

# Holdings in a single account
monarch holdings --account <account_id>

# Holdings as of a past date (historical snapshot)
monarch holdings --date 2025-01-15

monarch holdings --format json
monarch holdings --format csv
```

Returns security-level positions — ticker, share quantity, closing price,
current value, cost basis, and per-acquisition tax lots. `cost_basis` may be
null for synced positions where the data provider did not supply basis.

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

## MCP Server for AI Assistants

The `monarch-mcp` command exposes Monarch data via the [Model Context Protocol](https://modelcontextprotocol.io/), enabling AI assistants like Claude and Gemini to access your financial data.

### Setup

Register a local MCP user with your Monarch token:

```bash
monarch-admin connect local
monarch-admin users add local --token $MONARCH_SESSION_TOKEN
```

### Register with Claude Code

```bash
claude mcp add --scope user monarch -- monarch-mcp stdio --user local
```

### Register with Gemini CLI

```bash
gemini mcp add monarch -- monarch-mcp stdio --user local
```

### Available Tools

| Tool | Description |
|------|-------------|
| `list_accounts` | Get all accounts with balances |
| `update_account` | Rename, exclude from net worth, or hide an account |
| `close_account` | Close an account (keeps balance history in net worth) |
| `get_holdings` | Get investment holdings (shares, cost basis, tax lots) |
| `download_balance_history` | Download an account's daily balance snapshots |
| `upload_balance_history` | Replace an account's balance history |
| `list_categories` | Get all transaction categories |
| `list_transactions` | Query transactions with filters |
| `get_transaction` | Get a single transaction |
| `update_transaction` | Update category, notes, etc. |
| `mark_transactions_reviewed` | Bulk mark as reviewed |
| `split_transaction` | Split across categories |
| `create_transactions` | Create one or more manual transactions (partial success reported) |
| `delete_transactions` | Delete one or more transactions (partial success reported) |
| `list_recurring` | List recurring obligations |
| `update_recurring` | Update recurring stream settings |
| `list_tags` | List all transaction tags (id, name, color) |
| `add_transaction_tag` | Add a tag to a transaction (created if missing); preserves existing tags |
| `remove_transaction_tag` | Remove a tag from a transaction, preserving its other tags |

`list_transactions` accepts a `tags` filter (list of tag names) alongside account, category, date, and expense/income filters — so a request like *"show me every agent-reviewed transaction in a given account"* is a single call combining `tags=["agent-reviewed"]` with an account filter. Tag add/remove are non-destructive: adding a tag never drops the transaction's existing tags, and adding the same tag twice is a no-op.

For detailed documentation, see **[MCP-SERVER.md](./MCP-SERVER.md)**.

## Cloud Deployment (Optional)

Deploying monarch-access as an HTTP MCP server means your Monarch session token stays on the server and is never exposed to clients — each client authenticates with a JWT issued by `monarch-admin`.

### Runtime contract

The MCP server reads these environment variables at startup. Any host must provide them:

| Variable | Required | Purpose |
|----------|----------|---------|
| `SIGNING_KEY` | yes | JWT signing secret. Generate once with `python3 -c 'import secrets; print(secrets.token_urlsafe(32))'` and supply via your host's secret mechanism. |
| `APP_USERS_PATH` | yes for durable deploys | Directory for per-user profiles. Must be a persistent path — mount a durable volume. |
| `JWT_AUD` | no | Expected JWT audience claim. Leave unset unless you're running multiple apps with a shared signing key. |
| `TOKEN_DURATION_SECONDS` | no | Lifetime of newly issued JWTs. Defaults to ~10 years. |

The server serves the MCP endpoint at `/`, a liveness probe at `/health`, and admin REST endpoints under `/admin/*`.

### Connect the admin CLI

Once the service is running, point the admin CLI at it with the same `SIGNING_KEY` the server is using:

```bash
monarch-admin connect https://your-service-url --signing-key "$SIGNING_KEY"
```

`connect` persists the URL and signing key to `~/.config/monarch/setup.json`, so subsequent `monarch-admin` commands don't need the flags repeated.

### Verify the deployment

```bash
monarch-admin health
```

### Register a user

```bash
monarch-admin users add user@example.com --token "$MONARCH_SESSION_TOKEN"
```

See [Authentication](#authentication) for how to obtain `$MONARCH_SESSION_TOKEN`. To rotate a user's token in place (keeps their JWT valid and their profile intact):

```bash
monarch-admin users update-profile user@example.com token "$NEW_TOKEN"
```

To revoke a user entirely (invalidates their JWT), use `monarch-admin users revoke user@example.com`.

### Issue a JWT for an MCP client

```bash
monarch-admin tokens create user@example.com
```

Copy the returned token and register the remote server with your MCP client. Both Claude Code and Gemini CLI expand `${VAR}` in MCP config, so keep the token in an env var rather than pasting it into config files:

```bash
export MONARCH_JWT="<token from tokens create>"

# Claude Code
claude mcp add --scope user --transport http monarch https://your-service-url/ \
  --header "Authorization: Bearer \${MONARCH_JWT}"

# Gemini CLI
gemini mcp add --transport http monarch https://your-service-url/ \
  --header "Authorization: Bearer \${MONARCH_JWT}"
```

## Development

See **[CONTRIBUTING.md](./CONTRIBUTING.md)** for development setup, testing, and architecture.

## For agents

If you are a coding agent operating this repo with plugin support, the
[author-mcp-app](https://github.com/echomodel/claude-coding) and
[mcp-app-admin](https://github.com/echomodel/claude-coding) skills
provide step-by-step workflows for authoring and operating apps on the
mcp-app framework. They are optional — this README and
[CONTRIBUTING.md](./CONTRIBUTING.md) are self-sufficient.

## License

MIT
