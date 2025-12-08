"""Provider factory and interfaces."""

import os
from pathlib import Path
from typing import TYPE_CHECKING, Optional, Union

from .base import Provider, TransactionsProvider, AccountsProvider, CategoriesProvider
from .api import APIProvider

if TYPE_CHECKING:
    from .local import LocalProvider

__all__ = [
    "Provider",
    "TransactionsProvider",
    "AccountsProvider",
    "CategoriesProvider",
    "APIProvider",
    "LocalProvider",
    "get_provider",
]

# Environment variable to switch providers
PROVIDER_ENV_VAR = "MONARCH_PROVIDER"
LOCAL_DB_PATH_ENV_VAR = "MONARCH_LOCAL_DB"


def get_provider(
    provider_type: Optional[str] = None,
    db_path: Optional[Path] = None,
) -> Union[APIProvider, "LocalProvider"]:
    """Get a provider instance based on configuration.

    Provider selection priority:
    1. Explicit provider_type argument
    2. MONARCH_PROVIDER environment variable
    3. Default to 'api'

    Args:
        provider_type: 'api' or 'local'. If None, uses env var or defaults to 'api'.
        db_path: Path to local database file (only used with 'local' provider).

    Returns:
        Provider instance.
    """
    if provider_type is None:
        provider_type = os.environ.get(PROVIDER_ENV_VAR, "api")

    provider_type = provider_type.lower()

    if provider_type == "local":
        # Lazy import to avoid requiring tinydb for normal CLI usage
        from .local import LocalProvider
        if db_path is None:
            env_path = os.environ.get(LOCAL_DB_PATH_ENV_VAR)
            if env_path:
                db_path = Path(env_path)
        return LocalProvider(db_path)
    elif provider_type == "api":
        return APIProvider()
    else:
        raise ValueError(f"Unknown provider type: {provider_type}. Use 'api' or 'local'.")
