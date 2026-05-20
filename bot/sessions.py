"""Per-channel Claude Agent SDK session manager.

Responsibilities:
  - On channel-create: scaffold workspace + gh repo + Obsidian folder, open SDK session
  - On message: enqueue for the session's next turn boundary (no mid-turn interrupt)
  - Track activity (tool calls, tokens streamed, user msgs) for idle detection
  - Suspend sessions after 30min of true silence; resume by session_id on next msg
  - Enforce soft-cap of 8 active sessions, queue overflow
  - Persist (session_id, channel_id) so we can resume across bot restarts
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from bot.audit import Audit
    from bot.budget import Budget
    from bot.main import PawpadBot

logger = logging.getLogger("pawpad.sessions")

IDLE_TIMEOUT_SECONDS = 30 * 60


@dataclass
class ChannelSession:
    """One agent session bound to one Discord channel."""

    channel_id: int
    channel_name: str
    workspace: Path
    vault_project_dir: Path
    session_id: str | None = None  # set after first turn, used to resume

    # activity tracking — any of these resets the idle timer
    last_tool_event_at: float = 0.0
    last_token_event_at: float = 0.0
    last_user_msg_at: float = 0.0

    # state
    state: str = "idle"  # idle | active | queued | suspended | paused
    pending_messages: list[str] = field(default_factory=list)

    def latest_activity(self) -> float:
        return max(self.last_tool_event_at, self.last_token_event_at, self.last_user_msg_at)


class SessionManager:
    def __init__(
        self,
        *,
        bot: "PawpadBot",
        workspaces_root: Path,
        vault_root: Path,
        budget: "Budget",
        audit: "Audit",
        soft_cap: int = 8,
    ) -> None:
        self.bot = bot
        self.workspaces_root = workspaces_root
        self.vault_root = vault_root
        self.budget = budget
        self.audit = audit
        self.soft_cap = soft_cap
        self.sessions: dict[int, ChannelSession] = {}
        self.queue: asyncio.Queue[int] = asyncio.Queue()

    # ---- lifecycle ---------------------------------------------------------

    async def bootstrap_existing_channels(self, guild: discord.Guild) -> None:
        """On bot startup, reconnect to any existing channels in the projects category."""
        # TODO:
        #   - find category named PROJECTS_CATEGORY
        #   - for each text channel inside, if workspace exists -> attach (don't recreate)
        #     else -> create_for_channel
        raise NotImplementedError

    async def create_for_channel(self, channel: discord.TextChannel) -> None:
        """Scaffold workspace + gh repo + Obsidian folder, then open the SDK session."""
        # TODO:
        #   - call scripts/new-project.sh {slug} (or do it in-process)
        #   - create gh repo via `gh repo create alpacaswillrule/{slug} --private`
        #   - create vault project dir + plan.md from template
        #   - register ChannelSession in self.sessions
        #   - if channel.topic: enqueue topic as initial prompt
        #   - post welcome message
        raise NotImplementedError

    async def archive_channel(self, channel_id: int) -> None:
        """Channel deleted (or /archive). Move workspace + vault dir to _archived/."""
        # TODO
        raise NotImplementedError

    # ---- message routing ---------------------------------------------------

    async def handle_message(self, msg: discord.Message) -> None:
        """Discord message arrived. Enqueue for next turn boundary."""
        # TODO:
        #   - look up ChannelSession by msg.channel.id
        #   - if state == paused: ignore
        #   - if state == suspended: resume via session_id, then enqueue
        #   - if state == queued: add to pending_messages, return
        #   - if state == active: add to pending_messages (will be picked up at next turn)
        #   - if state == idle: enqueue + start a turn
        #   - update last_user_msg_at
        raise NotImplementedError

    # ---- agent loop --------------------------------------------------------

    async def run_turn(self, session: ChannelSession) -> None:
        """Run one turn of the agent against the SDK, streaming output to Discord."""
        # TODO:
        #   - check budget; if over -> pause and post to audit
        #   - drain pending_messages into the SDK's input
        #   - open ClaudeSDKClient (or reuse) with:
        #       cwd=session.workspace
        #       permission_mode="bypassPermissions"
        #       allowed_tools=["*"]
        #       system_prompt=auto-injected identity + channel context
        #       resume=session.session_id (if set)
        #   - subscribe to events:
        #       tool_use_start  -> last_tool_event_at
        #       tool_use_result -> last_tool_event_at
        #       text_delta      -> last_token_event_at, buffer for final post
        #       turn_end        -> capture session_id, final text, tool count, cost
        #   - post final text via bot.output (chunked); append footer
        #   - update budget ledger
        raise NotImplementedError

    # ---- idle watcher ------------------------------------------------------

    async def idle_watcher(self) -> None:
        """Background task: suspend sessions idle for IDLE_TIMEOUT_SECONDS."""
        # TODO:
        #   - every 60s, scan sessions
        #   - if state == active and (now - latest_activity()) > IDLE_TIMEOUT_SECONDS:
        #       -> suspend (free slot, keep session_id for resume)
        raise NotImplementedError
