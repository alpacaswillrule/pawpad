"""GitHub auth verification.

Verifies that `gh` CLI is authed on this machine, that the active account
matches the expected owner (alpacaswillrule by default), and that the active
auth has `repo` scope so the bot can create private repos.

The VM will get a separate SSH deploy key generated during the deploy step.

Writes:
  state["github_user"]
"""

from __future__ import annotations

# TODO:
#   - run `gh auth status --hostname github.com` and parse
#   - confirm the active account
#   - check `repo` scope
#   - if not authed: instruct operator to run `gh auth login -s repo,admin:public_key`
#   - then re-run installer (state is persisted, will resume)


def run(state: dict) -> None:
    raise NotImplementedError("TODO: GitHub auth verification")
