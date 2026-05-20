"""Tailscale auth key collection."""

from __future__ import annotations

from installer._helpers import prompt, section


def run(state: dict) -> None:
    if state.get("tailscale_authkey", "").startswith("tskey-auth-"):
        section("Tailscale", "Auth key already loaded from .env.dev. Skipping.")
        return

    section(
        "Tailscale auth key",
        "1. Open: [link]https://login.tailscale.com/admin/settings/keys[/link]\n"
        "2. Add tag `tag:pawpad` to your ACL at\n"
        "   [link]https://login.tailscale.com/admin/acls/file[/link] (under tagOwners)\n"
        "3. Generate auth key: check Reusable, Pre-approved, tag: tag:pawpad\n"
        "4. Copy the [bold]tskey-auth-...[/bold] string and paste below.\n",
    )
    key = prompt("Tailscale auth key (tskey-auth-...)", password=True)
    if not key.startswith("tskey-"):
        raise RuntimeError("auth key should start with 'tskey-'")
    state["tailscale_authkey"] = key
