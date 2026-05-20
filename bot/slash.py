"""Slash command registration.

v1 commands:
  /budget <amount>             set daily $ cap
  /status                       channel agent state + queue + today's spend
  /spend                        per-channel + global breakdown for day/week
  /pause                        park this channel's agent
  /resume                       unpark
  /archive                      archive workspace + Obsidian dir; stop agent; keep Discord channel
  /claude-instructions <text>   append to this channel's CLAUDE.md
  /claude-instructions global <text>   append to VM-wide CLAUDE.md (admin-only)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from bot.main import PawpadBot


def register_slash_commands(tree: app_commands.CommandTree, bot: "PawpadBot") -> None:
    @tree.command(name="budget", description="Set the daily Anthropic spend cap in USD.")
    @app_commands.describe(amount="Daily $ cap (default 500)")
    async def budget(interaction: discord.Interaction, amount: float) -> None:
        # TODO: validate amount > 0; update bot.budget.set_daily_cap(amount); reply
        raise NotImplementedError

    @tree.command(name="status", description="Show this channel's agent state.")
    async def status(interaction: discord.Interaction) -> None:
        # TODO: lookup session; report state/queue/today's spend
        raise NotImplementedError

    @tree.command(name="spend", description="Per-channel + global spend breakdown.")
    async def spend(interaction: discord.Interaction) -> None:
        # TODO: bot.budget.report_breakdown(today, week)
        raise NotImplementedError

    @tree.command(name="pause", description="Pause this channel's agent.")
    async def pause(interaction: discord.Interaction) -> None:
        # TODO: bot.sessions.pause(channel.id)
        raise NotImplementedError

    @tree.command(name="resume", description="Resume this channel's agent.")
    async def resume(interaction: discord.Interaction) -> None:
        # TODO: bot.sessions.resume(channel.id)
        raise NotImplementedError

    @tree.command(name="archive", description="Archive workspace + Obsidian dir; keep channel.")
    async def archive(interaction: discord.Interaction) -> None:
        # TODO: bot.sessions.archive_channel(channel.id)
        raise NotImplementedError

    @tree.command(
        name="claude-instructions",
        description="Append instructions to this channel's CLAUDE.md (use 'global' as first arg for VM-wide).",
    )
    @app_commands.describe(text="Instruction text. Prefix with 'global ' to update VM-wide CLAUDE.md.")
    async def claude_instructions(interaction: discord.Interaction, text: str) -> None:
        # TODO:
        #   - if text starts with "global ": append to VM-wide CLAUDE.md (admin gate by guild owner)
        #   - else: append to ~/projects/{slug}/CLAUDE.md for this channel
        #   - reply with confirmation
        raise NotImplementedError
