"""Browser-session import for Monarch authentication.

Monarch's web app authenticates its API calls with an HttpOnly session
cookie plus a CSRF token, not a bearer token. The only place a valid
session exists is a signed-in browser. This module reads that session from
the user's everyday Chrome (its cookie store; see ``chrome_cookies``) or,
optionally, from a Chrome running with remote debugging, verifies it
against the API, and stores it in a user profile of the local store or a
remote deployment. A sign-in is requested only when the browser holds no
session the API accepts.
"""

from __future__ import annotations

import asyncio
import subprocess
import sys
import time
import webbrowser
from datetime import datetime, timezone
from typing import Callable, Optional

import aiohttp

from . import chrome_cookies
from .client import MonarchClient, AuthenticationError

LOCAL_USER = "local"  # user the CLI and stdio MCP server read

WHOAMI_QUERY = "query Whoami { me { id } }"


class BrowserSessionError(Exception):
    """Raised when no usable Monarch session can be read from the browser."""


def pick_session(cookies: list[dict]) -> dict:
    """Select the Monarch auth cookies from a cookie list (CDP cookie shape).

    Returns a profile-update dict: session_id, csrftoken, device_uuid and
    session_expires (ISO-8601 UTC). Raises BrowserSessionError when the
    session cookie is missing — i.e. the browser is not logged in.
    """
    def _monarch(c: dict) -> bool:
        return c.get("domain", "").endswith("monarch.com")

    session = next((c for c in cookies if c.get("name") == "session_id" and _monarch(c)), None)
    csrf = next((c for c in cookies if c.get("name") == "csrftoken" and _monarch(c)), None)
    device = next((c for c in cookies if c.get("name") == "monarchDeviceUUID" and _monarch(c)), None)

    if not session or not session.get("value"):
        raise BrowserSessionError(
            "No Monarch session cookie in the browser (not signed in to Monarch)."
        )
    if not csrf or not csrf.get("value"):
        raise BrowserSessionError("Monarch csrftoken cookie missing — reload https://app.monarch.com/ and retry.")

    expires = session.get("expires")
    expires_iso = (
        datetime.fromtimestamp(expires, tz=timezone.utc).isoformat(timespec="seconds")
        if isinstance(expires, (int, float)) and expires > 0 else None
    )
    return {
        "session_id": session["value"],
        "csrftoken": csrf["value"],
        "device_uuid": device["value"] if device and device.get("value") else None,
        "session_expires": expires_iso,
    }


LOGIN_URL = "https://app.monarch.com/login"
MONARCH_DOMAIN = "monarch.com"


async def _cdp_call(cdp_url: str, method: str, params: Optional[dict] = None) -> dict:
    """Send one browser-level DevTools command and return its result."""
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(f"{cdp_url}/json/version",
                                timeout=aiohttp.ClientTimeout(total=5)) as resp:
                ws_url = (await resp.json())["webSocketDebuggerUrl"]
            async with http.ws_connect(ws_url, max_msg_size=0) as ws:
                await ws.send_json({"id": 1, "method": method, "params": params or {}})
                while True:
                    msg = await ws.receive_json()
                    if msg.get("id") == 1:
                        break
    except (aiohttp.ClientError, OSError, asyncio.TimeoutError, KeyError) as exc:
        raise BrowserSessionError(f"Cannot reach Chrome DevTools at {cdp_url} ({exc}).") from exc
    if "error" in msg:
        raise BrowserSessionError(f"DevTools error: {msg['error']}")
    return msg.get("result", {})


class ChromeSource:
    """Monarch sessions from the user's everyday Chrome (its cookie store)."""

    def __init__(self):
        self._key: Optional[bytes] = None

    def candidates(self) -> list[dict]:
        if self._key is None:
            self._key = chrome_cookies.safe_storage_key()
        found = []
        for _profile, db in chrome_cookies.profile_cookie_dbs():
            try:
                found.append(pick_session(chrome_cookies.read_cookies(db, MONARCH_DOMAIN, self._key)))
            except BrowserSessionError:
                continue
        # Longest-lived session first: the most recent sign-in.
        return sorted(found, key=lambda s: s.get("session_expires") or "", reverse=True)

    async def open_login(self) -> None:
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "Google Chrome", LOGIN_URL], check=False)
        else:
            webbrowser.open(LOGIN_URL)


class CdpSource:
    """Monarch session from a Chrome the user runs with remote debugging."""

    def __init__(self, cdp_url: str):
        self.cdp_url = cdp_url.rstrip("/")

    async def open_login(self) -> None:
        target = await _cdp_call(self.cdp_url, "Target.createTarget", {"url": LOGIN_URL})
        await _cdp_call(self.cdp_url, "Target.activateTarget", {"targetId": target["targetId"]})


async def _candidates(source) -> list[dict]:
    if isinstance(source, CdpSource):
        cookies = (await _cdp_call(source.cdp_url, "Storage.getCookies"))["cookies"]
        try:
            return [pick_session(cookies)]
        except BrowserSessionError:
            return []
    try:
        return await asyncio.to_thread(source.candidates)
    except chrome_cookies.ChromeCookieError as exc:
        raise BrowserSessionError(str(exc)) from exc


async def acquire_session(cdp_url: Optional[str] = None, *, wait: float = 300, poll: float = 3,
                          on_status: Callable[[str], None] = lambda _m: None) -> dict:
    """Return a verified Monarch session, asking for a sign-in only when needed.

    Reads the session the browser already holds (the everyday Chrome's cookie
    store by default, or a debugging Chrome at ``cdp_url``). If none is
    accepted by the API, opens the Monarch sign-in page in that browser and
    polls until a new session verifies or ``wait`` seconds pass.
    """
    source = CdpSource(cdp_url) if cdp_url else ChromeSource()

    async def _first_valid(seen: set) -> Optional[dict]:
        for session in await _candidates(source):
            if session["session_id"] in seen:
                continue
            seen.add(session["session_id"])
            try:
                await verify(session)
                return session
            except AuthenticationError:
                continue
        return None

    rejected: set = set()
    session = await _first_valid(rejected)
    if session:
        return session
    await source.open_login()
    on_status("Sign in to Monarch in the Chrome tab that just opened; waiting...")
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        await asyncio.sleep(poll)
        session = await _first_valid(rejected)
        if session:
            return session
    raise BrowserSessionError(f"No Monarch sign-in within {int(wait)} seconds.")


class SessionTargetError(Exception):
    """Raised when the user whose profile should receive the session is ambiguous."""


async def resolve_user(store, user: Optional[str] = None, default_user: Optional[str] = None) -> str:
    """Pick the user whose profile receives the session.

    An explicit ``user`` wins. Otherwise the store's only user is chosen;
    an empty store falls back to ``default_user`` (the local CLI user).
    Several users with none named is an error listing the choices.
    """
    if user:
        return user
    users = [u.email for u in await store.list()]
    if len(users) == 1:
        return users[0]
    if not users and default_user:
        return default_user
    if not users:
        raise SessionTargetError("No users registered; pass --user to create one.")
    raise SessionTargetError(
        f"{len(users)} users registered; pass --user to pick one: {', '.join(sorted(users))}"
    )


async def store_session(store, session: dict, user: str) -> None:
    """Merge the session fields into ``user``'s profile, creating the user if absent.

    ``store`` is an mcp-app UserAuthStore (local data-store adapter or
    remote admin adapter), so the same call serves both deployment modes.
    """
    from mcp_app.models import UserAuthRecord
    if await store.get(user) is None:
        await store.save(UserAuthRecord(email=user), profile=dict(session))
    else:
        await store.update_profile(user, dict(session))


async def verify(profile_updates: dict) -> None:
    """Prove the imported session works by asking the API who we are."""
    client = MonarchClient.from_profile(profile_updates)
    data = await client._request(WHOAMI_QUERY)
    if not (data.get("me") or {}).get("id"):
        raise AuthenticationError("Session imported but the API did not recognize it")
