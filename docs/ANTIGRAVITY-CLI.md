# Configuring Monarch MCP Server with Antigravity CLI (agy)

Antigravity CLI (`agy`) replaced Gemini CLI. It keeps one user-level MCP
configuration (no user/project scopes).

## Prerequisites

- **Monarch Access installed:** `pipx install git+https://github.com/echomodel/monarch-access.git`
- **Monarch session imported:** see [README.md](../README.md#authentication)
- **`agy` installed**

## Local (stdio)

```bash
agy mcp add monarch -- monarch-mcp stdio --user local
```

The `--` is required: everything after it is passed to the server command,
including `--user`, which would otherwise be read as an `agy` flag.

## Remote (HTTP)

Flags must come before the server name; the URL makes it an HTTP server.

```bash
agy mcp add --header "Authorization: Bearer <token>" monarch https://your-service-url/
```

`monarch-admin register --user <email>` prints this command with the URL and
a token filled in. See [README.md](../README.md#cloud-deployment-optional)
for issuing tokens.

## Managing servers

```bash
agy mcp list
agy mcp remove monarch
```

To change a registration, remove it and add it again.

## Manual configuration

`agy mcp add` writes `~/.gemini/config/mcp_config.json`:

```json
{
  "mcpServers": {
    "monarch": {
      "command": "monarch-mcp",
      "args": ["stdio", "--user", "local"],
      "disabled": false
    },
    "monarch-remote": {
      "serverUrl": "https://your-service-url/",
      "headers": { "Authorization": "Bearer <token>" },
      "disabled": false
    }
  }
}
```

HTTP servers use the key `serverUrl` (not `url`).

## Non-interactive runs

`agy -p "<prompt>"` runs headless and needs the server's tools allowed in
`~/.gemini/antigravity-cli/settings.json`:

```json
{ "permissions": { "allow": ["mcp(monarch/*)"] } }
```

## Troubleshooting

**"Monarch session invalid or expired":** see
[README → Session lifecycle](../README.md#session-lifecycle).

**Server not starting:** run `monarch-mcp stdio --user local` directly to see
errors; check that a session is imported into the local store
([README → Authentication](../README.md#authentication)).
