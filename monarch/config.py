"""Configuration management for Monarch Access.

Handles configuration paths following XDG conventions.
Default: ~/.config/monarch/
"""

import os
from pathlib import Path


def get_config_dir() -> Path:
    """Get the configuration directory path.

    Respects MONARCH_CONFIG_DIR environment variable if set,
    otherwise uses ~/.config/monarch/
    """
    env_path = os.getenv("MONARCH_CONFIG_DIR")
    if env_path:
        return Path(env_path)
    return Path.home() / ".config" / "monarch"


def get_token_file() -> Path:
    """Get the path to the token file.

    Respects MONARCH_TOKEN_FILE environment variable if set,
    otherwise uses {config_dir}/token
    """
    env_path = os.getenv("MONARCH_TOKEN_FILE")
    if env_path:
        return Path(env_path)
    return get_config_dir() / "token"


def get_token() -> str | None:
    """Get the authentication token.

    Priority:
    1. MONARCH_TOKEN environment variable
    2. Token file at get_token_file() path

    Returns None if no token is available.
    """
    # Check environment variable first
    token = os.getenv("MONARCH_TOKEN")
    if token:
        return token.strip()

    # Fall back to token file
    token_file = get_token_file()
    if token_file.exists():
        return token_file.read_text().strip()

    return None


def save_token(token: str) -> Path:
    """Save the authentication token to the token file.

    Creates the config directory if it doesn't exist.
    Returns the path where the token was saved.
    """
    token_file = get_token_file()
    token_file.parent.mkdir(parents=True, exist_ok=True)
    token_file.write_text(token)
    return token_file
