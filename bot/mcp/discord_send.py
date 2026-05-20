"""In-process MCP server exposing `discord_send(text)`.

Registered per-channel-session. The Agent SDK auto-forwards the final
text of each turn to Discord, so `discord_send` is for mid-turn status
updates the agent wants to surface ("I'm running the test suite, will
update when it finishes").

Tool name as the agent sees it: `mcp__pawpad__discord_send`.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

import discord
from claude_agent_sdk import create_sdk_mcp_server, tool

from bot.output import post_chunked

logger = logging.getLogger("pawpad.mcp.discord_send")


def make_server(channel: discord.abc.Messageable):
    """Build a per-session MCP server bound to one Discord channel.

    `discord_send` is fire-and-forget: it schedules the actual post as a
    background task and returns immediately. This is important — if the
    tool awaited the Discord HTTP roundtrip, the SDK subprocess would be
    blocked waiting on `tool_result`, which can stall the entire turn
    (we observed 10-minute delays in practice).

    The agent gets back "queued" and continues; the post lands asynchronously.
    """

    @tool(
        "discord_send",
        "Post an intermediate status update to the Discord channel. "
        "Plain assistant text now streams to Discord automatically, so prefer "
        "writing your response directly. Use this tool only when you want a "
        "discrete status ping that's separate from your main reply (e.g. "
        "'starting tests…', 'gradle build kicked off, watching').",
        {"text": str},
    )
    async def discord_send(args: dict[str, Any]) -> dict[str, Any]:
        text = args.get("text", "")
        if not text:
            return {"content": [{"type": "text", "text": "empty text, nothing sent"}]}

        async def _post() -> None:
            try:
                await post_chunked(channel, text)
            except discord.HTTPException as exc:
                logger.warning("discord_send (bg) failed: %s", exc)

        # Fire and forget so the SDK doesn't block waiting for HTTP.
        asyncio.create_task(_post())
        return {"content": [{"type": "text", "text": "queued"}]}

    return create_sdk_mcp_server(
        name="pawpad",
        version="1.0.0",
        tools=[discord_send],
    )
