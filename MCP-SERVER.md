# Monarch MCP Server

A **Model Context Protocol (MCP)** server that exposes Monarch Money financial data to AI assistants.

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io/) is an open standard that enables AI assistants to securely connect to external data sources. With the Monarch MCP Server, you can ask your AI assistant things like:

- "Show me my spending on groceries this month"
- "Find all Amazon transactions and mark them as reviewed"
- "Split this transaction between Groceries and Household categories"
- "What are my current account balances?"

## Quick Start

### Prerequisites

1. **Install** (includes CLI, MCP server, and admin tools):
   ```bash
   pipx install git+https://github.com/krisrowe/monarch-access.git
   ```

2. **Import your Monarch session** into the local store (opens a Monarch
   sign-in in Chrome when needed; see [README.md](./README.md#authentication)):
   ```bash
   monarch-admin connect local
   monarch-admin acquire-session
   ```

### Register with Claude Code

```bash
claude mcp add --scope user monarch -- monarch-mcp stdio --user local
```

### Register with Gemini CLI

```bash
gemini mcp add monarch -- monarch-mcp stdio --user local
```

### Verify

```bash
# Claude Code
claude mcp list

# Gemini CLI
gemini mcp list
```

## Available Tools

| Tool | Description |
|------|-------------|
| `list_accounts` | Get all financial accounts with balances |
| `count_accounts` | Count open accounts (returns only a number; the admin safe tool) |
| `list_categories` | Get all transaction categories |
| `list_transactions` | Query transactions with filters (date, account, category, search, tags) |
| `get_transaction` | Get details of a single transaction |
| `update_transaction` | Update category, merchant, notes, or review status |
| `mark_transactions_reviewed` | Bulk mark transactions as reviewed |
| `split_transaction` | Split a transaction across multiple categories |
| `create_transactions` | Create one or more manual transactions (partial success reported) |
| `delete_transactions` | Delete one or more transactions (partial success reported) |
| `list_recurring` | List tracked recurring obligations (bills, subscriptions, loans) |
| `update_recurring` | Update a recurring stream's status, amount, or frequency |
| `mark_as_not_recurring` | Permanently remove a recurring stream (deprecated — use `update_recurring`) |
| `list_tags` | List all transaction tags (id, name, color) |
| `add_transaction_tag` | Add a tag to a transaction (created if missing); preserves existing tags |
| `remove_transaction_tag` | Remove a tag from a transaction, preserving its other tags |

## Configuration

### Local (stdio)

The MCP server uses mcp-app's user store. `monarch-admin acquire-session`
imports the Monarch browser session into the `local` user's profile:

```bash
monarch-admin connect local
monarch-admin acquire-session
```

Re-run `acquire-session` to rotate an expired session.

### Cloud (HTTP)

See [Cloud Deployment](./README.md#cloud-deployment-optional) for deploying as an HTTP MCP server with multi-user support.

## Troubleshooting

### "Monarch session invalid or expired" / "No Monarch session configured"

The stored session has expired or was never imported:

Run `monarch-admin acquire-session` against each target you use
(`monarch-admin connect local` or `connect <url> --signing-key …` first). It
opens a Monarch sign-in in Chrome when the browser's session has expired.

`monarch-admin users get-profile local` shows the stored `session_expires`.

### Server not starting

Test the server directly:
```bash
monarch-mcp stdio --user local
```

If it exits with errors, check that:
1. Dependencies are installed: `pipx reinstall monarch-access`
2. A session is imported: `monarch-admin connect local && monarch-admin acquire-session`

## Security

- **Credential storage**: Never commit session values to version control; `acquire-session` never prints them unless `--print` is given
- **Local stdio**: Runs locally under your user account; the session is stored in mcp-app's local user store
- **Cloud HTTP**: The session is stored server-side; clients authenticate with JWTs issued by `monarch-admin`
- **Session expiration**: Monarch sessions expire after a fixed period; rotate with `monarch-admin acquire-session`

## Related Documentation

- [README.md](./README.md) - CLI usage and authentication
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Development setup
- [MCP Specification](https://modelcontextprotocol.io/) - Official MCP docs
