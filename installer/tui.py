"""pawpad installer — interactive TUI.

Walks the operator through credential gathering, then provisions the GCP VM
and runs the on-VM install. Built on `rich` and `textual`.

State is persisted to `installer/.state.json` so a re-run can resume after a
failure.

Steps live in `installer.steps.*` — each module exports a `run(state) -> None`
function. tui.py is a thin sequencer.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from rich.console import Console

from installer.steps import (
    anthropic,
    deploy,
    discord,
    finalize,
    gcp_auth,
    gcp_project,
    github,
    obsidian,
    tailscale,
    vm_specs,
    welcome,
)

STATE_FILE = Path(__file__).parent / ".state.json"
console = Console()


def load_state() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {}


def save_state(state: dict) -> None:
    # Write through a temp file with 0600 perms before rename, so the secret-
    # bearing file is never world-readable even momentarily.
    tmp = STATE_FILE.with_suffix(".tmp")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp, STATE_FILE)


STEPS = [
    ("welcome", welcome.run),
    ("gcp_auth", gcp_auth.run),
    ("gcp_project", gcp_project.run),
    ("vm_specs", vm_specs.run),
    ("tailscale", tailscale.run),
    ("github", github.run),
    ("discord", discord.run),
    ("anthropic", anthropic.run),
    ("obsidian", obsidian.run),
    ("deploy", deploy.run),
    ("finalize", finalize.run),
]


def main() -> int:
    state = load_state()
    try:
        for name, fn in STEPS:
            if state.get(f"_done_{name}"):
                console.log(f"[dim]skipping {name} (already done)[/dim]")
                continue
            console.rule(f"[bold]{name}[/bold]")
            fn(state)
            state[f"_done_{name}"] = True
            save_state(state)
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted. Re-run ./install.sh to resume.[/yellow]")
        return 130
    except Exception as exc:  # noqa: BLE001
        console.print_exception()
        console.print(f"\n[red]Step failed: {exc}[/red]")
        console.print("[dim]State saved. Fix the issue and re-run to resume.[/dim]")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
