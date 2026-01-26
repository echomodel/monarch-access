# Configuring Monarch MCP Server with Gemini CLI

This document outlines how to configure the Monarch MCP Server for use with Gemini CLI and Gemini Code Assist in VS Code.

**Note:** IntelliJ's Gemini Code Assist plugin does not currently support MCP servers.

## Prerequisites

- **Monarch Access Installed:** `pipx install git+https://github.com/krisrowe/monarch-access.git`
- **Monarch Token:** Obtain your token via `monarch auth` - see [README.md](../README.md#authentication)
- **Gemini CLI or Gemini Code Assist Installed:**
  - For Gemini CLI: [Install Gemini CLI](https://google-gemini.github.io/gemini-cli/)
  - For Gemini Code Assist: Install from VS Code marketplace

## Quick Start

```bash
gemini mcp add monarch monarch-mcp --scope user
```

This adds the Monarch MCP server to your user scope so it's available in all projects.

## Verifying Configuration

```bash
gemini mcp list
```

Expected output:
```
Configured MCP servers:

✓ monarch: monarch-mcp (stdio) - Connected
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
gemini mcp add monarch monarch-mcp --scope user
```

## Manual Configuration

For fine-grained control, edit `~/.gemini/settings.json` directly:

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

**Server shows as "Disconnected":**

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
- Monarch tokens typically last several months
- Run `monarch auth "NEW_TOKEN"` to refresh
- No re-registration needed - the server reads from the token file

## Environment Variable Override

If you need to use a different token:

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

## VS Code Notes

- Configuration is shared with Gemini CLI - no separate setup needed
- Restart VS Code after config changes for Gemini Code Assist to pick them up
- User scope makes the server available in all workspaces

---

For more details on Gemini CLI MCP configuration, see the [official documentation](https://google-gemini.github.io/gemini-cli/docs/tools/mcp-server.html).
