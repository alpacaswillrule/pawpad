"""pawpad bot — Discord entry point.

Runs on the VM under systemd. Watches the configured guild, spawns a Claude
Agent SDK session per channel in the `projects` category, and routes messages
in both directions.

Architecture:
  - main.py            discord.py client, event handlers
  - sessions.py        per-channel agent session manager (Agent SDK)
  - slash.py           slash command registration + handlers
  - budget.py          spend ledger + hard-pause
  - audit.py           #jojo-audit poster
  - output.py          Discord output formatting (chunking, attachments)
  - mcp/discord_send.py in-process MCP server for outbound mid-turn updates
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

import discord
from dotenv import load_dotenv

from bot.audit import Audit
from bot.budget import Budget
from bot.sessions import SessionManager
from bot.slash import register_slash_commands

logger = logging.getLogger("pawpad.bot")

PROJECTS_CATEGORY = "projects"
AUDIT_CHANNEL = "jojo-audit"


def make_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.members = True
    intents.guilds = True
    return intents


class PawpadBot(discord.Client):
    def __init__(self, *, guild_id: int, workspaces_root: Path, vault_root: Path) -> None:
        super().__init__(intents=make_intents())
        self.tree = discord.app_commands.CommandTree(self)
        self.guild_id = guild_id
        self.workspaces_root = workspaces_root
        self.vault_root = vault_root
        self.budget = Budget()
        self.audit = Audit(self)
        self.sessions = SessionManager(
            bot=self,
            workspaces_root=workspaces_root,
            vault_root=vault_root,
            budget=self.budget,
            audit=self.audit,
            soft_cap=8,
        )

    async def setup_hook(self) -> None:
        register_slash_commands(self.tree, self)
        await self.tree.sync(guild=discord.Object(id=self.guild_id))

    async def on_ready(self) -> None:
        logger.info("Logged in as %s (%s)", self.user, self.user.id if self.user else "?")
        guild = self.get_guild(self.guild_id)
        if guild is None:
            logger.error("Bot is not in guild %s", self.guild_id)
            return
        await self.audit.ensure_channel(guild)
        await self.audit.post(f"pawpad bot online · {self.user}")
        await self.sessions.bootstrap_existing_channels(guild)

    async def on_guild_channel_create(self, channel: discord.abc.GuildChannel) -> None:
        # TODO: filter to channels under PROJECTS_CATEGORY only; ignore otherwise
        # TODO: hand off to self.sessions.create_for_channel(channel)
        raise NotImplementedError

    async def on_guild_channel_delete(self, channel: discord.abc.GuildChannel) -> None:
        # TODO: archive workspace + Obsidian folder; close session
        raise NotImplementedError

    async def on_message(self, msg: discord.Message) -> None:
        # TODO:
        #   - ignore self
        #   - ignore non-projects/non-audit channels
        #   - route to self.sessions.handle_message(msg)
        raise NotImplementedError


def main() -> None:
    load_dotenv()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    token = os.environ["DISCORD_TOKEN"]
    guild_id = int(os.environ["DISCORD_GUILD_ID"])
    workspaces_root = Path(os.environ.get("PAWPAD_WORKSPACES", "~/projects")).expanduser()
    vault_root = Path(os.environ.get("PAWPAD_VAULT", "~/obsidian-vault")).expanduser()

    bot = PawpadBot(
        guild_id=guild_id,
        workspaces_root=workspaces_root,
        vault_root=vault_root,
    )
    bot.run(token)


if __name__ == "__main__":
    main()
