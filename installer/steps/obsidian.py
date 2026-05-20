"""Obsidian LiveSync passphrase + CouchDB credentials."""

from __future__ import annotations

from installer._helpers import random_password, section


def run(state: dict) -> None:
    if state.get("livesync_passphrase") and state.get("couchdb_password"):
        section("Obsidian LiveSync", "credentials already set; skipping.")
        return

    state["couchdb_user"] = state.get("couchdb_user") or "pawpad"
    state["couchdb_password"] = state.get("couchdb_password") or random_password(24)
    state["livesync_passphrase"] = state.get("livesync_passphrase") or random_password(32)

    section(
        "Obsidian LiveSync",
        "Generated CouchDB credentials + E2E passphrase.\n"
        "Save these — you'll paste them into the Obsidian Self-Hosted LiveSync\n"
        "plugin on every device that will sync the vault.\n\n"
        f"  CouchDB user:  [bold]{state['couchdb_user']}[/bold]\n"
        f"  CouchDB pass:  [bold]{state['couchdb_password']}[/bold]\n"
        f"  E2E passphrase: [bold]{state['livesync_passphrase']}[/bold]\n",
    )
