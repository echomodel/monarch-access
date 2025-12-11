# Use a lightweight Python base image
FROM python:3.11-slim-bookworm

# Install curl for uv installation
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Install uv (Rust-based Python package manager)
RUN curl -LsSf https://astral.sh/uv/install.sh | sh \
    && mv /root/.local/bin/uv /usr/local/bin/uv

# Copy project files
COPY . /app

# Install the monarch-access package and MCP dependencies
RUN uv pip install --system "mcp[cli]" uvicorn && \
    uv pip install --system -e .

# Expose the port for HTTP transport
EXPOSE 8000

# Set environment variables
ENV LOG_LEVEL=INFO

# Default command: run MCP server with HTTP transport
CMD ["uvicorn", "server:mcp_app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "info"]
