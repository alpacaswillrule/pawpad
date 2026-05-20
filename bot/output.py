"""Discord output formatting.

Responsibilities:
  - Stream the agent's final natural-language text with a typing indicator
  - Chunk at the 2000-char Discord limit (split on word/line boundaries)
  - Code blocks > 1800 chars: write to a temp file, attach instead of inlining
  - Append a footer: `• N tools · T seconds · $C`
  - Provide a `discord_send` async helper used by the in-process MCP tool for
    mid-turn status updates
"""

from __future__ import annotations

from dataclasses import dataclass

import discord

DISCORD_LIMIT = 2000
CODE_INLINE_LIMIT = 1800


@dataclass
class TurnFooter:
    tool_count: int
    elapsed_seconds: float
    usd: float

    def render(self) -> str:
        return f"• {self.tool_count} tools · {self.elapsed_seconds:.0f}s · ${self.usd:.2f}"


def split_for_discord(text: str, limit: int = DISCORD_LIMIT) -> list[str]:
    """Split text into chunks that fit in a single Discord message."""
    # TODO:
    #   - prefer line boundaries, fall back to word boundaries, fall back to hard cut
    #   - preserve fenced code blocks across splits (reopen ``` after split)
    raise NotImplementedError


async def post_turn(
    channel: discord.TextChannel,
    text: str,
    *,
    footer: TurnFooter,
    code_attachments: list[tuple[str, str]] | None = None,
) -> None:
    """Post a complete agent turn to a Discord channel.

    code_attachments: list of (filename, content) — anything too big for inlining.
    """
    # TODO:
    #   - send code attachments first as files
    #   - then post text chunks
    #   - last chunk appends `\n-# {footer.render()}` (Discord subtext syntax)
    raise NotImplementedError


async def stream_typing(channel: discord.TextChannel) -> None:
    """Hold a typing indicator on the channel until cancelled."""
    # TODO: async with channel.typing() loop until task is cancelled
    raise NotImplementedError
