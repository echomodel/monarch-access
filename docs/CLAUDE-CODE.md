# Configuring Monarch MCP Server with Claude Code

This document outlines how to configure the Monarch MCP Server for use with Claude Code (the CLI tool).

## Prerequisites

- **Docker Setup Complete:** Follow the Docker setup steps in [MCP-SERVER.md](../MCP-SERVER.md) to build the Docker image.
- **Monarch Token:** Obtain your token via the CLI (`monarch auth`) - see main [README.md](../README.md#authentication).
- **Claude Code Installed:** [Install Claude Code](https://docs.anthropic.com/en/docs/claude-code)

## Quick Start

```bash
claude mcp add --scope user monarch -- docker run -i --rm \
  -v ~/.config/monarch:/root/.config/monarch:ro \
  monarch-mcp-server:latest python server-stdio.py
```

This adds the Monarch MCP server to your user scope so it's available in all projects.

## Configuration Options

### Option A: CLI Command (Recommended)

The simplest way to add the MCP server:

```bash
claude mcp add --scope user monarch -- docker run -i --rm \
  -v ~/.config/monarch:/root/.config/monarch:ro \
  monarch-mcp-server:latest python server-stdio.py
```

**Key points:**
- `--scope user` makes the server available across all projects
- `--` separates Claude's flags from the Docker command
- The config mount method shares your existing token, so `monarch auth` refreshes work automatically

### Option B: Manual Configuration

For team sharing or more control, create a `.mcp.json` file.

**User scope** (`~/.claude.json`):

```json
{
  "mcpServers": {
    "monarch": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "~/.config/monarch:/root/.config/monarch:ro",
        "monarch-mcp-server:latest",
        "python", "server-stdio.py"
      ]
    }
  }
}
```

**Project scope** (`.mcp.json` in project root):

```json
{
  "mcpServers": {
    "monarch": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "~/.config/monarch:/root/.config/monarch:ro",
        "monarch-mcp-server:latest",
        "python", "server-stdio.py"
      ]
    }
  }
}
```

### Option C: Environment Variable Method

If you prefer to pass the token directly instead of mounting the config:

```bash
claude mcp add --scope user monarch -- docker run -i --rm \
  -e MONARCH_TOKEN="$(cat ~/.config/monarch/token)" \
  monarch-mcp-server:latest python server-stdio.py
```

Or in JSON:

```json
{
  "mcpServers": {
    "monarch": {
      "type": "stdio",
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "MONARCH_TOKEN",
        "monarch-mcp-server:latest",
        "python", "server-stdio.py"
      ],
      "env": {
        "MONARCH_TOKEN": "your_token_here"
      }
    }
  }
}
```

## Configuration Scope

| Scope | Location | Use Case |
|-------|----------|----------|
| `user` | `~/.claude.json` | Personal use across all projects (recommended) |
| `project` | `.mcp.json` in project root | Team sharing |
| `local` | Local to current session | Temporary testing |

For Monarch, **user scope is recommended** since you'll want financial data access from various projects.

## Verifying Configuration

```bash
# List all configured MCP servers
claude mcp list

# Get details for the monarch server
claude mcp get monarch
```

Within a Claude Code session, use the `/mcp` command to check server status.

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
claude mcp remove monarch --scope user

# Update by removing and re-adding
claude mcp remove monarch --scope user
claude mcp add --scope user monarch -- docker run ...
```

## Troubleshooting

**Server not connecting:**
- Ensure Docker is running: `docker ps`
- Check the Docker image exists: `docker images | grep monarch-mcp-server`
- Rebuild if needed: `docker build -t monarch-mcp-server:latest .`

**Token expiration:**
- Run `monarch auth "NEW_TOKEN"` to refresh
- With config mount method: No re-configuration needed
- With env var method: Re-add the server with the new token

**Permission errors:**
- Claude Code prompts for approval on project-scoped servers from `.mcp.json`
- User-scoped servers in `~/.claude.json` don't require approval

**Debug mode:**
For detailed server logs, run the Docker container manually:
```bash
docker run -i --rm \
  -v ~/.config/monarch:/root/.config/monarch:ro \
  monarch-mcp-server:latest python server-stdio.py
```

## Security Considerations

**Token Storage:**
- With env var method, the actual token value may be stored in plain text
- Config mount method is more secure (token stays in one place)
- Never commit `~/.claude.json` or `.mcp.json` containing tokens to version control

**File Permissions:**
```bash
chmod 600 ~/.claude.json
```

## Comparison with Other Clients

| Feature | Claude Code | Claude Desktop | Gemini CLI |
|---------|-------------|----------------|------------|
| Config file | `~/.claude.json` or `.mcp.json` | Platform-specific | `~/.gemini/settings.json` |
| Add command | `claude mcp add` | Manual JSON edit | `gemini mcp add` |
| Transport | stdio | stdio or HTTP | stdio or HTTP |
| Scope levels | user, project, local | N/A | user, project |

---

For more details on Claude Code MCP server configuration, see the [official documentation](https://docs.anthropic.com/en/docs/claude-code/mcp).
