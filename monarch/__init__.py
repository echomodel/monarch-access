"""Monarch Money SDK - lightweight Python client for Monarch Money API."""

from .client import MonarchClient
from . import accounts
from . import net_worth
from . import transactions

__all__ = ["MonarchClient", "accounts", "net_worth", "transactions", "app"]
__version__ = "0.3.0"

# --- mcp-app integration ---

from pydantic import BaseModel, Field
from mcp_app import App
from .mcp import tools
import monarch as _self


class Profile(BaseModel):
    """Per-user profile storing the Monarch Money session token.

    Field descriptions drive `monarch-admin users add --help` output —
    they are the re-discovery path for operators who need to know what
    each field is for months after initial setup. Always include a
    Field(description=...) that states what the credential is and how
    to obtain it.
    """

    token: str = Field(
        description=(
            "Monarch Money session token. Obtain from the browser: "
            "log in at https://app.monarch.com/, open DevTools console, "
            "and run "
            "`JSON.parse(JSON.parse(localStorage.getItem(\"persist:root\")).user).token`. "
            "Tokens typically last several months."
        )
    )


app = App(
    name="monarch",
    tools_module=tools,
    sdk_package=_self,
    profile_model=Profile,
    profile_expand=True,
)
