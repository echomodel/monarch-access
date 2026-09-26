"""Browser-session auth: cookie selection and request headers."""

import pytest

from monarch.auth import pick_session, BrowserSessionError
from monarch.client import MonarchClient


COOKIES = [
    {"name": "session_id", "domain": ".api.monarch.com", "value": "sess-1", "expires": 1790416142.0},
    {"name": "csrftoken", "domain": ".monarch.com", "value": "csrf-1", "expires": 1821568961.0},
    {"name": "csrftoken", "domain": ".example.com", "value": "other", "expires": -1},
    {"name": "monarchDeviceUUID", "domain": ".monarch.com", "value": "dev-1", "expires": -1},
]


def test_pick_session_selects_monarch_cookies():
    s = pick_session(COOKIES)
    assert s["session_id"] == "sess-1"
    assert s["csrftoken"] == "csrf-1"
    assert s["device_uuid"] == "dev-1"
    assert s["session_expires"] == "2026-09-26T09:49:02+00:00"


def test_pick_session_requires_login():
    with pytest.raises(BrowserSessionError):
        pick_session([c for c in COOKIES if c["name"] != "session_id"])


def test_session_headers_prefer_cookie_over_token():
    c = MonarchClient.from_profile({"token": "old", "session_id": "s", "csrftoken": "c", "device_uuid": "d"})
    h = c._auth_headers()
    assert h["Cookie"] == "session_id=s; csrftoken=c"
    assert h["x-csrftoken"] == "c"
    assert h["device-uuid"] == "d"
    assert "Authorization" not in h


def test_token_headers_when_no_session():
    c = MonarchClient.from_profile({"token": "tok"})
    assert c._auth_headers()["Authorization"] == "Token tok"
    assert not MonarchClient.from_profile({}).is_authenticated


def test_multipart_headers_drop_content_type():
    assert "Content-Type" not in MonarchClient(session_id="s", csrftoken="c")._auth_headers(content_type=None)


# --- storing the session in a user profile ---

import asyncio

from mcp_app import FileSystemUserDataStore
from mcp_app.bridge import DataStoreAuthAdapter
from mcp_app.models import UserAuthRecord

from monarch.auth import resolve_user, store_session, SessionTargetError

SESSION = {"session_id": "s", "csrftoken": "c", "device_uuid": "d", "session_expires": None}


@pytest.fixture
def store(tmp_path, monkeypatch):
    monkeypatch.setenv("APP_USERS_PATH", str(tmp_path / "users"))
    return DataStoreAuthAdapter(FileSystemUserDataStore("monarch"))


def _profile(store, user):
    return asyncio.run(store.get_full(user)).profile


def test_empty_local_store_defaults_to_local_user(store):
    user = asyncio.run(resolve_user(store, default_user="local"))
    asyncio.run(store_session(store, SESSION, user))
    assert user == "local"
    assert _profile(store, "local")["session_id"] == "s"


def test_session_merges_into_existing_profile(store):
    asyncio.run(store.save(UserAuthRecord(email="a@example.com"), profile={"token": "t"}))
    user = asyncio.run(resolve_user(store))
    asyncio.run(store_session(store, SESSION, user))
    profile = _profile(store, "a@example.com")
    assert profile["session_id"] == "s" and profile["token"] == "t"


def test_several_users_require_explicit_choice(store):
    for u in ("a@example.com", "b@example.com"):
        asyncio.run(store.save(UserAuthRecord(email=u), profile={}))
    with pytest.raises(SessionTargetError, match="a@example.com, b@example.com"):
        asyncio.run(resolve_user(store))
    assert asyncio.run(resolve_user(store, "b@example.com")) == "b@example.com"


def test_empty_remote_store_requires_user(store):
    with pytest.raises(SessionTargetError):
        asyncio.run(resolve_user(store))


# --- everyday Chrome cookie store ---

import hashlib
import sqlite3
from pathlib import Path

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from monarch import chrome_cookies

KEY = hashlib.pbkdf2_hmac("sha1", b"test-password", b"saltysalt", 1003, 16)


def _encrypt(value: str, host: str, version: int) -> bytes:
    plain = value.encode()
    if version >= 24:
        plain = hashlib.sha256(host.encode()).digest() + plain
    pad = 16 - len(plain) % 16
    plain += bytes([pad]) * pad
    enc = Cipher(algorithms.AES(KEY), modes.CBC(b" " * 16)).encryptor()
    return b"v10" + enc.update(plain) + enc.finalize()


def _make_profile(user_data: Path, profile: str, cookies: list[tuple], version: int = 24) -> None:
    d = user_data / profile
    d.mkdir(parents=True)
    con = sqlite3.connect(d / "Cookies")
    con.execute("CREATE TABLE meta (key TEXT, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('version', ?)", (str(version),))
    con.execute("CREATE TABLE cookies (host_key TEXT, name TEXT, value TEXT, "
                "encrypted_value BLOB, expires_utc INTEGER)")
    for host, name, value, expires_unix in cookies:
        expires_utc = int((expires_unix + 11644473600) * 1_000_000)
        con.execute("INSERT INTO cookies VALUES (?, ?, '', ?, ?)",
                    (host, name, _encrypt(value, host, version), expires_utc))
    con.commit()
    con.close()



@pytest.mark.parametrize("version", [23, 24])
def test_reads_and_decrypts_monarch_cookies(tmp_path, version):
    _make_profile(tmp_path, "Default", [
        (".api.monarch.com", "session_id", "sess-1", 1790416142),
        (".monarch.com", "csrftoken", "csrf-1", 1821568961),
        ("app.monarch.com", "monarchDeviceUUID", "dev-1", 1816768133),
        (".example.com", "session_id", "not-monarch", 1790416142),
    ], version=version)
    [(name, db)] = chrome_cookies.profile_cookie_dbs(tmp_path)
    assert name == "Default"
    session = pick_session(chrome_cookies.read_cookies(db, "monarch.com", KEY))
    assert session == {
        "session_id": "sess-1", "csrftoken": "csrf-1", "device_uuid": "dev-1",
        "session_expires": "2026-09-26T09:49:02+00:00",
    }


def test_profile_discovery_skips_non_profile_dirs(tmp_path):
    _make_profile(tmp_path, "Default", [])
    _make_profile(tmp_path, "Profile 2", [])
    _make_profile(tmp_path, "System Profile", [])
    assert [n for n, _ in chrome_cookies.profile_cookie_dbs(tmp_path)] == ["Default", "Profile 2"]


def test_unknown_encryption_scheme_is_rejected():
    with pytest.raises(chrome_cookies.ChromeCookieError):
        chrome_cookies.decrypt_value(b"v11" + b"\0" * 16, KEY, strip_host_digest=True)
