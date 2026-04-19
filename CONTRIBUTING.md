# Contributing

## Project Structure

```
monarch-access/
├── pyproject.toml        # Package config, dependencies, entry points
├── Makefile              # Development commands
├── monarch/              # SDK package
│   ├── cli.py            # CLI entry point (monarch command)
│   ├── client.py         # MonarchClient - auth & API requests
│   ├── queries.py        # GraphQL queries
│   ├── accounts.py       # Account operations & formatting
│   ├── categories.py     # Category operations
│   ├── net_worth.py      # Net worth report logic & formatting
│   ├── transactions/     # Transaction operations
│   │   ├── list.py
│   │   ├── get.py
│   │   └── update.py
│   ├── providers/        # Provider abstraction for API/local switching
│   │   ├── base.py       # Protocol interfaces
│   │   ├── api/          # Real Monarch API provider
│   │   └── local/        # Local TinyDB provider (for testing)
│   └── mcp/              # MCP server (mcp-app framework)
│       ├── __init__.py
│       └── tools.py      # Plain async functions registered by mcp-app
├── tests/
│   ├── unit/sdk/         # SDK unit tests (use local provider)
│   │   ├── conftest.py
│   │   ├── fixtures/
│   │   └── test_*.py
│   ├── framework/        # mcp-app framework compliance tests
│   └── integration/      # Integration tests (require live credentials)
│       └── test_live_reads.py
```

## Development

After cloning, just run tests - venv is created automatically:

```bash
git clone https://github.com/krisrowe/monarch-access.git
cd monarch-access
make test
```

### Make Commands

| Command | Description |
|---------|-------------|
| `make test` | Run unit tests (auto-creates venv, no credentials needed) |
| `make integration-test` | Run integration tests (requires Monarch token) |
| `make install` | Install CLI + MCP server with pipx |
| `make clean` | Remove venv and build artifacts |
| `make uninstall` | Remove from pipx |

### Testing

**Unit tests** use a local provider with TinyDB - no network or auth required. Test data is auto-generated from `tests/fixtures/test_data_seed.json`.

**Integration tests** hit the live Monarch API and are skipped automatically if no token is configured.

```bash
make test              # Unit tests only (default)
make integration-test  # Live API tests (requires token)
```

## Architecture

This project follows a CLI/MCP/SDK layered architecture:
- **SDK layer** (`monarch/*.py`): Business logic, reusable — `client.py` (auth + GraphQL), operation modules (accounts, categories, transactions, recurring)
- **CLI layer** (`monarch/cli.py`): Thin Click wrapper
- **MCP layer** (`monarch/mcp/tools.py`): Plain async functions registered by [mcp-app](https://github.com/echomodel/mcp-app). `MonarchSDK` in `client.py` bridges mcp-app's `current_user` context to the SDK.

The `App` object in `monarch/__init__.py` wires everything: tools module, profile model, and entry points (`monarch-mcp`, `monarch-admin`).

## Monarch API Behaviors

Observations from working with the Monarch Money GraphQL API. These are not documented by Monarch — they're discovered through testing. Introspection queries are disabled for non-admin users, so mutation names and input shapes must be reverse-engineered.

### Two Recurring Query Types

Monarch has two separate GraphQL queries for recurring data:

| Query | Returns | Payment status? | Credit report liabilities? |
|-------|---------|-----------------|---------------------------|
| `Web_GetUpcomingRecurringTransactionItems` | Date-specific occurrences (many per stream) | Yes (`isPast`, `transactionId`, `date`, `category`, `account`) | No |
| `Common_GetRecurringStreams` | One entry per stream (catalog) | No | Yes (with `includeLiabilities: true`) |

Everything in the first query is a subset of the second. The second is a superset that also includes inactive/stale streams and credit report liabilities.

### Credit Report Liability Streams

Streams sourced from credit bureau data (not transaction detection). These have:
- `merchant: null` — no merchant association
- `amount: null` — no fixed payment amount (balance varies)
- `recurringType`: `credit_card`, `expense` (mortgages), or `credit_line`
- `creditReportLiabilityAccount` with: `status` (OPEN/CLOSED), `accountType` (MORTGAGE/REVOLVING/CREDIT_LINE/INSTALLMENT), `reportedDate`, and linked `account` with balance

Fields NOT available on credit report liabilities (all return 400): `lastStatementBalance`, `minimumPayment`, `lastPaymentAmount`, `dueDate`, `creditLimit`, `apr`, `monthlyPayment`.

The Monarch UI displays payment amounts and due dates for these streams, but the API doesn't expose how those are derived — likely from account statement data or transaction history.

### Merchant-Level Recurring

Recurring streams are controlled through the **merchant** resource:
- Each merchant has a recurring flag (on/off), amount, and frequency
- Toggling recurring on a merchant creates streams; toggling off removes ALL streams for that merchant
- One merchant can have multiple streams (different detection patterns from varying payee names)
- The `markStreamAsNotRecurring(streamId)` mutation removes a stream but affects all streams for its merchant

### Merchant Data Staleness

When a loan transfers between servicers (e.g., from one mortgage company to another), Monarch's merchant may retain the old loan's amount and recurring settings. The new servicer creates a new merchant with its own detection. The old merchant's data becomes stale but is never automatically cleaned up.

### Duplicate Streams

Monarch creates separate streams when the same payee's transaction description varies (e.g., different abbreviations, location suffixes, or "Memorial" vs regular entries). These are the same real-world obligation but appear as 2-3 separate streams.

### `last_paid_date` Null Behavior

In the collapsed stream output, `last_paid_date: null` means no transaction was matched to any occurrence in the trailing 12-month window. This could mean:
- The stream is genuinely stale (no payments ever or account closed)
- The payment comes from an account not linked to Monarch
- The merchant name changed and payments now post under a different merchant
- The account credential is disconnected and transactions stopped syncing

The null is ambiguous — consumers should investigate rather than assume "never paid."

### Third Recurring Query: Aggregated Items

`Common_GetAggregatedRecurringItems` is what the Monarch UI actually uses for its Upcoming/Complete view. It returns BOTH merchant-based AND credit report liability items in one response, grouped by status. Key fields not available in the other queries:

- `isLate` — whether the item is past due
- `isCompleted` — whether payment is confirmed
- `liabilityStatement.minimumPaymentAmount` — the minimum payment due (this is where the UI gets payment amounts for credit cards and mortgages)
- `liabilityStatement.paymentsInformation.status` — paid/unpaid/partially_paid
- `liabilityStatement.paymentsInformation.remainingBalance` — balance after payments
- `liabilityStatement.paymentsInformation.transactions[]` — actual payments applied

This query is captured in `queries.py` as `AGGREGATED_RECURRING_ITEMS_QUERY` but not yet wired to SDK/MCP/CLI.

### Discovered Mutations

Schema introspection is disabled. All mutations were reverse-engineered from the Monarch web app via Chrome DevTools.

**Recurring stream removal:**
- `markStreamAsNotRecurring(streamId: ID!)` — permanently removes stream. Affects all streams for the merchant. Request only `success` — requesting `errors` sub-fields causes HTTP 400. Implemented in SDK/MCP/CLI.

**Merchant update:**
- `updateMerchant(input: UpdateMerchantInput!)` — update merchant name and recurring settings. Input shape:
  ```json
  {
    "input": {
      "merchantId": "...",
      "name": "...",
      "recurrence": {
        "isRecurring": true,
        "frequency": "monthly",
        "baseDate": "YYYY-MM-DD",
        "amount": -123.45,
        "isActive": true/false
      }
    }
  }
  ```
  Setting `isActive: false` deactivates the stream (reversible). Setting `isRecurring: false` removes it. All `recurrence` fields must be sent every time — partial updates not supported. Implemented in SDK/MCP/CLI via `update_recurring`.

**Merchant logo (3-step process):**
1. `getCloudinaryUploadInfo(input: {entityType: "merchant"})` — returns signed upload params (timestamp, folder, signature, api_key, upload_preset)
2. POST to `https://api.cloudinary.com/v1_1/monarch-money/image/upload/` — multipart form with image file + signed params
3. `setMerchantLogo(input: {merchantId, cloudinaryPublicId})` — associates uploaded image with merchant

The `cloudinaryPublicId` from an existing merchant can be reused on other merchants to share logos. Captured in `queries.py` but not yet wired to SDK/MCP/CLI.

**Merchant queries:**
- `merchants(search: String)` — search merchants by name. Returns id, name, logoUrl, transactionsCount, canBeDeleted, createdAt, recurringTransactionStream.
- `merchant(id: ID!)` — get single merchant by ID. Returns additional fields: transactionCount, ruleCount, hasActiveRecurringStreams.

Both captured in `queries.py` but not yet wired to SDK/MCP/CLI.

### Multi-Account Merchant Splitting

When one merchant (e.g., an insurer) handles multiple policies from different accounts, transactions can be reassigned to new merchants:

1. Use `update_transaction(id, merchant_name="New Name")` — Monarch auto-creates the merchant if it doesn't exist
2. Set up recurring on the new merchant via `updateMerchant`
3. Copy logo via `setMerchantLogo` with the original's `cloudinaryPublicId`
4. Deactivate the original merchant's recurring

This workflow is proven and uses existing implemented tools for steps 1-2, plus captured-but-not-yet-implemented mutations for steps 3-4.

### Product Model (Monarch Recurring)

Monarch's Recurring feature tracks bills and subscriptions via two input modes: **auto-detection** (scans transaction history for merchant/frequency patterns) and **manual addition** (user searches a merchant in the UI and marks it recurring). Auto-detected candidates go through a user-review flow before appearing on the confirmed list.

Product constraints that leak into the API surface:

- **Transaction-seeded.** A recurring obligation cannot be created from thin air; the merchant must already have transaction history. Workaround: create a manual transaction first, then confirm it as recurring.
- **Persistent.** Items do not auto-remove. They persist until a user marks them "not recurring" (or until the merchant is updated to `isRecurring: false`).
- **Active/Canceled.** Canceled items remain visible in the API but are separated from active ones in the UI.

Source: [Monarch Help — Tracking Recurring Expenses and Bills](https://help.monarch.com/hc/en-us/articles/4890751141908-Tracking-Recurring-Expenses-and-Bills).

### Payment Matching Rules

Monarch automatically marks items paid when a transaction matching the bill amount posts in the mapped account before the due date. The UI surfaces three states — paid, unpaid, partially paid — driven by type-specific thresholds:

- **Loans**: transaction amount ≥ bill amount → paid; less → partially paid.
- **Credit cards**: ≥ bill amount → paid; less than bill but ≥ minimum payment → partially paid.
- **Manual override**: users can mark items paid via the UI three-dot menu. How this surfaces in the API (whether it sets `transactionId` or uses a separate field) is unverified.
- **Notifications**: 3 days before the due date.
- **Past-due unpaid items** are hidden from the calendar view but remain in the list view under Active merchants.

### Bill Sync (Spinwheel)

Monarch's Bill Sync feature pulls due dates and statement balances from credit bureau data via Spinwheel. This is what populates the liability-statement fields surfaced by `Common_GetAggregatedRecurringItems` (`liabilityStatement.minimumPaymentAmount`, `liabilityStatement.paymentsInformation.*`). Bill Sync covers **only** credit-report-visible liabilities — credit cards, mortgages, loans. It does not cover utilities, subscriptions, or any detection-based recurring. The `GetBills` query appears to be the underlying read path; not yet implemented here.

Source: [Monarch Help — Getting Started with Bill Sync](https://help.monarch.com/hc/en-us/articles/29446697869076-Getting-Started-with-Bill-Sync).

### Field Semantics

Confirmed against live API data:

- **`isPast`** — relative to today's date, not to the query's date range. Dynamic; the value changes as time passes. Items with `date` on or before today return `true`; items with `date` after today return `false`.
- **`transactionId`** — null means the item is unpaid (no transaction matched). Non-null means the item has been matched to that specific transaction. Consumers can treat non-null as "paid" (with the caveat that the behavior of manual mark-as-paid in the UI is unverified).
- **`stream.id`** — stable across time and across query ranges. The same stream ID is returned for the same obligation whether you query one month or twelve. Safe to cache and use as a stable identifier; deduplicating by `stream.id` across a multi-month range collapses projected occurrences back to one entry per obligation.
- **`isApproximate`** — flag indicating the stream's `amount` is variable (e.g., credit card minimum payments). Treat the stream `amount` as an estimate when this is true.
- **Stream `amount` vs item `amount`** — the stream's `amount` is Monarch's historical average or initial estimate at detection time. The item's `amount` is the actual or expected amount for that specific occurrence. These diverge significantly in practice — by orders of magnitude in some streams, and occasionally with opposite signs. **Do not sum stream amounts for budgeting or "total monthly obligations" calculations.**
- **Frequency values**: `weekly`, `biweekly`, `monthly`, `quarterly`, `yearly`.
- **Empty fields**: `category`, `category_id`, `account`, `account_id` can come back as empty strings on some items. Consuming code should handle empty, not just null.

### Category Behavior

- **Categories are user-customizable.** Users can create subcategories under Monarch's system-defined parent category groups. The recurring list reflects user-created categories, not just system defaults — any assumption that categories are a fixed enum is wrong.
- **Stream category is inherited**, not independent. The stream reports the category of the seeding transaction. Recategorizing the transaction updates the stream's category; there is no separate "stream category" field to set.
- **Credit card payments use the `Credit Card Payment` category**, not a generic `Transfer`. Other obligation types have their own specific categories (`Mortgage`, `Loan Repayment`, `Dependent Support`, etc.). Earlier assumptions that CC payments were indistinguishable from transfers are wrong.

### Stale and Positive-Amount Streams

Two classes of streams consumers should filter or flag explicitly:

- **Stale streams.** Because streams don't auto-remove, some appear with `last_paid_date` many months behind their `due_date`. The canonical detection is a `last_paid_date` gap relative to the stream's `frequency` — e.g., a monthly stream with no payment in 3+ months is almost certainly stale. Consumers producing a current-obligations view should either hide stale streams or flag them.
- **Positive-amount streams.** Monarch's recurring list includes incoming money — payrolls, interest paid, transfers in, loan credits. These have `amount > 0`. Consumers filtering for "obligations" (money going out) should filter on `amount < 0` or maintain a category/merchant blacklist.

### Date Range Behavior

`Web_GetUpcomingRecurringTransactionItems` requires a date range and returns one item per projected occurrence within that range. For a weekly stream queried over 12 months, that yields ~52 items before deduplication by `stream.id`. There is no "list all streams" endpoint on the implemented query; either use the date-range + collapse pattern (trailing 12 months is a reasonable default for deriving a `last_paid_date`), or switch to `Common_GetRecurringStreams` for a raw stream catalog (not yet implemented). The `$filters: RecurringTransactionFilter` parameter exists but its accepted fields are not publicly documented — schema would need DevTools capture to reverse-engineer.

### Known Queries Not Yet Wired

Captured from community research; not yet implemented in this repo:

- `Web_GetAllRecurringTransactionItems` — filter-enabled variant of the upcoming-items query
- `GetBills` — Bill Sync due dates and statement balances for credit-report liabilities
- `RecurringMerchantSearch` — status check for whether a merchant is marked recurring
- `Web_ReviewStream` — mutation to review/update a recurring stream (distinct from `updateMerchant`)

No `CreateRecurringStream` mutation has been found in any community library. Such a mutation almost certainly exists internally and could be captured from the Monarch web app's DevTools network panel.

### Community Libraries

Ecosystem references for cross-checking reverse-engineered API details:

- [`hammem/monarchmoney`](https://github.com/hammem/monarchmoney) (Python) — includes `get_recurring_transactions()` (read-only)
- [`keithah/monarchmoney-enhanced`](https://github.com/keithah/monarchmoney-enhanced) (Python) — documents additional query names in its `GRAPHQL.md`
- [`keithah/monarchmoney-ts`](https://github.com/keithah/monarchmoney-ts) (TypeScript) — no recurring support
