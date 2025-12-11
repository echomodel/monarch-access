# Configuring Monarch MCP Server with Gemini CLI and Gemini Code Assist

This document outlines how to configure the Monarch MCP Server for use with Gemini CLI and Gemini Code Assist extension in VS Code. The same configuration works for both clients, as they share the same `settings.json` configuration system.

**Note:** IntelliJ's Gemini Code Assist plugin does not currently support MCP servers.

## Prerequisites

- **Docker Setup Complete:** Follow the Docker setup steps in [MCP-SERVER.md](../MCP-SERVER.md) to build the Docker image.
- **Monarch Token:** Obtain your token via the CLI (`monarch auth`) - see main [README.md](../README.md#authentication).
- **Gemini CLI or Gemini Code Assist Installed:**
  - For Gemini CLI: [Install Gemini CLI](https://google-gemini.github.io/gemini-cli/)
  - For Gemini Code Assist: Install from VS Code marketplace

## Shared Configuration

Gemini CLI and Gemini Code Assist extension in VS Code share the same configuration system. When you configure the MCP server, the configuration is automatically available to both:
- Gemini CLI (command-line interface)
- Gemini Code Assist in VS Code

Both clients read from `~/.gemini/settings.json` (user scope) or `.gemini/settings.json` (project scope).

## Configuration Options

### Option A: Stdio Transport (Recommended)

With stdio transport, Gemini CLI automatically manages the Docker container:
- ✅ Container starts automatically when Gemini connects
- ✅ Container stops automatically when done (with `--rm` flag)
- ✅ No need to manually manage container lifecycle

#### Configuration (Manual Edit Required)

**Important:** The `gemini mcp add` command does not reliably parse complex docker arguments like `-v` (volume mounts) or `-e` (environment variables). You must manually edit `settings.json`.

Edit `~/.gemini/settings.json` (user scope) or `.gemini/settings.json` (project scope):

**Method 1 - Mount config directory (Recommended):**

This mounts your existing `~/.config/monarch/token` file read-only. Token refreshes via `monarch auth` work automatically.

```json
{
  "mcpServers": {
    "monarch": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-v", "${HOME}/.config/monarch:/root/.config/monarch:ro",
        "monarch-mcp-server:latest",
        "python", "server-stdio.py"
      ]
    }
  }
}
```

**Method 2 - Environment variable:**

Token is stored in settings.json. You'll need to update it manually when it expires.

```json
{
  "mcpServers": {
    "monarch": {
      "command": "docker",
      "args": [
        "run", "-i", "--rm",
        "-e", "MONARCH_TOKEN",
        "monarch-mcp-server:latest",
        "python", "server-stdio.py"
      ],
      "env": {
        "MONARCH_TOKEN": "your_actual_token_here"
      }
    }
  }
}
```

To get your token value:
```bash
cat ~/.config/monarch/token
```

### Option B: HTTP Transport (Manual Container Management)

With HTTP transport, you must manually manage the Docker container:
- Run `docker run -d` before using Gemini CLI
- Container stays running until you stop it
- Remember to start the container each session

#### Using `gemini mcp add` Command

```bash
gemini mcp add monarch \
  --transport http \
  --http-url "http://localhost:8000/mcp" \
  --scope user
```

#### Manual Configuration

```json
{
  "mcpServers": {
    "monarch": {
      "httpUrl": "http://localhost:8000/mcp"
    }
  }
}
```

**Important:** Before using, ensure the Docker container is running:
```bash
docker ps | grep monarch-mcp-server
# If not running:
docker run -d --name monarch-mcp-server -p 8000:8000 \
  -v ~/.config/monarch:/root/.config/monarch:ro \
  monarch-mcp-server:latest
```

## Configuration Scope

- **`--scope user`** - Saves to `~/.gemini/settings.json`, available everywhere (recommended)
- **`--scope project`** (default) - Saves to `.gemini/settings.json` in current directory

For Monarch, **user scope is recommended** since you'll want financial data access from various projects.

## Verifying Configuration

```bash
gemini mcp list
```

Expected output:
```
Configured MCP servers:

✓ monarch: docker run -i --rm ... (stdio) - Connected
```

## Security Considerations

**Token Storage:**
- With environment variable method, the actual token value is stored in plain text in `settings.json`
- Ensure restricted file permissions: `chmod 600 ~/.gemini/settings.json`
- Never commit `settings.json` containing tokens to version control

**Config Mount Method:**
- Token stays in `~/.config/monarch/token` (not duplicated in settings.json)
- More secure as token isn't stored in multiple places
- Token refreshes automatically when you run `monarch auth`

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

## Troubleshooting

**Server shows as "Disconnected":**
- For HTTP transport: Ensure container is running (`docker start monarch-mcp-server`)
- For stdio: Check Docker is running (`docker ps`)
- Verify token hasn't expired

**"Connection refused" errors:**
- Ensure Docker is running
- Check container logs: `docker logs monarch-mcp-server`
- Verify port 8000 isn't in use

**Token expiration:**
- Monarch tokens typically last several months
- Run `monarch auth "NEW_TOKEN"` to refresh
- With config mount method: No re-registration needed
- With env var method: Re-register with `gemini mcp add`

**Switching from HTTP to Stdio:**
```bash
gemini mcp remove monarch --scope user
# Then re-add with stdio transport (see above)
```

## VS Code Notes

- Configuration is shared with Gemini CLI - no separate setup needed
- Restart VS Code after config changes for Gemini Code Assist to pick them up
- User scope makes the server available in all workspaces

---

For more details on Gemini CLI MCP server configuration, see the [official documentation](https://google-gemini.github.io/gemini-cli/docs/tools/mcp-server.html).
