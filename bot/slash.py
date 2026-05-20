"""Slash command registration.

  /budget <amount>             set daily $ cap
  /status                       channel agent state + queue + today's spend
  /spend                        per-channel + global breakdown for day & week
  /pause                        park this channel's agent
  /resume                       unpark
  /archive                      archive workspace + Obsidian dir
  /claude-instructions <text>   append to this channel's CLAUDE.md
                                (or VM-wide if `text` starts with `global `)
"""

from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from discord import app_commands

from bot.sessions import slugify

if TYPE_CHECKING:
    from bot.main import PawpadBot

logger = logging.getLogger("pawpad.slash")

VM_WIDE_CLAUDE_MD = Path("/opt/pawpad/claude/CLAUDE.md")


def register_slash_commands(tree: app_commands.CommandTree, bot: "PawpadBot") -> None:
    @tree.command(name="budget", description="Set the daily Anthropic spend cap in USD.")
    @app_commands.describe(amount="Daily $ cap (>0)")
    async def budget_cmd(interaction: discord.Interaction, amount: float) -> None:
        if amount <= 0:
            await interaction.response.send_message("amount must be > 0", ephemeral=True)
            return
        prev = bot.budget.daily_cap()
        bot.budget.set_daily_cap(amount)
        await interaction.response.send_message(
            f"daily cap: ${prev:.2f} → **${amount:.2f}** (spent today: ${bot.budget.spent_today():.2f})"
        )

    @tree.command(name="status", description="Show this channel's agent state.")
    async def status_cmd(interaction: discord.Interaction) -> None:
        session = bot.sessions.sessions.get(interaction.channel_id)
        if session is None:
            await interaction.response.send_message(
                "no agent session bound to this channel (channel isn't under `projects`?)",
                ephemeral=True,
            )
            return
        spent_today = bot.budget.spent_by_channel_today().get(interaction.channel_id, 0.0)
        idle_for = max(0.0, time.time() - session.latest_activity()) if session.latest_activity() else None
        idle_str = f"{idle_for / 60:.0f}m" if idle_for is not None else "—"
        await interaction.response.send_message(
            "\n".join(
                [
                    f"**#{session.channel_name}** · state: `{session.state}`",
                    f"  pending msgs: {len(session.pending)} · idle for: {idle_str}",
                    f"  spent today: ${spent_today:.2f} (channel) · ${bot.budget.spent_today():.2f} (global) / ${bot.budget.daily_cap():.2f} cap",
                    f"  active slots: {len(bot.sessions.holders)} / {bot.sessions.soft_cap}",
                    f"  session_id: `{session.session_id or '(new)'}`",
                ]
            ),
            ephemeral=False,
        )

    @tree.command(name="spend", description="Per-channel + global spend (today & this week).")
    async def spend_cmd(interaction: discord.Interaction) -> None:
        today = bot.budget.spent_by_channel_today()
        week = bot.budget.spent_by_channel_week()
        if not today and not week:
            await interaction.response.send_message("no spend yet", ephemeral=True)
            return

        guild = interaction.guild
        def _name(cid: int) -> str:
            ch = guild.get_channel(cid) if guild else None
            return f"#{ch.name}" if ch else f"#{cid}"

        all_cids = sorted(set(today) | set(week), key=lambda c: -today.get(c, 0))
        rows = ["```"]
        rows.append(f"{'channel':<24} {'today':>10}  {'week':>10}")
        for cid in all_cids:
            rows.append(
                f"{_name(cid)[:24]:<24} ${today.get(cid, 0):>8.2f}  ${week.get(cid, 0):>8.2f}"
            )
        rows.append("-" * 50)
        rows.append(
            f"{'TOTAL':<24} ${sum(today.values()):>8.2f}  ${sum(week.values()):>8.2f}"
        )
        rows.append("```")
        rows.append(
            f"cap: ${bot.budget.daily_cap():.2f}/day · remaining today: ${bot.budget.remaining_today():.2f}"
        )
        await interaction.response.send_message("\n".join(rows))

    @tree.command(name="pause", description="Pause this channel's agent.")
    async def pause_cmd(interaction: discord.Interaction) -> None:
        ok = await bot.sessions.pause(interaction.channel_id)
        if ok:
            await interaction.response.send_message("paused. messages will be ignored until `/resume`.")
        else:
            await interaction.response.send_message("no session bound to this channel.", ephemeral=True)

    @tree.command(name="resume", description="Resume this channel's agent.")
    async def resume_cmd(interaction: discord.Interaction) -> None:
        ok = await bot.sessions.resume(interaction.channel_id)
        if ok:
            await interaction.response.send_message("resumed.")
        else:
            await interaction.response.send_message(
                "session isn't paused (state may already be active or channel isn't tracked).",
                ephemeral=True,
            )

    @tree.command(
        name="archive",
        description="Archive this channel's workspace + Obsidian dir (keeps the Discord channel).",
    )
    async def archive_cmd(interaction: discord.Interaction) -> None:
        cid = interaction.channel_id
        if cid is None or cid not in bot.sessions.sessions:
            await interaction.response.send_message(
                "no session bound to this channel.", ephemeral=True
            )
            return
        await interaction.response.send_message("archiving…")
        await bot.sessions.archive_channel(cid, source="manual")
        await interaction.followup.send("archived. session removed; channel preserved.")

    @tree.command(
        name="claude-instructions",
        description="Append instructions to this channel's CLAUDE.md (prefix with `global ` for VM-wide).",
    )
    @app_commands.describe(text="Instruction text. Prefix with 'global ' to update VM-wide CLAUDE.md.")
    async def claude_instructions_cmd(
        interaction: discord.Interaction, text: str
    ) -> None:
        if not text.strip():
            await interaction.response.send_message("text required", ephemeral=True)
            return

        if text.startswith("global "):
            body = text[len("global ") :].strip()
            if not body:
                await interaction.response.send_message("text required after `global `", ephemeral=True)
                return
            target = VM_WIDE_CLAUDE_MD
            scope = "VM-wide"
        else:
            session = bot.sessions.sessions.get(interaction.channel_id)
            if session is None:
                await interaction.response.send_message(
                    "no session bound to this channel.", ephemeral=True
                )
                return
            body = text.strip()
            target = session.workspace / "CLAUDE.md"
            scope = f"#{session.channel_name}"

        _append_instruction(target, body, author=interaction.user.display_name)
        await interaction.response.send_message(
            f"appended to {scope} CLAUDE.md ({target}). agent picks it up on the next turn."
        )


def _append_instruction(path: Path, body: str, *, author: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
    block = f"\n\n## {stamp} — added by {author} via /claude-instructions\n\n{body}\n"
    if path.exists():
        path.write_text(path.read_text() + block)
    else:
        path.write_text(f"# Project-specific instructions{block}")
