"""`monarch-admin` extensions — thin Click wrappers over the SDK `auth` module."""

import asyncio
import json

import click

from . import auth
from .client import AuthenticationError, APIError


@click.command("acquire-session")
@click.option("--cdp", "cdp_url", default=None,
              help="Read from a Chrome you run with remote debugging at this DevTools "
                   "URL instead of your everyday Chrome.")
@click.option("--wait", default=300, show_default=True,
              help="Seconds to wait for a Monarch sign-in when one is needed.")
@click.option("--user", default=None,
              help="User whose profile receives the session. Defaults to the only "
                   "registered user (or 'local' when the local store is empty).")
@click.option("--print", "print_json", is_flag=True,
              help="Also write the session fields as JSON to stdout.")
def acquire_session(cdp_url, wait, user, print_json):
    """Import your Monarch browser session into a user profile.

    Reads the session from your everyday Chrome's cookie store (macOS asks
    once for Keychain access to "Chrome Safe Storage"). If Chrome already
    holds a Monarch session the API accepts, it is stored with no prompt;
    otherwise the Monarch sign-in page opens in Chrome and the command waits
    for you to sign in. The session is stored in the profile of a user on
    the target set by `connect` (local store or remote deployment).
    Credential values are not printed unless --print is given.
    """
    # Private framework helper: resolves the local-or-remote store chosen
    # by `monarch-admin connect`, the same one `users` commands use.
    from mcp_app.cli import _get_auth_store, _load_setup

    local = _load_setup("monarch").get("mode") == "local"
    store = _get_auth_store("monarch")

    async def _run():
        try:
            target = await auth.resolve_user(
                store, user, default_user=auth.LOCAL_USER if local else None
            )
            session = await auth.acquire_session(
                cdp_url, wait=wait, on_status=lambda m: click.echo(m, err=True)
            )
            await auth.store_session(store, session, target)
            return session, target
        finally:
            if hasattr(store, "aclose"):
                await store.aclose()

    try:
        session, target = asyncio.run(_run())
    except (auth.BrowserSessionError, auth.SessionTargetError,
            AuthenticationError, APIError) as exc:
        raise click.ClickException(str(exc))

    where = "local store" if local else "remote deployment"
    click.echo(f"Session verified and stored for user '{target}' ({where}).", err=print_json)
    click.echo(f"Session expires: {session.get('session_expires') or 'unknown'}", err=print_json)
    if print_json:
        click.echo(json.dumps(session, indent=2))
