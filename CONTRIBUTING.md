# Contributing

## Project Structure

```
monarch-access/
├── pyproject.toml        # Package config and dependencies
├── monarch/              # SDK package
│   ├── cli.py            # CLI entry point
│   ├── client.py         # MonarchClient - auth & API requests
│   ├── queries.py        # GraphQL queries
│   ├── accounts.py       # Account operations & formatting
│   ├── categories.py     # Category operations
│   ├── net_worth.py      # Net worth report logic & formatting
│   ├── transactions/     # Transaction operations
│   │   ├── list.py
│   │   ├── get.py
│   │   └── update.py
│   └── providers/        # Provider abstraction for API/local switching
│       ├── base.py       # Protocol interfaces
│       ├── api/          # Real Monarch API provider
│       └── local/        # Local TinyDB provider (for testing)
└── tests/
    ├── conftest.py       # Pytest fixtures
    ├── fixtures/
    │   └── test_data_seed.json  # Seed data for test generation
    └── test_*.py         # Test modules

~/.config/monarch/token   # Auth token (created by monarch auth)
```

## Architecture

- **`client.py`**: Only handles authentication (token load/save) and the generic `_request()` method for GraphQL calls
- **Operation modules** (accounts.py, categories.py, transactions/*.py): Each contains the API call function and any formatting utilities for that operation
- **`cli.py`**: Thin layer that wires up Click commands to the operation modules

## Development Setup

```bash
git clone https://github.com/krisrowe/monarch-access.git
cd monarch-access
pip install -e .
```

The `-e` flag installs in editable mode so changes take effect immediately.

## Running Tests

```bash
pip install -e ".[dev]"
pytest
```

Tests use a local provider with TinyDB, so no network access or authentication is required. Test data is auto-generated from `tests/fixtures/test_data_seed.json` on first run.
