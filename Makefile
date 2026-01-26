.PHONY: install test integration-test clean uninstall help venv

# Create venv if it doesn't exist
venv:
	@if [ ! -d ".venv" ]; then \
		python3 -m venv .venv && \
		. .venv/bin/activate && pip install --upgrade pip && pip install -e '.[dev]'; \
	fi

# Install CLI + MCP server with pipx (for regular usage)
install:
	@command -v pipx >/dev/null 2>&1 || (echo "pipx not found; install with: pip install pipx"; exit 1)
	@echo "Installing monarch CLI with pipx..."
	@pipx install -e . --force 2>/dev/null || pipx install . --force
	@echo "Done. Run 'monarch --help' to get started."
	@echo "MCP server available as 'monarch-mcp'"

# Run unit tests (auto-creates venv if needed, no credentials required)
test: venv
	@. .venv/bin/activate && pytest

# Run integration tests (requires valid Monarch token)
integration-test: venv
	@. .venv/bin/activate && pytest tests/integration/ -v

# Clean build artifacts and venv
clean:
	rm -rf .venv build/ dist/ *.egg-info/ .pytest_cache/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

# Uninstall from pipx
uninstall:
	pipx uninstall monarch-access 2>/dev/null || true

# Show help
help:
	@echo "Available targets:"
	@echo "  install          - Install CLI + MCP server with pipx"
	@echo "  test             - Run unit tests (auto-creates venv, no credentials needed)"
	@echo "  integration-test - Run integration tests (requires Monarch token)"
	@echo "  clean            - Remove venv and build artifacts"
	@echo "  uninstall        - Remove from pipx"
