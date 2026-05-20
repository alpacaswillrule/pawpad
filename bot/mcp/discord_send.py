"""In-process MCP server exposing one tool: discord_send(text).

The Agent SDK supports custom MCP servers. We register this one with each
ChannelSession so the agent can push mid-turn status updates to Discord
without waiting for turn-end. Default-final-text routing still happens
automatically — this is purely for intermediate progress messages.

Exposed tool:
  discord_send(text: str) -> {"ok": True}
    Sends `text` to the Discord channel bound to the current session.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import discord


def make_server(channel: "discord.TextChannel"):
    """Build an in-process MCP server bound to a specific channel."""
    # TODO:
    #   - import from claude_agent_sdk: create_sdk_mcp_server, tool
    #   - define `discord_send(text)` as @tool
    #     -> use channel.send (chunked via bot.output.split_for_discord)
    #   - return the assembled server
    raise NotImplementedError
