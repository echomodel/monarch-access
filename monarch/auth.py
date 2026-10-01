"""Browser-session import for Monarch authentication.

Monarch's web app authenticates its API calls with an HttpOnly session
cookie plus a CSRF token, not a bearer token. The only place a valid
session exists is a signed-in browser. This module reads that session from
a Chrome running with remote debugging (DevTools protocol) or, as a
fallback, the everyday Chrome's cookie store (see ``chrome_cookies``; needs
Keychain access), verifies it against the API, and stores it in a user
profile of the local store or a remote deployment. A sign-in is requested
only when no source holds a session the API accepts.
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

from . import chrome_cookies, settings
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


class SourceUnavailable(Exception):
    """A session source cannot be read at all (e.g. no DevTools endpoint answers)."""


class NoSourceReachable(BrowserSessionError):
    """No session source could be read at all."""


MANUAL_SOURCE = "manual input"

# Accepted input keys -> profile field. Cookie names as shown in a browser's
# DevTools (Application -> Cookies -> app.monarch.com) are accepted alongside
# the profile field names that `acquire-session --print` emits.
_MANUAL_KEYS = {
    "session_id": "session_id",
    "csrftoken": "csrftoken",
    "device_uuid": "device_uuid",
    "monarchDeviceUUID": "device_uuid",
    "session_expires": "session_expires",
}


def session_from_input(data: dict) -> dict:
    """Build a session from manually supplied values (``--print`` JSON or cookie names).

    ``session_id`` and ``csrftoken`` are required; the device id and expiry are
    optional. Unknown keys are rejected so a typo cannot silently drop a field.
    """
    if not isinstance(data, dict):
        raise BrowserSessionError("Session input must be a JSON object.")
    unknown = sorted(set(data) - set(_MANUAL_KEYS))
    if unknown:
        raise BrowserSessionError(f"Unknown session field(s): {', '.join(unknown)}")
    session = {"session_id": None, "csrftoken": None, "device_uuid": None, "session_expires": None}
    for key, value in data.items():
        value = value.strip() if isinstance(value, str) else value
        if value:
            session[_MANUAL_KEYS[key]] = value
    missing = [k for k in ("session_id", "csrftoken") if not session[k]]
    if missing:
        raise BrowserSessionError(f"Missing required session field(s): {', '.join(missing)}")
    return session


class CdpSource:
    """Monarch session from a Chrome running with remote debugging (DevTools protocol)."""

    def __init__(self, cdp_url: str):
        self.cdp_url = cdp_url.rstrip("/")
        self.name = f"Chrome DevTools at {self.cdp_url}"

    async def candidates(self) -> list[dict]:
        try:
            cookies = (await _cdp_call(self.cdp_url, "Storage.getCookies"))["cookies"]
        except BrowserSessionError as exc:
            raise SourceUnavailable(str(exc)) from exc
        try:
            return [pick_session(cookies)]
        except BrowserSessionError:
            return []

    async def open_login(self) -> None:
        target = await _cdp_call(self.cdp_url, "Target.createTarget", {"url": LOGIN_URL})
        await _cdp_call(self.cdp_url, "Target.activateTarget", {"targetId": target["targetId"]})


class ChromeSource:
    """Monarch sessions from the everyday Chrome's cookie store (macOS Keychain prompt)."""

    name = "Chrome cookie store (Keychain)"

    def __init__(self):
        self._key: Optional[bytes] = None

    def _read(self) -> list[dict]:
        if self._key is None:
            self._key = chrome_cookies.safe_storage_key()
        found = []
        for _profile, db in chrome_cookies.profile_cookie_dbs():
            try:
                found.append(pick_session(chrome_cookies.read_cookies(db, MONARCH_DOMAIN, self._key)))
            except BrowserSessionError:
                continue
        return found

    async def candidates(self) -> list[dict]:
        try:
            return await asyncio.to_thread(self._read)
        except chrome_cookies.ChromeCookieError as exc:
            raise BrowserSessionError(str(exc)) from exc

    async def open_login(self) -> None:
        if sys.platform == "darwin":
            subprocess.run(["open", "-a", "Google Chrome", LOGIN_URL], check=False)
        else:
            webbrowser.open(LOGIN_URL)


async def acquire_from(sources: list, *, verify_fn: Callable = None, wait: float = 300,
                       poll: float = 3, on_status: Callable[[str], None] = lambda _m: None
                       ) -> tuple[dict, str]:
    """Return ``(session, source name)`` for the first live session, in source order.

    Liveness is decided by the API (``verify_fn``, default ``me { id }``), not by
    cookie expiry. A source that cannot be read at all (``SourceUnavailable``) is
    skipped; a source with no live session falls through to the next. When none
    has a live session, the Monarch sign-in page opens in the first readable
    source and that source is polled until a new session verifies or ``wait``
    seconds pass.
    """
    verify_fn = verify_fn or verify
    rejected: set = set()

    async def _live(source) -> Optional[dict]:
        for session in await source.candidates():
            if session["session_id"] in rejected:
                continue
            try:
                await verify_fn(session)
                return session
            except AuthenticationError:
                rejected.add(session["session_id"])
        return None

    readable = []
    for source in sources:
        try:
            session = await _live(source)
        except SourceUnavailable:
            continue
        readable.append(source)
        if session:
            return session, source.name
    if not readable:
        raise NoSourceReachable("No browser session source is reachable.")

    login_source = readable[0]
    await login_source.open_login()
    on_status(f"Sign in to Monarch in the tab that just opened ({login_source.name}); waiting...")
    deadline = time.monotonic() + wait
    while time.monotonic() < deadline:
        await asyncio.sleep(poll)
        session = await _live(login_source)
        if session:
            return session, login_source.name
    raise BrowserSessionError(f"No Monarch sign-in within {int(wait)} seconds.")


def default_sources(cdp_url: str, platform: str = sys.platform) -> list:
    """Source order without ``--cdp``: the DevTools endpoint, then (macOS only)
    the everyday Chrome's cookie store. No cookie-store reader exists for other
    platforms, so there the DevTools endpoint is the only automatic source."""
    sources = [CdpSource(cdp_url)]
    if platform == "darwin":
        sources.append(ChromeSource())
    return sources


async def acquire_session(cdp_url: Optional[str] = None, *, wait: float = 300, poll: float = 3,
                          on_status: Callable[[str], None] = lambda _m: None) -> tuple[dict, str]:
    """Return ``(session, source name)``, asking for a sign-in only when needed.

    With ``cdp_url`` given, only that DevTools endpoint is used. Otherwise the
    configured DevTools endpoint (``settings.get_cdp_url()``) is tried first and
    the everyday Chrome's cookie store — which needs Keychain access — only when
    that endpoint is unreachable or holds no live session (macOS only).
    """
    endpoint = cdp_url or settings.get_cdp_url()
    sources = [CdpSource(endpoint)] if cdp_url else default_sources(endpoint)
    try:
        return await acquire_from(sources, wait=wait, poll=poll, on_status=on_status)
    except NoSourceReachable:
        raise NoSourceReachable(
            f"No Chrome DevTools endpoint answered at {endpoint}. Start a Chrome with "
            "remote debugging enabled and signed in to Monarch (set its endpoint with "
            "`monarch-admin cdp-url`), or import the session manually with "
            "`monarch-admin acquire-session --stdin`."
        ) from None


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
