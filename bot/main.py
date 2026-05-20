"""pawpad bot — Discord entry point.

Runs on the VM under systemd. Watches the configured guild, spawns a Claude
Agent SDK session per channel in the `projects` category, and routes messages
in both directions.

Env (see .env.example):
  DISCORD_TOKEN, DISCORD_GUILD_ID                   required
  ANTHROPIC_API_KEY                                  required (read by SDK)
  PAWPAD_WORKSPACES   default ~/projects
  PAWPAD_VAULT        default ~/obsidian-vault
  PAWPAD_GH_OWNER     default alpacaswillrule
  PAWPAD_SOFT_CAP     default 8
  PAWPAD_IDLE_TIMEOUT_SECONDS  default 1800
  PAWPAD_DEFAULT_DAILY_CAP_USD default 500
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import signal
from pathlib import Path

import discord
from dotenv import load_dotenv

from bot.audit import Audit
from bot.budget import Budget
from bot.sessions import SessionManager
from bot.slash import register_slash_commands

logger = logging.getLogger("pawpad.bot")

PROJECTS_CATEGORY = "projects"


SLASH_HASH_PATH = Path("~/.pawpad/slash_hash").expanduser()


def make_intents() -> discord.Intents:
    intents = discord.Intents.default()
    intents.message_content = True
    intents.guilds = True
    return intents


def _slash_signature(tree: discord.app_commands.CommandTree) -> str:
    """Hash the registered commands so we only re-sync when they change."""
    sig = []
    for cmd in tree.get_commands():
        sig.append({
            "name": cmd.name,
            "description": getattr(cmd, "description", ""),
            "params": [
                {"name": p.name, "type": str(p.type), "required": p.required}
                for p in (cmd.parameters if hasattr(cmd, "parameters") else [])
            ],
        })
    blob = json.dumps(sig, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


class PawpadBot(discord.Client):
    def __init__(
        self,
        *,
        guild_id: int,
        workspaces_root: Path,
        vault_root: Path,
        gh_owner: str = "alpacaswillrule",
        soft_cap: int = 8,
        idle_timeout: int = 1800,
        default_daily_cap_usd: float = 500.0,
    ) -> None:
        super().__init__(intents=make_intents())
        self.tree = discord.app_commands.CommandTree(self)
        self.guild_id = guild_id
        self.workspaces_root = workspaces_root
        self.vault_root = vault_root

        self.budget = Budget(default_daily_cap_usd=default_daily_cap_usd)
        self.audit = Audit(self)
        self.sessions = SessionManager(
            bot=self,
            workspaces_root=workspaces_root,
            vault_root=vault_root,
            budget=self.budget,
            audit=self.audit,
            soft_cap=soft_cap,
            idle_timeout_seconds=idle_timeout,
            gh_owner=gh_owner,
        )

    async def setup_hook(self) -> None:
        self.budget.open()
        register_slash_commands(self.tree, self)

        # Globally-registered tree commands get copied to the guild via
        # copy_global_to so they appear instantly (no 1hr global propagation).
        guild_obj = discord.Object(id=self.guild_id)
        try:
            self.tree.copy_global_to(guild=guild_obj)
        except Exception as exc:  # noqa: BLE001
            logger.debug("copy_global_to skipped: %s", exc)

        sig = _slash_signature(self.tree)
        prev = SLASH_HASH_PATH.read_text().strip() if SLASH_HASH_PATH.exists() else ""
        force = os.environ.get("PAWPAD_FORCE_SYNC") == "1"
        if force or sig != prev:
            try:
                synced = await self.tree.sync(guild=guild_obj)
                SLASH_HASH_PATH.parent.mkdir(parents=True, exist_ok=True)
                SLASH_HASH_PATH.write_text(sig)
                logger.info(
                    "synced %d slash commands to guild %s: %s",
                    len(synced),
                    self.guild_id,
                    ", ".join(f"/{c.name}" for c in synced) or "(none!)",
                )
            except discord.HTTPException as exc:
                logger.warning("slash sync failed: %s", exc)
        else:
            logger.info("slash commands unchanged; skipping sync")

    async def on_ready(self) -> None:
        logger.info(
            "logged in as %s (%s)", self.user, self.user.id if self.user else "?"
        )
        guild = self.get_guild(self.guild_id)
        if guild is None:
            logger.error("bot is not in guild %s — invite it via OAuth URL", self.guild_id)
            return

        await self.audit.ensure_channel(guild)
        await self.audit.post_event("ok", f"pawpad bot online as {self.user}")

        await self.sessions.bootstrap_existing_channels(guild)
        await self.sessions.start_background()

    async def on_guild_channel_create(
        self, channel: discord.abc.GuildChannel
    ) -> None:
        try:
            await self.sessions.on_channel_created(channel)
        except Exception:
            logger.exception("on_guild_channel_create failed")

    async def on_guild_channel_delete(
        self, channel: discord.abc.GuildChannel
    ) -> None:
        try:
            await self.sessions.on_channel_deleted(channel)
        except Exception:
            logger.exception("on_guild_channel_delete failed")

    async def on_message(self, msg: discord.Message) -> None:
        if msg.guild is None or msg.guild.id != self.guild_id:
            return
        if msg.author.bot:
            return
        try:
            await self.sessions.handle_message(msg)
        except Exception:
            logger.exception("on_message failed for #%s", msg.channel)

    async def on_error(self, event: str, *args, **kwargs) -> None:
        logger.exception("discord client error in %s", event)

    async def close(self) -> None:
        await self.sessions.stop_background()
        for cid in list(self.sessions.sessions):
            try:
                await self.sessions.pause(cid)
            except Exception:
                pass
        self.budget.close()
        await super().close()


def _env(*names: str, default: str | None = None) -> str | None:
    """Look up env var under multiple possible names; first non-empty wins."""
    for n in names:
        v = os.environ.get(n)
        if v:
            return v
    return default


def main() -> None:
    # Load .env.dev first (local dev secrets) then .env on top with override=False.
    # Empty values in .env shouldn't shadow real values in .env.dev.
    load_dotenv(".env.dev")
    load_dotenv(override=False)

    logging.basicConfig(
        level=os.environ.get("PAWPAD_LOG_LEVEL", "INFO"),
        format="%(asctime)s %(name)s %(levelname)s %(message)s",
    )

    token = _env("DISCORD_TOKEN")
    if not token:
        raise SystemExit("DISCORD_TOKEN not set")
    guild_id_raw = _env("DISCORD_GUILD_ID", "SERVER_ID", "DISCORD_SERVER_ID")
    if not guild_id_raw:
        raise SystemExit("DISCORD_GUILD_ID (or SERVER_ID) not set")
    guild_id = int(guild_id_raw)
    workspaces_root = Path(os.environ.get("PAWPAD_WORKSPACES", "~/projects")).expanduser()
    vault_root = Path(os.environ.get("PAWPAD_VAULT", "~/obsidian-vault")).expanduser()
    gh_owner = os.environ.get("PAWPAD_GH_OWNER", "alpacaswillrule")
    soft_cap = int(os.environ.get("PAWPAD_SOFT_CAP", "8"))
    idle_timeout = int(os.environ.get("PAWPAD_IDLE_TIMEOUT_SECONDS", "1800"))
    default_daily_cap = float(os.environ.get("PAWPAD_DEFAULT_DAILY_CAP_USD", "500"))

    workspaces_root.mkdir(parents=True, exist_ok=True)
    vault_root.mkdir(parents=True, exist_ok=True)

    bot = PawpadBot(
        guild_id=guild_id,
        workspaces_root=workspaces_root,
        vault_root=vault_root,
        gh_owner=gh_owner,
        soft_cap=soft_cap,
        idle_timeout=idle_timeout,
        default_daily_cap_usd=default_daily_cap,
    )

    async def _runner() -> None:
        loop = asyncio.get_running_loop()
        stop = asyncio.Event()
        for sig in (signal.SIGTERM, signal.SIGINT):
            try:
                loop.add_signal_handler(sig, stop.set)
            except NotImplementedError:
                pass
        try:
            await bot.start(token)
        finally:
            await bot.close()

    asyncio.run(_runner())


if __name__ == "__main__":
    main()
