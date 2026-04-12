"""Monarch Money SDK - lightweight Python client for Monarch Money API."""

from .client import MonarchClient
from . import accounts
from . import net_worth
from . import transactions

__all__ = ["MonarchClient", "accounts", "net_worth", "transactions", "app"]
__version__ = "0.3.0"

# --- mcp-app integration ---

from pydantic import BaseModel
from mcp_app import App
from .mcp import tools


class Profile(BaseModel):
    """Per-user profile storing the Monarch Money session token."""
    token: str


app = App(
    name="monarch",
    tools_module=tools,
    profile_model=Profile,
    profile_expand=True,
)
