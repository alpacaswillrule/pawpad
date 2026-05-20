"""Finalize — print summary, save runtime config locally.

Outputs:
  - Tailscale IP + hostname (operator uses these to SSH and to access Quartz)
  - Quartz URL (e.g. http://pawpad-vm:8080 over tailnet)
  - Discord guild link reminder
  - "Create your first channel under the 'projects' category to start"

Writes:
  ~/.pawpad/runtime.json   (operator-side runtime metadata for later `pawpad ssh`,
                            `pawpad logs`, etc. — to be implemented later)
"""

from __future__ import annotations

# TODO:
#   - print the rich summary panel
#   - write ~/.pawpad/runtime.json
#   - point operator at docs/runbook.md


def run(state: dict) -> None:
    raise NotImplementedError("TODO: finalize step")
