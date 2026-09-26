"""Monarch Money SDK - lightweight Python client for Monarch Money API."""

from .client import MonarchClient
from . import accounts
from . import net_worth
from . import transactions

__all__ = ["MonarchClient", "accounts", "net_worth", "transactions", "app"]
__version__ = "0.8.0"

# --- mcp-app integration ---

from typing import Optional

from pydantic import BaseModel, Field
from mcp_app import App, SafeTool
from .mcp import tools
import monarch as _self


class Profile(BaseModel):
    """Per-user profile holding the Monarch browser session.

    Field descriptions drive `monarch-admin users add --help` output —
    they are the re-discovery path for operators who need to know what
    each field is for months after initial setup. Every field must carry a
    Field(description=...) stating what the value is and how to obtain it.
    """

    session_id: Optional[str] = Field(
        default=None,
        description=(
            "Monarch web session cookie (HttpOnly). Imported from a logged-in "
            "Chrome with `monarch-admin acquire-session`; sessions expire after a "
            "fixed period, re-run it when calls start failing."
        ),
    )
    csrftoken: Optional[str] = Field(
        default=None,
        description="Monarch csrftoken cookie, sent as the x-csrftoken header. Stored with session_id by acquire-session.",
    )
    device_uuid: Optional[str] = Field(
        default=None,
        description="Browser device id (monarchDeviceUUID cookie). Stored with session_id by acquire-session.",
    )
    session_expires: Optional[str] = Field(
        default=None,
        description="When the imported session expires (ISO-8601 UTC), for operator visibility.",
    )
    token: Optional[str] = Field(
        default=None,
        description="Monarch bearer token; used only when no session_id is stored.",
    )


app = App(
    name="monarch",
    tools_module=tools,
    sdk_package=_self,
    profile_model=Profile,
    profile_expand=True,
    safe_tool=SafeTool(
        name="count_accounts",
        arguments={},
        description="Counts the user's Monarch accounts (returns only a number).",
    ),
)

from .admin import acquire_session as _acquire_session  # noqa: E402

app.admin_cli.add_command(_acquire_session)
