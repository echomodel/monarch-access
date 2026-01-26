"""Monarch Money API client."""

from pathlib import Path
from typing import Optional

import aiohttp

from .config import get_token, get_token_file, save_token as config_save_token

GRAPHQL_URL = "https://api.monarch.com/graphql"

HEADERS = {
    "Content-Type": "application/json",
    "Accept": "*/*",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": "https://app.monarch.com",
    "Referer": "https://app.monarch.com/",
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
}


class MonarchClientError(Exception):
    """Base exception for Monarch client errors."""
    pass


class AuthenticationError(MonarchClientError):
    """Raised when authentication fails."""
    pass


class APIError(MonarchClientError):
    """Raised when API request fails."""
    pass


class MonarchClient:
    """Lightweight client for Monarch Money API."""

    def __init__(
        self,
        token: Optional[str] = None,
    ):
        self._token = token or get_token()
        self._token_file = get_token_file()

    def save_token(self) -> None:
        """Save token to file."""
        if not self._token:
            raise AuthenticationError("No token to save")

        config_save_token(self._token)

    @property
    def is_authenticated(self) -> bool:
        return self._token is not None

    async def _request(self, query: str, variables: Optional[dict] = None) -> dict:
        if not self._token:
            raise AuthenticationError(
                "Not authenticated. Get token from browser:\n"
                "1. Login to https://app.monarch.com/\n"
                "2. DevTools (F12) -> Console\n"
                "3. Run: JSON.parse(JSON.parse(localStorage.getItem('persist:root')).user).token"
            )

        headers = {**HEADERS, "Authorization": f"Token {self._token}"}
        payload = {"query": query}
        if variables:
            payload["variables"] = variables

        async with aiohttp.ClientSession() as session:
            async with session.post(GRAPHQL_URL, json=payload, headers=headers) as resp:
                if resp.status == 401:
                    raise AuthenticationError("Invalid or expired token")
                if resp.status != 200:
                    text = await resp.text()
                    raise APIError(f"HTTP {resp.status}: {text[:200]}")

                data = await resp.json()
                if "errors" in data:
                    raise APIError(f"GraphQL error: {data['errors']}")

                return data.get("data", {})
