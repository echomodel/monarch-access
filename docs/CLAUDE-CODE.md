# Configuring Monarch MCP Server with Claude Code

## Prerequisites

- **Monarch Access Installed:** `pipx install git+https://github.com/krisrowe/monarch-access.git`
- **Monarch Token:** See [README.md](../README.md#authentication)
- **Claude Code Installed:** [Install Claude Code](https://docs.anthropic.com/en/docs/claude-code)

## Quick Start

1. Register a local user with your Monarch session token:
   ```bash
   monarch-admin connect local
   monarch-admin users add local --token $MONARCH_SESSION_TOKEN
   ```

2. Add the MCP server:
   ```bash
   claude mcp add --scope user monarch -- monarch-mcp stdio --user local
   ```

## Verifying Configuration

```bash
claude mcp list
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
claude mcp add --scope user monarch -- monarch-mcp stdio --user local
```

## Manual Configuration

**User scope** (`~/.claude/settings.local.json`):

```json
{
  "mcpServers": {
    "monarch": {
      "command": "monarch-mcp",
      "args": ["stdio", "--user", "local"]
    }
  }
}
```

**Project scope** (`.mcp.json` in project root):

```json
{
  "mcpServers": {
    "monarch": {
      "command": "monarch-mcp",
      "args": ["stdio", "--user", "local"]
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
   monarch-mcp stdio --user local
   ```

3. Verify a local user is registered:
   ```bash
   monarch-admin connect local
   monarch-admin users list
   ```

**Token expiration:**
- Monarch tokens expire periodically
- Update with: `monarch-admin users add local --token "NEW_TOKEN"`
- No MCP re-registration needed

**Permission errors:**
- Claude Code prompts for approval on project-scoped servers
- User-scoped servers don't require approval

---

For more details on Claude Code MCP configuration, see the [official documentation](https://docs.anthropic.com/en/docs/claude-code/mcp).
