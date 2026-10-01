"""Monarch Money SDK - lightweight Python client for Monarch Money API."""

from .client import MonarchClient
from . import accounts
from . import net_worth
from . import transactions

__all__ = ["MonarchClient", "accounts", "net_worth", "transactions", "app"]
__version__ = "0.9.0"

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
            "Monarch web session cookie (HttpOnly). Set with `monarch-admin "
            "acquire-session` (from a browser, or by hand with --stdin); re-run it "
            "when calls fail with 'session invalid or expired'."
        ),
    )
    csrftoken: Optional[str] = Field(
        default=None,
        description="Monarch csrftoken cookie, sent as the x-csrftoken header. Set with session_id by acquire-session.",
    )
    device_uuid: Optional[str] = Field(
        default=None,
        description="Browser device id (monarchDeviceUUID cookie). Optional; set with session_id by acquire-session.",
    )
    session_expires: Optional[str] = Field(
        default=None,
        description=(
            "Session cookie expiry (ISO-8601 UTC), for operator visibility. The latest "
            "the session can last, not a guarantee; Monarch may end it sooner."
        ),
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

from .admin import acquire_session as _acquire_session, cdp_url as _cdp_url  # noqa: E402

app.admin_cli.add_command(_acquire_session)
app.admin_cli.add_command(_cdp_url)
