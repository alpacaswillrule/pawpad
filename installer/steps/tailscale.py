"""Tailscale auth key collection.

Operator generates a reusable auth key at
https://login.tailscale.com/admin/settings/keys, pastes it here.

Optionally we can verify the key by hitting Tailscale's API.

Writes:
  state["tailscale_authkey"]   (sensitive — never written to logs)
  state["tailscale_tags"]      list of tags to apply to the VM, default ["tag:pawpad"]
"""

from __future__ import annotations

# TODO:
#   - present link with copyable instructions:
#       1. https://login.tailscale.com/admin/settings/keys
#       2. Generate auth key, check "Reusable" and "Ephemeral" (or one-time
#          if operator prefers strict)
#       3. paste here
#   - validate format (tskey-auth-...)
#   - optional: hit https://api.tailscale.com/api/v2/whois to validate
#   - optional: warn operator to add `tag:pawpad` to their tailnet ACL


def run(state: dict) -> None:
    raise NotImplementedError("TODO: Tailscale auth key collection")
