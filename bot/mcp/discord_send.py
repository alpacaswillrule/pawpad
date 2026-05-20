"""In-process MCP server exposing `discord_send(text)`.

Registered per-channel-session. The Agent SDK auto-forwards the final
text of each turn to Discord, so `discord_send` is for mid-turn status
updates the agent wants to surface ("I'm running the test suite, will
update when it finishes").

Tool name as the agent sees it: `mcp__pawpad__discord_send`.
"""

from __future__ import annotations

import logging
from typing import Any

import discord
from claude_agent_sdk import create_sdk_mcp_server, tool

from bot.output import post_chunked

logger = logging.getLogger("pawpad.mcp.discord_send")


def make_server(channel: discord.abc.Messageable):
    """Build a per-session MCP server bound to one Discord channel."""

    @tool(
        "discord_send",
        "Post an intermediate status update to the Discord channel. "
        "Use sparingly — final turn text is auto-posted. "
        "Use this when you want to tell the user something during a long task "
        "(e.g. 'starting the test suite, will report results when done').",
        {"text": str},
    )
    async def discord_send(args: dict[str, Any]) -> dict[str, Any]:
        text = args.get("text", "")
        if not text:
            return {"content": [{"type": "text", "text": "empty text, nothing sent"}]}
        try:
            await post_chunked(channel, text)
        except discord.HTTPException as exc:
            logger.warning("discord_send failed: %s", exc)
            return {
                "content": [{"type": "text", "text": f"send failed: {exc}"}],
                "isError": True,
            }
        return {"content": [{"type": "text", "text": "sent"}]}

    return create_sdk_mcp_server(
        name="pawpad",
        version="1.0.0",
        tools=[discord_send],
    )
