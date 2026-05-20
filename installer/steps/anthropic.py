"""Anthropic API key collection + validation.

Operator pastes their API key from https://console.anthropic.com/settings/keys.
We make a cheap models-list call to verify the key works.

Writes:
  state["anthropic_api_key"]  (sensitive)
"""

from __future__ import annotations

# TODO:
#   - link to https://console.anthropic.com/settings/keys
#   - prompt for paste (hide input)
#   - validate via httpx GET https://api.anthropic.com/v1/models
#     headers: x-api-key, anthropic-version
#   - optional: ask operator to set a workspace spend cap in console (we'll
#     enforce daily caps in-bot too, but a hard ceiling at the console is safer)


def run(state: dict) -> None:
    raise NotImplementedError("TODO: Anthropic API key validation")
