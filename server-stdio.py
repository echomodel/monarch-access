#!/usr/bin/env python3
"""
Entry point for stdio mode (used when MCP clients auto-start the server).
This allows the server to run in stdio mode for automatic container management.
"""

import sys

sys.path.insert(0, "/app")

from server import mcp

if __name__ == "__main__":
    mcp.run(transport="stdio")
