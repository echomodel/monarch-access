# Configuring Monarch MCP Server with Claude Code

This document outlines how to configure the Monarch MCP Server for use with Claude Code (the CLI tool).

## Prerequisites

- **Monarch Access Installed:** `pipx install git+https://github.com/krisrowe/monarch-access.git`
- **Monarch Token:** Obtain your token via `monarch auth` - see [README.md](../README.md#authentication)
- **Claude Code Installed:** [Install Claude Code](https://docs.anthropic.com/en/docs/claude-code)

## Quick Start

```bash
claude mcp add --scope user monarch monarch-mcp
```

This adds the Monarch MCP server to your user scope so it's available in all projects.

## Verifying Configuration

```bash
# List all configured MCP servers
claude mcp list

# You should see monarch listed with "Connected" status
```

Within a Claude Code session, use `/mcp` to check server status.

## Configuration Scope

| Scope | Flag | Use Case |
|-------|------|----------|
| `user` | `--scope user` | Personal use across all projects (recommended) |
| `project` | `--scope project` | Only current project |

For Monarch, **user scope is recommended** since you'll want financial data access from various projects.

## Using with Claude Code

Once configured, interact naturally:

- "What are my account balances?"
- "Show me transactions from last week"
- "Find all Amazon purchases this month"
- "Mark these transactions as reviewed"
- "Split this transaction between Groceries and Entertainment"

## Managing Servers

```bash
# Remove the server
claude mcp remove --scope user monarch

# Update by removing and re-adding
claude mcp remove --scope user monarch
claude mcp add --scope user monarch monarch-mcp
```

## Manual Configuration

For team sharing or fine-grained control, you can manually edit config files.

**User scope** (`~/.claude/settings.local.json`):

```json
{
  "mcpServers": {
    "monarch": {
      "command": "monarch-mcp"
    }
  }
}
```

**Project scope** (`.mcp.json` in project root):

```json
{
  "mcpServers": {
    "monarch": {
      "command": "monarch-mcp"
    }
  }
}
```

## Troubleshooting

**Server not connecting:**

1. Verify `monarch-mcp` is in PATH:
   ```bash
   which monarch-mcp
   ```

2. Test the server directly:
   ```bash
   monarch-mcp
   ```
   (Press Ctrl+C to exit)

3. Verify token is configured:
   ```bash
   monarch accounts
   ```

**Token expiration:**
- Run `monarch auth "NEW_TOKEN"` to refresh
- No re-configuration needed - the server reads from the token file

**Permission errors:**
- Claude Code prompts for approval on project-scoped servers
- User-scoped servers don't require approval

## Environment Variable Override

If you need to use a different token than the default file:

```bash
MONARCH_TOKEN="your_token" claude
```

Or in manual config:

```json
{
  "mcpServers": {
    "monarch": {
      "command": "monarch-mcp",
      "env": {
        "MONARCH_TOKEN": "your_token_here"
      }
    }
  }
}
```

---

For more details on Claude Code MCP configuration, see the [official documentation](https://docs.anthropic.com/en/docs/claude-code/mcp).
