# Monarch Money Recurring Feature: Analysis & API Research

## Goal

Evaluate Monarch Money's Recurring feature as a data source for tracking monthly
financial obligations (bills, subscriptions, loan payments, credit card payments)
via API, to power MCP server tools that list and monitor commitments.

---

## How the Recurring Feature Works

**Source**: [Monarch Help — Tracking Recurring Expenses and Bills](https://help.monarch.com/hc/en-us/articles/4890751141908-Tracking-Recurring-Expenses-and-Bills)

Monarch's **Recurring** section tracks bills and subscriptions. It has two modes:

- **Auto-detection**: Scans transaction history for recurring patterns (same merchant,
  regular frequency). New detections are presented for user review — they don't appear
  on the confirmed list without approval.
- **Manual addition**: Users can search for a merchant and add it as recurring through
  the Monarch web/mobile UI. However, you **cannot add an arbitrary obligation
  independent of a transaction** — the merchant must have transaction history.

Once confirmed, a recurring item appears in a calendar/list view:
- **Upcoming** items (not yet paid this period)
- **Completed** items (matched to a transaction)
- Color coding: green = paid as expected, yellow = different amount

Items do **NOT auto-remove**. They persist until the user explicitly marks them as
"not recurring." Monarch also supports an **Active/Canceled** status — canceled items
remain visible but are separated.

### Payment Matching (Confirmed via Help Docs)

- A bill is automatically marked as **Paid** when a transaction for the bill amount
  is detected in the mapped account before the bill's due date.
- Bills can be **Paid** or **Partially Paid**:
  - **Loans**: Payment >= bill amount = paid; less = partially paid.
  - **Credit cards**: Payment >= bill amount = paid; less than bill but more than
    minimum = partially paid.
- Users can **manually mark as paid** via the UI three-dot menu.
- Notifications go out **3 days before** a due date.
- Past due items that were not paid are **hidden from the calendar** (but remain
  in the list view under Active merchants).

### Bill Sync (Liability Accounts)

Monarch has a **Bill Sync** feature via Spinwheel (credit report connection) that pulls
due dates and balances for credit cards and loans. This is separate from the recurring
feature and only covers credit-report-visible liabilities, not utilities or subscriptions.

---

## Data Model

### Streams vs. Items

Monarch uses two levels:

- **Stream** (`recurringTransactionStream`): Monarch's internal term for a recurring
  obligation — one per commitment. This is the stable entity that represents
  "I pay Netflix monthly." Not related to data streaming or financial streaming.
- **Item** (`recurringTransactionItem`): A projected occurrence of a stream for a
  specific date. The API returns items within a date range, and each item may or may
  not be matched to an actual transaction.

The API does not expose a direct "list all streams" endpoint that we've been able to
use. Instead, you query for items within a date range, and each item references its
parent stream. Our implementation queries a trailing 12 months and deduplicates by
stream ID to produce the stable obligations list.

### Stream Fields (confirmed from API response shape)

| Field | Description |
|-------|-------------|
| `id` | Unique stream identifier |
| `frequency` | How often it recurs (monthly, weekly, etc.) |
| `amount` | Expected payment amount |
| `isApproximate` | Whether the amount varies |
| `merchant` | Associated merchant (id, name, logoUrl) |

### Item Fields (confirmed from API response shape)

| Field | Description | Verified? |
|-------|-------------|-----------|
| `date` | Expected payment date for this occurrence | Field exists in query; exact semantics **untested** |
| `isPast` | Presumably whether the date has passed | **UNTESTED** — we assume this means "due date passed relative to today" but have not confirmed |
| `transactionId` | Presumably linked actual transaction ID (null if unpaid) | **UNTESTED** — assumed to be null when no payment matched |
| `amount` | Actual or expected amount for this occurrence | Field exists in query |
| `amountDiff` | Presumably difference from expected amount | **UNTESTED** |
| `category` | Category (id, name) — inherited from the seeding transaction | Confirmed: no separate stream category exists |
| `account` | Payment account (id, displayName, logoUrl) | Field exists in query |

---

## What We Know vs. What We're Assuming

### Confirmed (from documentation or source code inspection)

- Recurring items persist until explicitly removed by user
- Auto-detected items require user review/approval before appearing on confirmed list
- Items are transaction-seeded — cannot create from thin air without a transaction
- Each merchant can only have one recurring stream
- Categories are system-defined, not customizable
- CC payments land as "Transfer" category (same as any inter-account movement)
- The category on a recurring stream is inherited from the transaction — no separate
  stream category exists
- The `monarchmoney` Python library has `get_recurring_transactions()` (read-only)
- No create/update/delete mutations for recurring items found in any community library
- The GraphQL query accepts `$filters: RecurringTransactionFilter` (schema unknown)
- Tags exist on transactions; unknown if they exist on recurring streams

### Assumptions (NOT verified against live API)

- **`isPast` meaning**: We assume this means "the due date has passed relative to
  today's date." It could mean something else (e.g., relative to the query date
  range, or a fixed property set at item creation).

- **`transactionId` meaning**: We assume null means "no payment matched" and non-null
  means "paid." Could have other semantics (e.g., partially paid states).

- **Date range behavior**: We assume querying Jan 1 – Dec 31 returns one item per
  stream per month. We do NOT know:
  - What happens with mid-month ranges (e.g., Jan 15 – Feb 15)
  - Whether items outside the range but related are included
  - How the range interacts with `isPast`
  - Whether the API returns items for months where no payment was expected

- **`last_paid_date` derivation**: Our code derives this by finding the most recent
  item with a non-null `transactionId` across the queried range. This assumes
  `transactionId` reliably indicates payment. Untested.

- **Stream deduplication**: We assume that querying multiple months returns the same
  `stream.id` for the same obligation across months. Untested.

- **`amountDiff` behavior**: We include this field but don't know how Monarch
  calculates it or when it's populated.

---

## Key Constraint: Transaction-Seeded

You **cannot create a recurring item from scratch** independent of a transaction.
Recurring items emerge from transaction patterns — either auto-detected or triggered
by manual merchant search that matches existing transactions. There is no freeform
"add an arbitrary obligation" capability.

**Workaround**: Create a manual transaction in Monarch for the merchant, then confirm
it as recurring. Once it's on the list, it persists regardless of future transaction
activity.

---

## Category Limitations

Monarch categories are **system-defined and not customizable**. You cannot create
custom categories like "Monthly Obligations" or "Critical Bills."

This creates a specific problem for credit card payments: they're categorized as
**"Transfer"** — the same category used for moving money between accounts, paying
yourself back, etc. There's no way to distinguish "credit card payment (obligation)"
from "savings transfer (not an obligation)" by category alone.

The category on a recurring stream is **inherited from the seeding transaction**.
There is no independent "stream category" — it's the same value. Recategorizing the
source transaction would change the stream's category.

Monarch does support **tags** (user-created, freeform) on transactions. Whether tags
are available on recurring streams is unconfirmed and would need to be verified in the
web app.

### Available Filter/Grouping Dimensions

Data available on each recurring item that could be used for client-side filtering:

| Field | Example Values | Useful For |
|-------|---------------|------------|
| Category | Mortgage, Entertainment, Transfer | Grouping by type (imprecise for CC payments) |
| Account | Checking, Credit Card, Loan | Grouping by payment source |
| Frequency | monthly, weekly, biweekly | Filtering to just monthly |
| Merchant | Netflix, Chase, MOHELA | Matching specific obligations |
| Amount | -15.49, -2500.00 | Sorting by size |
| isApproximate | true/false | Fixed vs. variable amounts |

The API accepts a `$filters: RecurringTransactionFilter` parameter, but the schema
for this filter type is **undocumented**. The fields it accepts would need to be
reverse-engineered from the Monarch web app's network traffic.

We do **not** currently expose any filter parameters on the CLI or MCP tool.

---

## Available GraphQL API Operations

### Queries (Read)

| Operation Name | Purpose | Implemented | Source |
|---------------|---------|-------------|--------|
| `Web_GetUpcomingRecurringTransactionItems` | Items for a date range with stream, merchant, account, category | **Yes** | monarchmoney Python lib |
| `Common_GetRecurringStreams` | Raw stream definitions (no date range) | No | monarchmoney-enhanced GRAPHQL.md |
| `Common_GetAggregatedRecurringItems` | Aggregated view with status grouping | No | monarchmoney-enhanced GRAPHQL.md |
| `Web_GetAllRecurringTransactionItems` | All items with filtering | No | monarchmoney-enhanced GRAPHQL.md |
| `GetBills` | Bills and payments with due dates | No | monarchmoney-enhanced GRAPHQL.md |
| `RecurringMerchantSearch` | Check recurring merchant search status | No | monarchmoney-enhanced GRAPHQL.md |

### Mutations (Write)

| Operation Name | Purpose | Implemented | Source |
|---------------|---------|-------------|--------|
| `Web_ReviewStream` | Review/update a recurring stream | No | monarchmoney-enhanced GRAPHQL.md |
| `Common_MarkAsNotRecurring` | Mark merchant as not recurring | No | monarchmoney-enhanced GRAPHQL.md |

**No create or delete mutations** have been found in any community library. A create
mutation almost certainly exists internally — it could be captured from the Monarch web
app's network traffic (DevTools → Network → filter `graphql` → add a recurring merchant
and observe the request).

### Implemented Query

```graphql
query Web_GetUpcomingRecurringTransactionItems(
  $startDate: Date!
  $endDate: Date!
  $filters: RecurringTransactionFilter
) {
  recurringTransactionItems(
    startDate: $startDate
    endDate: $endDate
    filters: $filters
  ) {
    stream {
      id
      frequency
      amount
      isApproximate
      merchant { id name logoUrl }
    }
    date
    isPast
    transactionId
    amount
    amountDiff
    category { id name }
    account { id displayName logoUrl }
  }
}
```

### Community Libraries

| Library | Recurring Support |
|---------|-------------------|
| [hammem/monarchmoney](https://github.com/hammem/monarchmoney) (Python) | `get_recurring_transactions()` — read only |
| [keithah/monarchmoney-enhanced](https://github.com/keithah/monarchmoney-enhanced) (Python) | Documents additional query names in GRAPHQL.md |
| [keithah/monarchmoney-ts](https://github.com/keithah/monarchmoney-ts) (TypeScript) | No recurring support found |

---

## Our Implementation

### What We Built

The recurring feature is implemented across all layers of this project:

- **GraphQL query**: `RECURRING_TRANSACTION_ITEMS_QUERY` in `monarch/queries.py`
- **Provider layer**: `RecurringProvider` protocol + API and Local implementations
- **SDK module**: `monarch/recurring.py` — raw item fetching, stream collapsing, formatting
- **CLI**: `monarch recurring [--format text|json|csv]`
- **MCP tool**: `list_recurring` — returns deduplicated obligations list

### How It Works

1. Query Monarch API for a **trailing 12 months** of recurring transaction items
2. `collapse_to_streams()` deduplicates by stream ID → one entry per obligation
3. For each stream, tracks the most recent occurrence (due_date, is_past, transaction_id)
   and the most recent paid occurrence (last_paid_date)
4. Output sorted alphabetically by merchant

The date range is an API implementation detail, not a user-facing concern. The user
runs `monarch recurring` and gets their stable list of obligations.

### Collapsed Stream Output Fields

| Field | Description |
|-------|-------------|
| `stream_id` | Unique stream identifier |
| `merchant` | Merchant/payee name |
| `merchant_id` | Merchant ID |
| `amount` | Expected payment amount |
| `frequency` | Recurrence frequency |
| `is_approximate` | Whether amount varies |
| `category` | Monarch category name (inherited from transaction) |
| `category_id` | Category ID |
| `account` | Payment account name |
| `account_id` | Account ID |
| `is_past` | Monarch's raw `isPast` for the most recent occurrence (**meaning assumed, not verified**) |
| `due_date` | `date` from the most recent occurrence (YYYY-MM-DD) |
| `last_paid_date` | Date of most recent occurrence with non-null `transactionId` in trailing 12 months (null if none found) |
| `actual_amount` | `amount` from the most recent occurrence |
| `transaction_id` | `transactionId` from the most recent occurrence (null if no payment matched — **assumed meaning**) |

### Payment Status

The MCP tool and JSON output return Monarch's raw fields (`is_past`, `transaction_id`)
directly. The text display derives a human-readable label for convenience:

| Display | Condition | Confidence |
|---------|-----------|------------|
| PAID | `transaction_id` is non-null | **Assumed** — we believe non-null means payment matched |
| OVERDUE | `is_past` is true AND `transaction_id` is null | **Assumed** — depends on `isPast` and `transactionId` meanings |
| UPCOMING | `is_past` is false AND `transaction_id` is null | **Assumed** — depends on `isPast` meaning |

`last_paid_date` provides the date of the most recent paid occurrence across the
trailing 12 months. Comparing `last_paid_date` to `due_date` gives a picture of
whether a payment is current — but this relies on our assumptions about what
`transactionId` being non-null actually means.

---

## Architecture Considerations for Obligations Tracking

### The Core Problem

Monarch's recurring list is useful but has concerns as a sole source of truth:

- Items are transaction-seeded, not user-declared
- Merchant names can change upstream
- Account disconnections could affect linked items
- Credit card payments are categorized as "Transfer" (indistinguishable from
  non-obligation transfers)
- No custom categories to tag obligations vs. non-obligations
- `RecurringTransactionFilter` schema is unknown, limiting server-side filtering

### Recommended Approach: Blacklist + Snapshot

Rather than maintaining a separate whitelist of obligations (double maintenance),
use Monarch's recurring list as the source with two guardrails:

1. **Blacklist** (local config): Streams/categories/merchants to ignore. Anything
   in Monarch's recurring that's NOT on the blacklist = your obligations. Less
   maintenance than a whitelist — you only track exceptions.

2. **Snapshot comparison**: Cache the previous run's list and alert if anything
   disappeared between runs. Catches silent removal (merchant changes, account
   disconnects, etc.) without requiring a full whitelist.

Neither of these has been implemented yet.

### Alternative: Whitelist (Local Config as Source of Truth)

For maximum control, maintain a YAML/JSON config file as the canonical register.
Monarch becomes enrichment only. Higher maintenance but absolute control — nothing
falls off the list without an explicit edit to the file.

### Enrichment Queries (Available Now)

| Query | Enrichment |
|-------|-----------|
| `GetAccounts` | Current balances for credit cards and loan accounts |
| `GetTransactionsList` (filter by merchant) | Transaction history for a merchant |
| `GetBills` (not yet implemented) | Due dates and statement balances via Bill Sync |

---

## Things We Need to Test Against the Live API

These are questions that can only be answered by making actual API calls with real
data. None of this has been tested.

1. **What does `isPast` actually mean?** Is it relative to today? To the query
   range? Is it a fixed property set when the item is created? Test by querying
   the same date range at different times and observing if `isPast` changes.

2. **What does `transactionId` being null vs non-null mean?** Does non-null always
   mean "paid"? Can it be set for partial payments? Test by looking at items where
   you know the payment status.

3. **How does the date range work?** What happens with:
   - A full calendar month (Jan 1 – Jan 31)
   - A mid-month range (Jan 15 – Feb 15)
   - A multi-month range (Jan 1 – Jun 30)
   - A single day
   Do you get one item per stream per month? Or per occurrence within the range?

4. **Is `stream.id` stable across months?** If I query January and March separately,
   does Netflix have the same `stream.id` both times?

5. **Does the API return items for months where no payment was expected?** If a
   stream is weekly, does querying one month return ~4 items?

6. **What does `amountDiff` contain?** When is it non-zero?

7. **What does `RecurringTransactionFilter` accept?** Capture from DevTools when
   using filter/sort options on the Monarch Recurring page.

8. **What does `Common_GetRecurringStreams` return?** Does it have fields like
   `lastPaidDate` that would eliminate our need to derive it?

9. **Are tags available on recurring streams?** Check via DevTools or by adding
   a tag to a recurring item in the UI.

10. **What mutation fires when adding a recurring merchant?** Capture from DevTools
    when adding one through the UI.

---

## Q&A: Analysis Discussion Log

Key questions and answers from the research and design process.

### Can I store my obligations list in Monarch?

**Yes, but with caveats.** You can add recurring items through the Monarch UI (manually
search for a merchant and add it). Once added, items persist until you explicitly remove
them. However, recurring items are **transaction-seeded** — you can't create one from
thin air without at least one matching transaction. If you need to add a brand-new
obligation with no history, you'd first create a manual transaction in Monarch to seed it.

### Can the API create new recurring items?

**No known mutation exists.** No community library (Python, TypeScript, Go) has found
a `CreateRecurringStream` or equivalent mutation. The mutations that do exist are
`Web_ReviewStream` (update status) and `Common_MarkAsNotRecurring` (remove). However,
the mutation almost certainly exists internally — it could be captured from the Monarch
web app's network traffic (DevTools → Network → filter `graphql` → add a recurring
merchant and observe the request).

### What about auto-detected items appearing without my control?

Auto-detected items go through a **review flow** — they're presented as suggestions
that you confirm or dismiss. They don't appear on the confirmed list without your
approval. However, the review queue itself could be noisy.

### If I maintain a local whitelist, why use Monarch at all?

You wouldn't need Monarch as the list source — a local config file is more reliable
for stability. But a **blacklist** approach is more practical: let Monarch be the
source, maintain a local blacklist of things to ignore, and use snapshot comparison
to catch anything that silently drops off.

### What does "stream" mean?

It's Monarch's internal term for a recurring obligation — not data streaming or
financial streaming. A "stream" is a single commitment (e.g., "Netflix, $15.49/month").
It generates "items" which are individual monthly occurrences. Our implementation
collapses items back to streams so the user sees the stable obligations list.

### What would a credit card payment be in the category field?

Most likely **"Transfer"** — the same category Monarch uses for any money movement
between accounts. This is problematic because it makes CC payments (obligations)
indistinguishable from savings transfers or reimbursements (not obligations) by
category alone.

### Is the category on a recurring stream separate from the transaction category?

**No, they're the same.** The recurring stream inherits its category from the
transaction that seeded it. There is no independent "stream category" field. If the
source transaction is categorized as "Transfer", the stream's category will be
"Transfer". Recategorizing the source transaction would change the stream's category.

### Can I create custom categories?

**No.** Monarch categories are system-defined. You cannot add custom categories like
"Monthly Obligations" or "Critical Bills." Tags (user-created, freeform) exist on
transactions, but it's unconfirmed whether they're available on recurring streams.

### What are the date range parameters for?

The Monarch API requires a date range to return recurring items — but these are
**projected occurrences**, not actual transactions. If you query January–March, you
presumably get multiple items per stream (one per month). The date range determines
which projected occurrences you see, not which obligations exist.

**However**: We have NOT tested how the date range actually works. We don't know what
happens with mid-month ranges, or exactly how many items come back per stream per
month. See "Things We Need to Test" above.

### How does `isPast` work?

**We don't know for certain.** We assume it means "the due date has passed relative
to today's date" — making it a dynamic field that changes as time passes. But it
could be relative to the query date range, or a fixed property. This needs to be
tested against the live API.

### Is there a built-in overdue indicator in Monarch?

**We don't know.** The help docs describe "Upcoming" and "Complete" sections, and say
past due unpaid items are "hidden from the calendar." But we haven't confirmed whether
Monarch's UI or API explicitly flags overdue items. The `isPast` + null `transactionId`
combination likely represents this state, but we're inferring — not confirming.

### How reliable is the payment status?

**Uncertain.** The status relies on Monarch's ability to match a transaction to a
recurring stream. From the help docs, matching is based on detecting a transaction
for the bill amount in the mapped account before the due date. Known considerations:

- **Variable amounts** (e.g., credit card minimum payments): The `isApproximate`
  flag may indicate this, but matching behavior is unclear.
- **Partially paid**: Help docs confirm this state exists for loans and credit cards.
  How it surfaces in the API (`transactionId`, `amountDiff`) is untested.
- **Manual marking**: Users can mark bills as paid in the UI. Whether this sets
  `transactionId` or uses a different mechanism is unknown.

### What if something silently disappears from the list?

This is the core stability concern. Monarch's recurring list could lose items if:
- A merchant name changes upstream
- An account gets disconnected
- Monarch changes its retention/detection behavior

The **blacklist + snapshot** approach mitigates this: cache the previous list and
diff against the current one. If a stream disappears that isn't on your blacklist,
flag it. This hasn't been implemented yet.

### How can I filter or categorize streams?

**Server-side**: The API accepts `$filters: RecurringTransactionFilter` but the
schema is undocumented. Fields would need to be reverse-engineered from DevTools.

**Client-side** (using data we already return): Category, account, frequency,
merchant name, amount, isApproximate, and payment-related fields are all available.
We don't currently expose filter parameters on the CLI or MCP tool.

### Do we have a last-paid date independent of current month?

**Not from Monarch directly.** The API does not return a `lastPaidDate` field on the
stream object (at least not in the query we use). Our code **derives** `last_paid_date`
by querying a trailing 12 months of items and finding the most recent one with a
non-null `transactionId`. This derivation depends on our assumptions about
`transactionId` meaning "paid" — which is untested.

The `Common_GetRecurringStreams` query (not yet implemented) might return a native
`lastPaidDate` field, but we don't know its schema.

### What is `due_date` exactly?

It's the `date` field from the most recent recurring transaction item returned by
the API. It's a full `YYYY-MM-DD` date (e.g., `2026-03-15`), not just a day-of-month.
Monarch presumably generates this per occurrence based on the stream's frequency and
anchor date — but we haven't confirmed this behavior. We don't know how Monarch
handles edge cases like months with fewer days (e.g., a "31st" anchor in February).

---

## Sources

- [Tracking Recurring Expenses and Bills — Monarch Help](https://help.monarch.com/hc/en-us/articles/4890751141908-Tracking-Recurring-Expenses-and-Bills)
- [Track Recurring Bills and Subscriptions — Monarch Blog](https://www.monarch.com/blog/track-recurring-bills-and-subscriptions)
- [Recurring Feature Page — Monarch](https://www.monarchmoney.com/features/recurring)
- [Getting Started with Bill Sync — Monarch Help](https://help.monarch.com/hc/en-us/articles/29446697869076-Getting-Started-with-Bill-Sync)
- [Introducing Bill Sync — Monarch Blog](https://www.monarch.com/blog/introducing-bill-sync)
- [monarchmoney Python Library — GitHub](https://github.com/hammem/monarchmoney)
- [monarchmoney-enhanced Fork — GitHub](https://github.com/keithah/monarchmoney-enhanced)
- [monarchmoney TypeScript SDK — GitHub](https://github.com/keithah/monarchmoney-ts)
