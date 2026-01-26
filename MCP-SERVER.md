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

1. **Install the CLI** (includes MCP server):
   ```bash
   pipx install git+https://github.com/krisrowe/monarch-access.git
   ```

2. **Authenticate** (see [README.md](./README.md#authentication)):
   ```bash
   monarch auth "YOUR_TOKEN"
   ```

### Register with Claude Code

```bash
claude mcp add --scope user monarch monarch-mcp
```

### Register with Gemini CLI

```bash
gemini mcp add monarch monarch-mcp
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

## Resources

| Resource | Description |
|----------|-------------|
| `monarch://accounts` | All accounts as JSON |
| `monarch://categories` | All categories as JSON |

## Configuration

The MCP server uses the same token as the CLI:

| Source | Location |
|--------|----------|
| Token file | `~/.config/monarch/token` |
| Environment variable | `MONARCH_TOKEN` (takes precedence) |

Override config directory with `MONARCH_CONFIG_DIR` environment variable.

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
monarch-mcp
```

If it exits with errors, check that dependencies are installed:
```bash
pipx reinstall monarch-access
```

## HTTP Transport (Advanced)

For persistent server or multi-client setups:

```bash
pip install uvicorn
uvicorn monarch.mcp.server:mcp_app --host 127.0.0.1 --port 8000
```

Then configure your client to connect to `http://localhost:8000/mcp`.

## Security

- **Token storage**: Never commit tokens to version control
- **Local only**: The MCP server runs locally under your user account
- **Token expiration**: Monarch tokens expire periodically; regenerate as needed

## Related Documentation

- [docs/CLAUDE-CODE.md](./docs/CLAUDE-CODE.md) - Claude Code configuration details
- [docs/GEMINI-CLI.md](./docs/GEMINI-CLI.md) - Gemini CLI configuration details
- [README.md](./README.md) - CLI usage and authentication
- [CONTRIBUTING.md](./CONTRIBUTING.md) - Development setup
- [MCP Specification](https://modelcontextprotocol.io/) - Official MCP docs
