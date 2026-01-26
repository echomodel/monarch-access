# Contributing

## Project Structure

```
monarch-access/
├── pyproject.toml        # Package config, dependencies, entry points
├── Makefile              # Development commands
├── monarch/              # SDK package
│   ├── cli.py            # CLI entry point (monarch command)
│   ├── client.py         # MonarchClient - auth & API requests
│   ├── config.py         # Config/token path management
│   ├── queries.py        # GraphQL queries
│   ├── accounts.py       # Account operations & formatting
│   ├── categories.py     # Category operations
│   ├── net_worth.py      # Net worth report logic & formatting
│   ├── transactions/     # Transaction operations
│   │   ├── list.py
│   │   ├── get.py
│   │   └── update.py
│   ├── providers/        # Provider abstraction for API/local switching
│   │   ├── base.py       # Protocol interfaces
│   │   ├── api/          # Real Monarch API provider
│   │   └── local/        # Local TinyDB provider (for testing)
│   └── mcp/              # MCP server
│       └── server.py     # MCP server entry point (monarch-mcp command)
├── tests/
│   ├── conftest.py       # Pytest fixtures
│   ├── fixtures/
│   │   └── test_data_seed.json  # Seed data for test generation
│   ├── test_*.py         # Unit tests (use local provider)
│   └── integration/      # Integration tests (require live credentials)
│       └── test_live_reads.py

~/.config/monarch/token   # Auth token (created by monarch auth)
```

## Development

After cloning, just run tests - venv is created automatically:

```bash
git clone https://github.com/krisrowe/monarch-access.git
cd monarch-access
make test
```

### Make Commands

| Command | Description |
|---------|-------------|
| `make test` | Run unit tests (auto-creates venv, no credentials needed) |
| `make integration-test` | Run integration tests (requires Monarch token) |
| `make install` | Install CLI + MCP server with pipx |
| `make clean` | Remove venv and build artifacts |
| `make uninstall` | Remove from pipx |

### Testing

**Unit tests** use a local provider with TinyDB - no network or auth required. Test data is auto-generated from `tests/fixtures/test_data_seed.json`.

**Integration tests** hit the live Monarch API and are skipped automatically if no token is configured.

```bash
make test              # Unit tests only (default)
make integration-test  # Live API tests (requires token)
```

## Architecture

- **`config.py`**: Centralized config/token path management with env var overrides
- **`client.py`**: Auth and generic `_request()` for GraphQL calls
- **Operation modules** (accounts.py, categories.py, transactions/*.py): API calls and formatting
- **`cli.py`**: Thin Click wrapper over operation modules
- **`mcp/server.py`**: MCP server exposing same operations to AI assistants

## Architecture Notes

This project follows a CLI/MCP/SDK layered architecture:
- **SDK layer** (`monarch/*.py`): Business logic, reusable
- **CLI layer** (`monarch/cli.py`): Thin Click wrapper
- **MCP layer** (`monarch/mcp/`): Thin MCP wrapper exposing SDK to AI assistants
