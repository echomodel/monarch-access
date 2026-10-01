"""acquire-session source order: DevTools endpoint first, cookie store only as fallback.

Sources are stand-ins for the two browser readers (network/Keychain I/O);
the ordering, liveness and fallback logic under test is the real code.
"""

import asyncio

import pytest

from monarch import settings
from monarch.auth import (
    BrowserSessionError, CdpSource, SourceUnavailable, acquire_from,
)
from monarch.client import AuthenticationError


def _session(sid: str) -> dict:
    return {"session_id": sid, "csrftoken": "c", "device_uuid": None, "session_expires": None}


class FakeSource:
    def __init__(self, name, sessions=(), unavailable=False):
        self.name = name
        self.sessions = [_session(s) for s in sessions]
        self.unavailable = unavailable
        self.reads = 0
        self.logins = 0

    async def candidates(self):
        self.reads += 1
        if self.unavailable:
            raise SourceUnavailable(f"{self.name} unreachable")
        return list(self.sessions)

    async def open_login(self):
        self.logins += 1


def _verifier(live: set):
    async def verify(session):
        if session["session_id"] not in live:
            raise AuthenticationError("rejected")
    return verify


def _acquire(sources, live, wait=0):
    return asyncio.run(acquire_from(sources, verify_fn=_verifier(live), wait=wait, poll=0))


def test_live_devtools_session_is_used_and_cookie_store_never_read():
    cdp = FakeSource("devtools", ["cdp-live"])
    cookies = FakeSource("cookie-store", ["cookie-live"])
    session, source = _acquire([cdp, cookies], live={"cdp-live", "cookie-live"})
    assert session["session_id"] == "cdp-live" and source == "devtools"
    assert cookies.reads == 0  # no Keychain access


def test_unreachable_devtools_endpoint_falls_back_to_cookie_store():
    cdp = FakeSource("devtools", unavailable=True)
    cookies = FakeSource("cookie-store", ["cookie-live"])
    session, source = _acquire([cdp, cookies], live={"cookie-live"})
    assert session["session_id"] == "cookie-live" and source == "cookie-store"


@pytest.mark.parametrize("cdp_sessions", [[], ["cdp-dead"]], ids=["no-session", "dead-session"])
def test_devtools_without_live_session_falls_back_to_cookie_store(cdp_sessions):
    # Liveness is decided by the API, not cookie expiry: a present but rejected
    # session counts the same as none.
    cdp = FakeSource("devtools", cdp_sessions)
    cookies = FakeSource("cookie-store", ["cookie-live"])
    session, source = _acquire([cdp, cookies], live={"cookie-live"})
    assert session["session_id"] == "cookie-live" and source == "cookie-store"


def test_no_live_session_anywhere_opens_login_in_first_reachable_source():
    cdp = FakeSource("devtools", ["cdp-dead"])
    cookies = FakeSource("cookie-store", [])
    with pytest.raises(BrowserSessionError, match="No Monarch sign-in"):
        _acquire([cdp, cookies], live=set())
    assert (cdp.logins, cookies.logins) == (1, 0)


def test_nothing_reachable_is_an_error():
    with pytest.raises(BrowserSessionError, match="reachable"):
        _acquire([FakeSource("devtools", unavailable=True)], live=set())


def test_closed_devtools_port_is_unavailable_not_an_error():
    # Real connection attempt to a port nothing listens on.
    with pytest.raises(SourceUnavailable):
        asyncio.run(CdpSource("http://127.0.0.1:1").candidates())


def test_cdp_url_setting_persists_and_resets(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert settings.get_cdp_url() == settings.DEFAULT_CDP_URL and settings.is_default_cdp_url()
    assert settings.set_cdp_url("http://127.0.0.1:9333/") == "http://127.0.0.1:9333"
    assert settings.get_cdp_url() == "http://127.0.0.1:9333" and not settings.is_default_cdp_url()
    assert settings.set_cdp_url(None) == settings.DEFAULT_CDP_URL


def test_cdp_url_setting_rejects_non_urls(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    with pytest.raises(settings.SettingsError):
        settings.set_cdp_url("9222")


# --- manual import (--stdin) ---

import json

from click.testing import CliRunner

from monarch import app
from monarch.auth import NoSourceReachable, acquire_session, default_sources, session_from_input


def test_print_output_round_trips_as_manual_input():
    printed = {"session_id": "s", "csrftoken": "c", "device_uuid": "d",
               "session_expires": "2026-11-30T00:00:00+00:00"}
    assert session_from_input(json.loads(json.dumps(printed))) == printed


def test_devtools_cookie_names_are_accepted():
    session = session_from_input({"session_id": " s ", "csrftoken": "c", "monarchDeviceUUID": "d"})
    assert session == {"session_id": "s", "csrftoken": "c", "device_uuid": "d", "session_expires": None}


@pytest.mark.parametrize("data,match", [
    ({"csrftoken": "c"}, "session_id"),
    ({"session_id": "s", "csrftoken": ""}, "csrftoken"),
    ({"session_id": "s", "csrftoken": "c", "sessionid": "x"}, "Unknown"),
])
def test_manual_input_is_validated(data, match):
    with pytest.raises(BrowserSessionError, match=match):
        session_from_input(data)


@pytest.mark.parametrize("stdin,match", [
    ("not json", "not valid JSON"),
    ('{"csrftoken": "c"}', "session_id"),
])
def test_stdin_import_rejects_bad_input_before_touching_any_store(stdin, match, tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))  # no admin target configured
    result = CliRunner().invoke(app.admin_cli, ["acquire-session", "--stdin"], input=stdin)
    assert result.exit_code != 0 and match in result.output


def test_stdin_and_cdp_are_mutually_exclusive():
    result = CliRunner().invoke(app.admin_cli, ["acquire-session", "--stdin", "--cdp", "http://127.0.0.1:9222"])
    assert result.exit_code != 0 and "mutually exclusive" in result.output


# --- platform source order ---

def test_cookie_store_fallback_only_on_macos():
    assert [type(s).__name__ for s in default_sources("http://127.0.0.1:9222", "darwin")] == ["CdpSource", "ChromeSource"]
    assert [type(s).__name__ for s in default_sources("http://127.0.0.1:9222", "linux")] == ["CdpSource"]


def test_unreachable_endpoint_alone_is_no_source_reachable():
    # Only the (unreachable) DevTools source, as on a non-macOS host.
    with pytest.raises(NoSourceReachable):
        asyncio.run(acquire_from(default_sources("http://127.0.0.1:1", "linux"), wait=0))


def test_no_endpoint_error_says_what_to_do():
    # Explicit endpoint => DevTools source only (never the Keychain route).
    with pytest.raises(NoSourceReachable) as exc:
        asyncio.run(acquire_session("http://127.0.0.1:1", wait=0))
    message = str(exc.value)
    assert "remote debugging" in message and "cdp-url" in message and "--stdin" in message
