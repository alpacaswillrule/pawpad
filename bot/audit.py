"""#jojo-audit channel poster.

Owns the audit channel: creates it on first run, posts daily spend summaries
at VM midnight, budget warnings, agent crashes, channel archives, new channel
+ repo creation events, suspend/resume (debug-toggleable).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bot.main import PawpadBot

logger = logging.getLogger("pawpad.audit")

AUDIT_CHANNEL_NAME = "jojo-audit"


class Audit:
    def __init__(self, bot: "PawpadBot") -> None:
        self.bot = bot
        self._channel_id: int | None = None
        self.verbose_suspends = False  # debug toggle

    async def ensure_channel(self, guild: discord.Guild) -> discord.TextChannel:
        """Find or create the #jojo-audit channel."""
        # TODO:
        #   - look for existing channel named AUDIT_CHANNEL_NAME
        #   - if missing: create it (text channel, not under 'projects' category)
        #   - cache self._channel_id
        raise NotImplementedError

    async def post(self, text: str) -> None:
        """Post a plain message to #jojo-audit."""
        # TODO
        raise NotImplementedError

    async def post_budget_warning(self, pct: float, spent: float, cap: float) -> None:
        """Post 80% / 95% / 100% warning."""
        # TODO
        raise NotImplementedError

    async def post_crash(self, channel_name: str, exc: BaseException) -> None:
        """Post an agent crash with truncated stack trace."""
        # TODO
        raise NotImplementedError

    async def post_daily_summary(self, summary: dict) -> None:
        """Post daily spend summary at VM midnight."""
        # TODO: format table of per-channel usage + global total
        raise NotImplementedError
