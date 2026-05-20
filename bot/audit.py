"""#jojo-audit channel poster.

Owns the audit channel: creates it on first run, posts daily spend summaries,
budget warnings, agent crashes, channel-create events, suspends/resumes (debug).
"""

from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING

import discord

from bot.output import post_chunked

if TYPE_CHECKING:
    from bot.main import PawpadBot

logger = logging.getLogger("pawpad.audit")

AUDIT_CHANNEL_NAME = "jojo-audit"


class Audit:
    def __init__(self, bot: "PawpadBot", verbose_suspends: bool = False) -> None:
        self.bot = bot
        self.verbose_suspends = verbose_suspends
        self._channel: discord.TextChannel | None = None

    async def ensure_channel(self, guild: discord.Guild) -> discord.TextChannel:
        for ch in guild.text_channels:
            if ch.name == AUDIT_CHANNEL_NAME:
                self._channel = ch
                logger.info("audit channel: #%s (%s)", ch.name, ch.id)
                return ch

        logger.info("creating #%s in guild %s", AUDIT_CHANNEL_NAME, guild.name)
        try:
            channel = await guild.create_text_channel(
                AUDIT_CHANNEL_NAME,
                topic="pawpad audit log — spend, crashes, channel events",
                reason="pawpad bot first-run setup",
            )
        except discord.Forbidden as exc:
            logger.error("Cannot create audit channel — missing Manage Channels: %s", exc)
            raise
        self._channel = channel
        return channel

    @property
    def channel(self) -> discord.TextChannel | None:
        return self._channel

    async def post(self, text: str) -> None:
        if self._channel is None:
            logger.warning("audit channel not ready, dropping: %s", text[:120])
            return
        try:
            await post_chunked(self._channel, text)
        except discord.HTTPException as exc:
            logger.warning("audit post failed: %s", exc)

    async def post_event(self, kind: str, body: str = "") -> None:
        prefix = {
            "info": "•",
            "warn": "⚠",
            "crash": "✗",
            "ok": "✓",
            "spend": "$",
            "channel": "#",
        }.get(kind, "•")
        text = f"`{prefix}` {body}" if body else f"`{prefix}`"
        await self.post(text)

    async def post_budget_warning(self, pct: float, spent: float, cap: float) -> None:
        await self.post_event(
            "warn",
            f"**budget {int(pct * 100)}%** — spent ${spent:.2f} of ${cap:.2f} cap today",
        )

    async def post_budget_hit(self, spent: float, cap: float) -> None:
        await self.post_event(
            "warn",
            f"**budget exceeded** — ${spent:.2f} >= ${cap:.2f}. All active sessions paused. "
            "Resumes at next VM midnight or after `/budget` raise.",
        )

    async def post_crash(self, channel_name: str, exc: BaseException) -> None:
        tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))
        if len(tb) > 1600:
            tb = tb[:1600] + "\n... (truncated)"
        await self.post(
            f"`✗` **crash in #{channel_name}**\n```\n{tb}\n```"
        )

    async def post_daily_summary(
        self,
        *,
        total_usd: float,
        per_channel: dict[str, float],
        cap: float,
    ) -> None:
        lines = [f"`$` **daily summary** — total ${total_usd:.2f} / cap ${cap:.2f}"]
        if per_channel:
            lines.append("```")
            for name, usd in sorted(per_channel.items(), key=lambda x: -x[1]):
                lines.append(f"  ${usd:>7.2f}  #{name}")
            lines.append("```")
        else:
            lines.append("(no activity)")
        await self.post("\n".join(lines))

    async def post_channel_created(
        self, channel_name: str, repo_url: str, workspace: str
    ) -> None:
        await self.post(
            f"`#` **#{channel_name}** initialized\n"
            f"  repo: <{repo_url}>\n"
            f"  workspace: `{workspace}`"
        )

    async def post_archived(self, channel_name: str, archive_path: str) -> None:
        await self.post_event(
            "channel", f"**#{channel_name}** archived → `{archive_path}`"
        )

    async def post_suspend(self, channel_name: str) -> None:
        if self.verbose_suspends:
            await self.post_event("info", f"#{channel_name} suspended (idle 30m)")

    async def post_resume(self, channel_name: str) -> None:
        if self.verbose_suspends:
            await self.post_event("info", f"#{channel_name} resumed")
