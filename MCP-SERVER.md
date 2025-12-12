# Monarch MCP Server

A **Model Context Protocol (MCP)** server that exposes Monarch Money financial data to AI assistants and agentic tools.

## What is MCP?

The [Model Context Protocol](https://modelcontextprotocol.io/) is an open standard that enables AI assistants to securely connect to external data sources and tools. MCP allows LLMs to:

- **Read data** from your applications (accounts, transactions, categories)
- **Take actions** on your behalf (update transactions, mark as reviewed)
- **Maintain context** across conversations

By running the Monarch MCP Server, you give AI assistants like Claude Desktop, Gemini CLI, and other MCP-compatible tools direct access to your Monarch Money financial data—enabling powerful workflows like:

- "Show me my spending on groceries this month"
- "Find all Amazon transactions and mark them as reviewed"
- "Split this transaction between Groceries and Household categories"
- "What's my current account balances?"

## Features

### Tools (Actions)

| Tool | Description |
|------|-------------|
| `list_accounts` | Get all financial accounts with balances |
| `list_categories` | Get all transaction categories |
| `list_transactions` | Query transactions with filters (date, account, category, search) |
| `get_transaction` | Get details of a single transaction |
| `update_transaction` | Update category, merchant, notes, or review status |
| `mark_transactions_reviewed` | Bulk mark transactions as reviewed |
| `split_transaction` | Split a transaction across multiple categories |

### Resources (Read-only Data)

| Resource | Description |
|----------|-------------|
| `monarch://accounts` | All accounts as JSON |
| `monarch://categories` | All categories as JSON |

For detailed documentation, see [docs/TOOLS.md](./docs/TOOLS.md).

## Quick Start

### Prerequisites

- **Docker**: [Install Docker](https://www.docker.com/get-started)
- **Monarch Money Token**: See main [README](./README.md#authentication)
- **MCP Client**: Claude Desktop, Gemini CLI, or similar

### Step 1: Build the Docker Image

```bash
cd monarch-access
docker build -t monarch-mcp-server:latest .
```

### Step 2: Run the Server

**HTTP Transport** (persistent server):

```bash
export MONARCH_TOKEN="your_token_here"

docker run -d \
  --name monarch-mcp-server \
  -p 8000:8000 \
  -e MONARCH_TOKEN="$MONARCH_TOKEN" \
  monarch-mcp-server:latest
```

**Stdio Transport** (auto-managed by client):

Configure your MCP client to run the server directly (see client configs below).

### Step 3: Verify

```bash
docker ps | grep monarch-mcp-server
docker logs monarch-mcp-server
```

## Configuring MCP Clients

### Claude Desktop

Add to your Claude Desktop config:
- **Linux**: `~/.config/claude/claude_desktop_config.json`
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`

**HTTP Transport** (requires running container):

```json
{
  "mcpServers": {
    "monarch": {
      "url": "http://localhost:8000/mcp"
    }
  }
}
```

**Stdio Transport** (auto-starts container):

Option 1 - **Mount config directory (Recommended)**: The container reads the token from your existing CLI config, so token refreshes via `monarch auth` work automatically:

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

Option 2 - Pass token as environment variable:

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
        "MONARCH_TOKEN": "your_token_here"
      }
    }
  }
}
```

### Gemini CLI and Gemini Code Assist

Quick setup (mounts your existing token config):

```bash
gemini mcp add monarch docker run -i --rm \
  -v ~/.config/monarch:/root/.config/monarch:ro \
  monarch-mcp-server:latest python server-stdio.py
```

For detailed configuration options, HTTP vs stdio transport, VS Code integration, and troubleshooting, see **[docs/GEMINI-CLI.md](./docs/GEMINI-CLI.md)**.

### Claude Code (CLI)

Quick setup (mounts your existing token config):

```bash
claude mcp add --scope user monarch -- docker run -i --rm \
  -v ~/.config/monarch:/root/.config/monarch:ro \
  monarch-mcp-server:latest python server-stdio.py
```

For detailed configuration options, scope levels, and troubleshooting, see **[docs/CLAUDE-CODE.md](./docs/CLAUDE-CODE.md)**.

### Other MCP Clients

For HTTP transport, connect to `http://localhost:8000/mcp` with the Docker container running.

For stdio transport, configure the client to execute:
```bash
docker run -i --rm -e MONARCH_TOKEN="$TOKEN" monarch-mcp-server:latest python server-stdio.py
```

## Local Development

Run without Docker for development:

```bash
# Install dependencies
pip install -e ".[mcp]"

# HTTP transport
uvicorn server:mcp_app --host 0.0.0.0 --port 8000

# Stdio transport
python server.py --stdio
```

## Transport Options

| Transport | Description | Use Case |
|-----------|-------------|----------|
| **HTTP** | Server runs persistently, clients connect via HTTP | Multiple clients, persistent connection |
| **Stdio** | Server starts/stops with each client session | Single client, automatic lifecycle |

## Managing the Container

```bash
# Stop
docker stop monarch-mcp-server

# Start
docker start monarch-mcp-server

# View logs
docker logs -f monarch-mcp-server

# Remove
docker rm -f monarch-mcp-server

# Rebuild (after code changes)
docker build -t monarch-mcp-server:latest .
```

## Troubleshooting

### Container Issues

**Port already in use:**
```bash
lsof -i :8000
# Use a different port: -p 8001:8000
```

**Container exits immediately:**
```bash
docker logs monarch-mcp-server
# Check for missing MONARCH_TOKEN
```

### Authentication Issues

**401 errors or "Not authenticated":**
- Token may have expired
- Get a new token from the browser (see main README)
- Ensure `MONARCH_TOKEN` environment variable is set

### Client Connection Issues

1. Verify container is running: `docker ps`
2. Check server logs: `docker logs monarch-mcp-server`
3. Test endpoint: `curl -X POST http://localhost:8000/mcp -H "Content-Type: application/json" -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{}}'`

## Architecture

The MCP server uses the same Provider interface as the CLI:

```
┌──────────────────┐     ┌──────────────────┐
│   Claude/Gemini  │     │       CLI        │
│   (MCP Client)   │     │    (monarch)     │
└────────┬─────────┘     └────────┬─────────┘
         │                        │
         ▼                        ▼
┌──────────────────────────────────────────┐
│           Provider Interface             │
│  get_accounts(), get_transactions(), ... │
├──────────────────────────────────────────┤
│             APIProvider                  │
│         (Monarch Money API)              │
└──────────────────────────────────────────┘
```

This ensures consistent behavior across CLI, MCP, and any third-party integrations.

## Security Considerations

- **Token storage**: Never commit tokens to version control
- **Container security**: The container only needs network access to Monarch's API
- **Local only**: By default, the HTTP server only listens on localhost
- **Token expiration**: Monarch tokens expire; regenerate as needed

## Related Documentation

- [Tools Reference](./docs/TOOLS.md) - Detailed documentation of all MCP tools and resources
- [Claude Code Setup](./docs/CLAUDE-CODE.md) - Claude Code CLI configuration
- [Gemini CLI Setup](./docs/GEMINI-CLI.md) - Gemini CLI and Code Assist configuration
- [Main README](./README.md) - CLI usage and authentication setup
- [MCP Specification](https://modelcontextprotocol.io/) - Official MCP documentation
