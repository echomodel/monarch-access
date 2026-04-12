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

2. **Get your Monarch token** (see [README.md](./README.md#authentication))

3. **Register a local user** for MCP:
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
| `list_categories` | Get all transaction categories |
| `list_transactions` | Query transactions with filters (date, account, category, search) |
| `get_transaction` | Get details of a single transaction |
| `update_transaction` | Update category, merchant, notes, or review status |
| `mark_transactions_reviewed` | Bulk mark transactions as reviewed |
| `split_transaction` | Split a transaction across multiple categories |
| `create_transaction` | Create a manual transaction |
| `delete_transaction` | Delete a transaction |
| `list_recurring` | List tracked recurring obligations (bills, subscriptions, loans) |
| `update_recurring` | Update a recurring stream's status, amount, or frequency |
| `mark_as_not_recurring` | Permanently remove a recurring stream (deprecated — use `update_recurring`) |

## Configuration

### Local (stdio)

The MCP server uses mcp-app's user store. Register a local user with your Monarch token:

```bash
monarch-admin connect local
monarch-admin users add local --token $MONARCH_SESSION_TOKEN
```

To update the token later:
```bash
monarch-admin connect local
monarch-admin users add local --token "NEW_TOKEN"
```

### Cloud (HTTP)

See [Cloud Deployment](./README.md#cloud-deployment-optional) for deploying as an HTTP MCP server with multi-user support.

## Troubleshooting

### "Not authenticated" errors

Token may have expired. Get a new one:

1. Go to https://app.monarch.com/ and log in
2. Open DevTools (F12) → Console
3. Run: `JSON.parse(JSON.parse(localStorage.getItem("persist:root")).user).token`
4. Save: `monarch auth "NEW_TOKEN"`

### Server not starting

Test the server directly:
```bash
monarch-mcp stdio --user local
```

If it exits with errors, check that:
1. Dependencies are installed: `pipx reinstall monarch-access`
2. A local user is registered: `monarch-admin connect local && monarch-admin users add local --token $MONARCH_SESSION_TOKEN`

## Security

- **Token storage**: Never commit tokens to version control
- **Local stdio**: Runs locally under your user account; token stored in mcp-app's local user store
- **Cloud HTTP**: Tokens stored server-side; clients authenticate with JWTs issued by `monarch-admin`
- **Token expiration**: Monarch tokens expire periodically; update with `monarch-admin users add`

## Related Documentation

- [README.md](./README.md) - CLI usage and authentication
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Development setup
- [MCP Specification](https://modelcontextprotocol.io/) - Official MCP docs
