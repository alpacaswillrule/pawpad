"""Non-interactive state preparation for unattended installs.

Reads .env.dev + gh auth + gcloud config, generates the SSH keypair and
LiveSync credentials in-process, writes a complete `installer/.state.json`
with every `_done_<step>` marker except deploy/finalize set. The TUI then
skips through directly to terraform apply.

Run: .venv/bin/python -m installer.prime
"""

from __future__ import annotations

import json
import os
import secrets
import subprocess
import sys
from pathlib import Path

from installer.tui import STATE_FILE
from installer._helpers import load_env_dev_defaults

REPO_ROOT = Path(__file__).resolve().parent.parent


def sh(cmd: list[str], check: bool = True) -> str:
    res = subprocess.run(cmd, capture_output=True, text=True, check=check)
    return res.stdout.strip()


def main() -> int:
    state: dict = {}
    if STATE_FILE.exists():
        state = json.loads(STATE_FILE.read_text())

    # 1. .env.dev / .env defaults
    load_env_dev_defaults(state, REPO_ROOT)

    # 2. gcp_auth — assume ADC
    state["gcp_uses_adc"] = True
    state.pop("gcp_creds_path", None)

    # 3. gcp_project — read from .env.dev (already loaded) + gcloud default
    if not state.get("gcp_project_id"):
        state["gcp_project_id"] = sh(["gcloud", "config", "get-value", "project"])
    state.setdefault("gcp_region", "us-central1")
    state.setdefault("gcp_zone", "us-central1-a")

    # 4. vm_specs — sensible defaults (tiered storage: hot SSD + cold HDD)
    state.setdefault("machine_type", "e2-standard-4")
    state.setdefault("disk_size_gb", 200)        # hot SSD
    state.setdefault("disk_type", "pd-balanced")
    state.setdefault("cold_disk_size_gb", 1000)  # cold HDD
    state.setdefault("cold_disk_type", "pd-standard")

    # 5. github — generate keypair + reuse gh token
    key_path = Path("~/.pawpad/vm_ssh_key").expanduser()
    if not key_path.exists():
        key_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key_path),
             "-C", "pawpad-vm-deploy"],
            check=True,
            capture_output=True,
        )
        os.chmod(key_path, 0o600)
    state["ssh_key_path"] = str(key_path)
    state["ssh_pub_key"] = (Path(str(key_path) + ".pub")).read_text().strip()
    state["github_user"] = "alpacaswillrule"
    try:
        state["gh_token"] = sh(["gh", "auth", "token"])
    except subprocess.CalledProcessError:
        print("warning: `gh auth token` failed; bot won't be able to create repos", file=sys.stderr)
        state["gh_token"] = ""

    # 6. obsidian — auto-generate
    state.setdefault("couchdb_user", "pawpad")
    state.setdefault("couchdb_password", secrets.token_urlsafe(24))
    state.setdefault("livesync_passphrase", secrets.token_urlsafe(32))

    # 7. mark every info step done
    for step in (
        "welcome", "gcp_auth", "gcp_project", "vm_specs",
        "tailscale", "github", "discord", "anthropic", "obsidian",
    ):
        state[f"_done_{step}"] = True

    # 8. write state.json with 0600
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(STATE_FILE, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)

    print(f"state primed at {STATE_FILE}")
    print("ready: deploy + finalize will run when you start the installer")
    return 0


if __name__ == "__main__":
    sys.exit(main())
