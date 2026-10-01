"""Persistent monarch-access settings (``$XDG_CONFIG_HOME/monarch/settings.json``).

Managed with `monarch-admin` subcommands, never environment variables.
Separate from ``setup.json``, which belongs to the admin CLI's `connect`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

DEFAULT_CDP_URL = "http://127.0.0.1:9222"


class SettingsError(ValueError):
    """Raised for an invalid setting value."""


def settings_path() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "monarch" / "settings.json"


def _load() -> dict:
    path = settings_path()
    if path.is_file():
        return json.loads(path.read_text())
    return {}


def _save(data: dict) -> None:
    path = settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n")


def get_cdp_url() -> str:
    """DevTools endpoint `acquire-session` checks first (default 127.0.0.1:9222)."""
    return _load().get("cdp_url") or DEFAULT_CDP_URL


def is_default_cdp_url() -> bool:
    return "cdp_url" not in _load()


def set_cdp_url(url: Optional[str]) -> str:
    """Store the DevTools endpoint; ``None`` resets to the default. Returns the effective URL."""
    data = _load()
    if url is None:
        data.pop("cdp_url", None)
    else:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https") or not parsed.hostname:
            raise SettingsError(f"Not a DevTools URL: {url!r} (expected e.g. {DEFAULT_CDP_URL})")
        data["cdp_url"] = url.rstrip("/")
    _save(data)
    return get_cdp_url()
