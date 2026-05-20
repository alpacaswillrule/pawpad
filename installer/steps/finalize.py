"""Finalize — print summary, save runtime config locally."""

from __future__ import annotations

import json
from pathlib import Path

from installer._helpers import console, section

RUNTIME_PATH = Path("~/.pawpad/runtime.json").expanduser()


def run(state: dict) -> None:
    RUNTIME_PATH.parent.mkdir(parents=True, exist_ok=True)
    runtime = {
        "gcp_project_id": state["gcp_project_id"],
        "gcp_region": state["gcp_region"],
        "gcp_zone": state["gcp_zone"],
        "vm_name": state.get("vm_name", "pawpad-vm"),
        "vm_tailnet_hostname": state.get("vm_tailnet_hostname", "pawpad-vm"),
        "vm_external_ip": state.get("vm_external_ip"),
        "vm_internal_ip": state.get("vm_internal_ip"),
        "ssh_user": state.get("ssh_user", "pawpad"),
        "ssh_key_path": state["ssh_key_path"],
        "disk_name": state.get("vm_name", "pawpad-vm") + "-data",
    }
    RUNTIME_PATH.write_text(json.dumps(runtime, indent=2))

    section(
        "done!",
        f"VM: [bold]{runtime['vm_tailnet_hostname']}[/bold] (tailnet)\n\n"
        f"  SSH:        tailscale ssh {runtime['vm_tailnet_hostname']}\n"
        f"  Quartz:     http://{runtime['vm_tailnet_hostname']}:8080\n"
        f"  LiveSync:   https://{runtime['vm_tailnet_hostname']}:5984\n"
        f"               user: [bold]{state.get('couchdb_user', 'pawpad')}[/bold]\n"
        f"               pass: [bold]{state['couchdb_password']}[/bold]\n"
        f"               e2e:  [bold]{state['livesync_passphrase']}[/bold]\n\n"
        "Next:\n"
        "  • In your Discord server, create a channel under the `projects` category.\n"
        "  • The bot will scaffold a workspace and a private GitHub repo.\n"
        "  • Watch [bold]#jojo-audit[/bold] for activity.\n\n"
        "Runbook: docs/runbook.md\n",
    )
    console.print(f"[dim]runtime saved to {RUNTIME_PATH}[/dim]")
