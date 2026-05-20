"""Shared helpers for installer steps."""

from __future__ import annotations

import os
import secrets
import shlex
import subprocess
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm, Prompt

console = Console()


def section(title: str, body: str) -> None:
    console.print(Panel.fit(body, title=title, border_style="cyan"))


def prompt(label: str, *, default: str | None = None, password: bool = False) -> str:
    return Prompt.ask(label, default=default or None, password=password, console=console)


def confirm(label: str, *, default: bool = True) -> bool:
    return Confirm.ask(label, default=default, console=console)


def run(cmd: list[str], *, check: bool = True, env: dict | None = None) -> subprocess.CompletedProcess:
    """Run a shell command, capturing output."""
    return subprocess.run(
        cmd,
        check=check,
        capture_output=True,
        text=True,
        env={**os.environ, **(env or {})},
    )


def run_stream(cmd: list[str], *, env: dict | None = None) -> int:
    """Run a shell command, streaming output live to the console."""
    console.print(f"[dim]$ {' '.join(shlex.quote(c) for c in cmd)}[/dim]")
    return subprocess.call(cmd, env={**os.environ, **(env or {})})


def have_cmd(name: str) -> bool:
    from shutil import which
    return which(name) is not None


def random_password(length: int = 32) -> str:
    return secrets.token_urlsafe(length)


def load_env_dev_defaults(state: dict, repo_root: Path) -> None:
    """If `.env.dev` (or `.env`) exists in the repo root, pre-fill state with any matching keys.

    Only sets state keys that are missing. Never overwrites.
    """
    for fname in (".env.dev", ".env"):
        path = repo_root / fname
        if not path.exists():
            continue
        for line in path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            if not v:
                continue
            # Match likely env var names to state keys
            mapping = {
                "DISCORD_TOKEN": "discord_token",
                "DISCORD_GUILD_ID": "discord_guild_id",
                "ANTHROPIC_API_KEY": "anthropic_api_key",
                "TAILSCALE_AUTHKEY": "tailscale_authkey",
                "GCP_PROJECT_ID": "gcp_project_id",
                "GCP_REGION": "gcp_region",
                "GCP_ZONE": "gcp_zone",
            }
            state_key = mapping.get(k)
            if state_key and state_key not in state:
                state[state_key] = v
        return
