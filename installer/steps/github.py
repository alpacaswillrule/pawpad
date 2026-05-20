"""GitHub auth verification + deploy keypair generation."""

from __future__ import annotations

import os
from pathlib import Path

from installer._helpers import have_cmd, section, sh


def run(state: dict) -> None:
    if not have_cmd("gh"):
        raise RuntimeError(
            "gh CLI not installed. Install via `brew install gh` and re-run."
        )

    res = sh(["gh", "auth", "status"], check=False)
    if res.returncode != 0:
        raise RuntimeError(
            "gh is not authenticated. Run:\n"
            "  gh auth login -s repo,admin:public_key\n"
            "and re-run the installer."
        )

    out = (res.stdout or "") + (res.stderr or "")
    if "alpacaswillrule" not in out:
        section(
            "warning",
            f"gh appears authed but not as `alpacaswillrule`:\n{out[:400]}\n\n"
            "Continuing anyway — change PAWPAD_GH_OWNER if needed.",
        )

    state["github_user"] = "alpacaswillrule"

    # --- generate deploy keypair for the VM's initial SSH login --------------
    key_path = Path("~/.pawpad/vm_ssh_key").expanduser()
    pub_path = Path(str(key_path) + ".pub")
    if not key_path.exists():
        key_path.parent.mkdir(parents=True, exist_ok=True)
        sh(
            ["ssh-keygen", "-t", "ed25519", "-N", "", "-f", str(key_path), "-C", "pawpad-vm-deploy"],
        )
        os.chmod(key_path, 0o600)

    state["ssh_key_path"] = str(key_path)
    state["ssh_pub_key"] = pub_path.read_text().strip()

    # --- pull a gh token to ship to the VM so the bot can `gh repo create` ---
    # gh CLI on the VM needs auth to create private repos per channel. Easiest
    # path: copy the operator's existing token from `gh auth token`.
    res = sh(["gh", "auth", "token"], check=False)
    if res.returncode != 0 or not res.stdout.strip():
        section(
            "warning",
            "Couldn't read your gh auth token via `gh auth token`. The bot won't be\n"
            "able to create per-channel repos. You can SSH in after install and run\n"
            "`gh auth login` manually.",
        )
    else:
        state["gh_token"] = res.stdout.strip()

    section(
        "GitHub + SSH",
        f"gh authed. Deploy keypair at [bold]{key_path}[/bold] (used for initial VM SSH only).\n"
        f"VM will reuse your gh token for per-channel `gh repo create`.",
    )
