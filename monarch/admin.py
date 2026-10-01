"""`monarch-admin` extensions — thin Click wrappers over the SDK `auth` module."""

import asyncio
import json

import click

from . import auth, settings
from .client import AuthenticationError, APIError


@click.command("acquire-session")
@click.option("--cdp", "cdp_url", default=None,
              help="Use only this DevTools endpoint (no cookie-store fallback). "
                   "Without it, the endpoint set by `cdp-url` is tried first.")
@click.option("--wait", default=300, show_default=True,
              help="Seconds to wait for a Monarch sign-in when one is needed.")
@click.option("--user", default=None,
              help="User whose profile receives the session. Defaults to the only "
                   "registered user (or 'local' when the local store is empty).")
@click.option("--stdin", "from_stdin", is_flag=True,
              help="Import a session supplied by hand instead of reading a browser: "
                   "JSON on stdin (as written by --print), or hidden prompts when "
                   "stdin is a terminal.")
@click.option("--print", "print_json", is_flag=True,
              help="Also write the session fields as JSON to stdout.")
def acquire_session(cdp_url, wait, user, from_stdin, print_json):
    """Import your Monarch browser session into a user profile.

    First reads the session from the Chrome with remote debugging enabled at
    the configured DevTools endpoint (see `cdp-url`; no Keychain prompt). Only
    if no endpoint answers, or its browser holds no live Monarch session, does
    it fall back to the everyday Chrome's cookie store, which needs macOS
    Keychain access to "Chrome Safe Storage". A session counts as live only if
    the Monarch API accepts it. If no source has one, the Monarch sign-in page
    opens and the command waits for you to sign in. The session is stored in
    the profile of a user on the target set by `connect` (local store or
    remote deployment). Credential values are not printed unless --print is
    given.

    With --stdin, the session comes from you instead of a browser: pipe the
    JSON that --print wrote on another machine, or, at a terminal, enter the
    session_id, csrftoken and monarchDeviceUUID cookie values (hidden input,
    so they never reach shell history). Either way it is verified first.
    """
    if from_stdin and cdp_url:
        raise click.UsageError("--stdin and --cdp are mutually exclusive.")
    manual = _read_manual_session() if from_stdin else None

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
            if manual is not None:
                await auth.verify(manual)
                session, source = manual, auth.MANUAL_SOURCE
            else:
                session, source = await auth.acquire_session(
                    cdp_url, wait=wait, on_status=lambda m: click.echo(m, err=True)
                )
            await auth.store_session(store, session, target)
            return session, source, target
        finally:
            if hasattr(store, "aclose"):
                await store.aclose()

    try:
        session, source, target = asyncio.run(_run())
    except (auth.BrowserSessionError, auth.SessionTargetError,
            AuthenticationError, APIError) as exc:
        raise click.ClickException(str(exc))

    where = "local store" if local else "remote deployment"
    click.echo(f"Session read from {source}.", err=print_json)
    click.echo(f"Session verified and stored for user '{target}' ({where}).", err=print_json)
    click.echo(f"Session expires: {session.get('session_expires') or 'unknown'}", err=print_json)
    if print_json:
        click.echo(json.dumps(session, indent=2))


def _read_manual_session() -> dict:
    """Session values from stdin JSON, or hidden prompts at a terminal."""
    import sys
    try:
        if sys.stdin.isatty():
            data = {
                "session_id": click.prompt("session_id cookie", hide_input=True),
                "csrftoken": click.prompt("csrftoken cookie", hide_input=True),
                "monarchDeviceUUID": click.prompt(
                    "monarchDeviceUUID cookie (optional)", default="", show_default=False),
            }
        else:
            try:
                data = json.loads(sys.stdin.read())
            except json.JSONDecodeError as exc:
                raise click.ClickException(f"stdin is not valid JSON: {exc.msg}")
        return auth.session_from_input(data)
    except auth.BrowserSessionError as exc:
        raise click.ClickException(str(exc))


@click.command("cdp-url")
@click.argument("url", required=False)
@click.option("--reset", is_flag=True, help="Return to the default endpoint.")
def cdp_url(url, reset):
    """Show or set the DevTools endpoint `acquire-session` checks first.

    The endpoint belongs to a Chrome running with remote debugging enabled
    and signed in to Monarch. Default: http://127.0.0.1:9222.
    """
    try:
        if reset:
            value = settings.set_cdp_url(None)
        elif url:
            value = settings.set_cdp_url(url)
        else:
            value = settings.get_cdp_url()
    except settings.SettingsError as exc:
        raise click.ClickException(str(exc))
    click.echo(value + (" (default)" if settings.is_default_cdp_url() else ""))
