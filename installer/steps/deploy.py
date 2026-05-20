"""Deploy step — terraform up, SSH in, install on VM.

This is the heavy step. With a live progress display:
  1. terraform init && terraform apply (creates VM, disk, firewall, static IP)
  2. wait for SSH on the VM
  3. install tailscale, bring up VM into tailnet using authkey
  4. scp the repo (or git-clone the public mirror)
  5. ssh into VM, run scripts/install-vm.sh which installs:
       - claude-code CLI
       - node, python, gh, docker
       - the pawpad bot package (pip install -e .)
       - CouchDB (livesync)
       - quartz (if enabled)
       - systemd units
  6. start systemd units
  7. smoke test: bot connects to Discord, creates #jojo-audit

Writes:
  state["vm_external_ip"]      (only used during deploy; afterwards we use tailnet)
  state["vm_tailscale_ip"]
  state["vm_tailscale_name"]
"""

from __future__ import annotations

# TODO: heavy. Implementation order:
#   1. render terraform tfvars from state
#   2. terraform init + apply with live output
#   3. poll SSH (use the deploy SSH key terraform created)
#   4. run install-vm.sh via ssh
#   5. systemctl start jojo-bot livesync quartz
#   6. wait for bot to post in #jojo-audit (proves it's alive)


def run(state: dict) -> None:
    raise NotImplementedError("TODO: deploy step")
