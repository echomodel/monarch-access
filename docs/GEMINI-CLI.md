# Configuring Monarch MCP Server with Gemini CLI

## Prerequisites

- **Monarch Access Installed:** `pipx install git+https://github.com/krisrowe/monarch-access.git`
- **Monarch Token:** See [README.md](../README.md#authentication)
- **Gemini CLI or Gemini Code Assist Installed:**
  - For Gemini CLI: [Install Gemini CLI](https://google-gemini.github.io/gemini-cli/)
  - For Gemini Code Assist: Install from VS Code marketplace

**Note:** IntelliJ's Gemini Code Assist plugin does not currently support MCP servers.

## Quick Start

1. Register a local user with your Monarch session token:
   ```bash
   monarch-admin connect local
   monarch-admin users add local --token $MONARCH_SESSION_TOKEN
   ```

2. Add the MCP server:
   ```bash
   gemini mcp add monarch -- monarch-mcp stdio --user local
   ```

## Verifying Configuration

```bash
gemini mcp list
```

## Configuration Scope

| Scope | Flag | Use Case |
|-------|------|----------|
| `--scope user` | User-wide | Personal use across all projects (recommended) |
| `--scope project` | Project only | Current directory only |

For Monarch, **user scope is recommended** since you'll want financial data access from various projects.

## Shared Configuration

Gemini CLI and Gemini Code Assist (VS Code) share the same configuration:
- User scope: `~/.gemini/settings.json`
- Project scope: `.gemini/settings.json`

Configure once, use in both!

## Using with Gemini

Once configured, interact naturally:

**With Gemini CLI:**
- "What are my account balances?"
- "Show me transactions from last week"
- "Find all Amazon purchases this month"
- "Mark these transactions as reviewed"

**With Gemini Code Assist (VS Code):**
- Use natural language in the chat interface
- The extension automatically uses the configured MCP server

## Managing Servers

```bash
# Remove the server
gemini mcp remove monarch --scope user

# Update by removing and re-adding
gemini mcp remove monarch --scope user
gemini mcp add monarch -- monarch-mcp stdio --user local
```

## Manual Configuration

Edit `~/.gemini/settings.json`:

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

**Server shows as "Disconnected":**

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

## VS Code Notes

- Configuration is shared with Gemini CLI - no separate setup needed
- Restart VS Code after config changes for Gemini Code Assist to pick them up
- User scope makes the server available in all workspaces

---

For more details on Gemini CLI MCP configuration, see the [official documentation](https://google-gemini.github.io/gemini-cli/docs/tools/mcp-server.html).
