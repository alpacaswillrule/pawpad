"""Deploy step — terraform → SSH → install-vm.sh."""

from __future__ import annotations

import json
import os
import socket
import subprocess
import time
from pathlib import Path

from installer._helpers import console, have_cmd, section, sh, sh_stream

REPO_ROOT = Path(__file__).resolve().parents[2]
TERRAFORM_DIR = REPO_ROOT / "infra" / "terraform"
INSTALL_VM_SH = REPO_ROOT / "scripts" / "install-vm.sh"


def run(state: dict) -> None:
    for cmd in ("terraform", "ssh", "scp"):
        if not have_cmd(cmd):
            raise RuntimeError(f"{cmd} not on PATH")

    _write_tfvars(state)
    _terraform_apply(state)
    outputs = _terraform_outputs()
    state["vm_external_ip"] = outputs["external_ip"]["value"]
    state["vm_internal_ip"] = outputs["internal_ip"]["value"]
    state["vm_name"] = outputs["instance_name"]["value"]
    state["vm_tailnet_hostname"] = outputs["tailnet_hostname"]["value"]
    state["ssh_user"] = outputs["ssh_user"]["value"]

    _wait_for_ssh(state)
    _run_install_vm(state)


# ---------------------------------------------------------------------------


def _write_tfvars(state: dict) -> None:
    tfvars = {
        "gcp_project_id": state["gcp_project_id"],
        "gcp_region": state["gcp_region"],
        "gcp_zone": state["gcp_zone"],
        "machine_type": state["machine_type"],
        "disk_size_gb": state["disk_size_gb"],
        "disk_type": state["disk_type"],
        "tailscale_authkey": state["tailscale_authkey"],
        "ssh_user": "pawpad",
        "ssh_pub_key": state["ssh_pub_key"],
    }
    path = TERRAFORM_DIR / "terraform.tfvars.json"
    path.write_text(json.dumps(tfvars, indent=2))
    os.chmod(path, 0o600)


def _terraform_apply(state: dict) -> None:
    section("terraform apply", "Provisioning VM. This takes ~3-5 minutes.")
    env = {}
    if not state.get("gcp_uses_adc"):
        env["GOOGLE_APPLICATION_CREDENTIALS"] = state["gcp_creds_path"]

    rc = sh_stream(["terraform", "-chdir=" + str(TERRAFORM_DIR), "init", "-upgrade"], env=env)
    if rc != 0:
        raise RuntimeError("terraform init failed")
    rc = sh_stream(
        ["terraform", "-chdir=" + str(TERRAFORM_DIR), "apply", "-auto-approve"],
        env=env,
    )
    if rc != 0:
        raise RuntimeError("terraform apply failed")


def _terraform_outputs() -> dict:
    res = sh(["terraform", "-chdir=" + str(TERRAFORM_DIR), "output", "-json"])
    return json.loads(res.stdout)


def _wait_for_ssh(state: dict) -> None:
    section("waiting for SSH", "")
    ip = state["vm_external_ip"]
    deadline = time.time() + 300
    last_err = ""
    while time.time() < deadline:
        try:
            with socket.create_connection((ip, 22), timeout=5):
                pass
            # also confirm sshd accepts our key
            res = sh(
                [
                    "ssh",
                    "-i", state["ssh_key_path"],
                    "-o", "StrictHostKeyChecking=no",
                    "-o", "UserKnownHostsFile=/dev/null",
                    "-o", "ConnectTimeout=10",
                    f"{state['ssh_user']}@{ip}",
                    "true",
                ],
                check=False,
            )
            if res.returncode == 0:
                console.log("SSH ready")
                return
            last_err = res.stderr.strip()
        except OSError as exc:
            last_err = str(exc)
        time.sleep(10)
        console.log(f"  still waiting… ({last_err[:80]})")
    raise RuntimeError(f"SSH never came up: {last_err}")


def _run_install_vm(state: dict) -> None:
    section("running install-vm.sh on the VM", "")
    secrets_json = json.dumps({
        "DISCORD_TOKEN": state["discord_token"],
        "DISCORD_GUILD_ID": state["discord_guild_id"],
        "ANTHROPIC_API_KEY": state["anthropic_api_key"],
        "COUCHDB_USER": state.get("couchdb_user", "pawpad"),
        "COUCHDB_PASSWORD": state["couchdb_password"],
        "LIVESYNC_PASSPHRASE": state["livesync_passphrase"],
        "PAWPAD_GH_OWNER": state.get("github_user", "alpacaswillrule"),
        "PAWPAD_DEFAULT_DAILY_CAP_USD": str(state.get("default_daily_cap_usd", 500)),
    })

    # SCP install-vm.sh over (the startup script clones the repo but the local
    # one may have edits we want to use). Then run it with the secrets piped in.
    scp_cmd = [
        "scp",
        "-i", state["ssh_key_path"],
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        str(INSTALL_VM_SH),
        f"{state['ssh_user']}@{state['vm_external_ip']}:/tmp/install-vm.sh",
    ]
    if sh_stream(scp_cmd) != 0:
        raise RuntimeError("scp install-vm.sh failed")

    ssh_target = f"{state['ssh_user']}@{state['vm_external_ip']}"
    ssh_cmd = [
        "ssh",
        "-i", state["ssh_key_path"],
        "-o", "StrictHostKeyChecking=no",
        "-o", "UserKnownHostsFile=/dev/null",
        ssh_target,
        "chmod +x /tmp/install-vm.sh && sudo /tmp/install-vm.sh",
    ]
    console.print(f"[dim]$ {' '.join(ssh_cmd)} <<<secrets[/dim]")
    proc = subprocess.Popen(ssh_cmd, stdin=subprocess.PIPE, stdout=None, stderr=None)
    proc.communicate(input=secrets_json.encode())
    if proc.returncode != 0:
        raise RuntimeError(f"install-vm.sh failed (rc={proc.returncode})")
