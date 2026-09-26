"""Read cookies from the user's installed Google Chrome profiles (macOS).

Chrome stores cookies in a per-profile SQLite database with values
encrypted by AES-128-CBC. The key is derived from the "Chrome Safe Storage"
password in the macOS login Keychain; reading it makes macOS ask the user
once for permission. HttpOnly cookies are stored like any other, so this
reaches session cookies that page scripts and DevTools on a normal
(non-debugging) Chrome cannot.

Only cookies whose host ends with the requested domain are decrypted.
"""

from __future__ import annotations

import hashlib
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Optional

# Chrome stores expiry as microseconds since 1601-01-01 UTC.
_WINDOWS_EPOCH_OFFSET = 11644473600
# From meta.version 24 on, the plaintext is prefixed with SHA-256(host_key).
_HOST_DIGEST_VERSION = 24


class ChromeCookieError(Exception):
    """Raised when Chrome's cookie store cannot be read or decrypted."""


def chrome_user_data_dir() -> Path:
    return Path.home() / "Library" / "Application Support" / "Google" / "Chrome"


def profile_cookie_dbs(user_data_dir: Optional[Path] = None) -> list[tuple[str, Path]]:
    """Return (profile name, cookie DB path) for every Chrome profile."""
    base = user_data_dir or chrome_user_data_dir()
    found = []
    if not base.is_dir():
        return found
    for profile in sorted(base.iterdir()):
        if not (profile.name == "Default" or profile.name.startswith("Profile ")):
            continue
        for rel in ("Cookies", "Network/Cookies"):
            db = profile / rel
            if db.is_file():
                found.append((profile.name, db))
                break
    return found


def safe_storage_key() -> bytes:
    """Derive the cookie encryption key from the Keychain (prompts once)."""
    if sys.platform != "darwin":
        raise ChromeCookieError("Reading Chrome's cookie store is supported on macOS only.")
    proc = subprocess.run(
        ["security", "find-generic-password", "-w", "-s", "Chrome Safe Storage", "-a", "Chrome"],
        capture_output=True, text=True,
    )
    if proc.returncode != 0 or not proc.stdout.strip():
        raise ChromeCookieError(
            "Keychain access to 'Chrome Safe Storage' was denied or not found. "
            "Re-run and choose Allow (or Always Allow) when macOS asks."
        )
    return hashlib.pbkdf2_hmac("sha1", proc.stdout.strip().encode(), b"saltysalt", 1003, 16)


def decrypt_value(encrypted: bytes, key: bytes, *, strip_host_digest: bool) -> str:
    """Decrypt one ``encrypted_value`` blob (``v10`` scheme)."""
    from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

    if not encrypted.startswith(b"v10"):
        raise ChromeCookieError("Unsupported cookie encryption scheme.")
    decryptor = Cipher(algorithms.AES(key), modes.CBC(b" " * 16)).decryptor()
    plain = decryptor.update(encrypted[3:]) + decryptor.finalize()
    pad = plain[-1]
    if not 1 <= pad <= 16:
        raise ChromeCookieError("Cookie decryption failed (bad padding).")
    plain = plain[:-pad]
    if strip_host_digest:
        plain = plain[32:]
    return plain.decode("utf-8")


def read_cookies(db_path: Path, domain: str, key: bytes) -> list[dict]:
    """Return cookies for ``domain`` from one profile DB, in the CDP cookie shape
    (``name``, ``domain``, ``value``, ``expires`` as Unix seconds or -1)."""
    with tempfile.TemporaryDirectory() as tmp:
        # Chrome holds the DB open; read a copy.
        copy = Path(tmp) / "Cookies"
        shutil.copyfile(db_path, copy)
        con = sqlite3.connect(copy)
        try:
            version = int((con.execute("SELECT value FROM meta WHERE key='version'").fetchone() or [0])[0])
            rows = con.execute(
                "SELECT host_key, name, value, encrypted_value, expires_utc FROM cookies "
                "WHERE host_key = ? OR host_key LIKE ?",
                (domain, f"%.{domain}"),
            ).fetchall()
        finally:
            con.close()
    cookies = []
    for host, name, value, encrypted, expires_utc in rows:
        if not value and encrypted:
            value = decrypt_value(encrypted, key, strip_host_digest=version >= _HOST_DIGEST_VERSION)
        expires = expires_utc / 1_000_000 - _WINDOWS_EPOCH_OFFSET if expires_utc else -1
        cookies.append({"name": name, "domain": host, "value": value, "expires": expires})
    return cookies
