"""Per-channel Claude Agent SDK session manager.

State machine per channel:

  closed     no SDK client, no work pending. Cold.
  open       SDK client live. May be running a turn or between turns.
  queued     work waiting, but the soft-cap is full. No client yet.
  paused     user ran /pause. Messages ignored until /resume.

Transitions:

  closed + message      → open (acquire slot) → run turn
  open   + message      → queued onto session, picked up at next turn boundary
  open   + idle 30min   → close (release slot); persisted session_id is kept
  closed + slot avail   → resume from session_id when next message arrives
  paused + message      → message ignored
  any    + /pause       → paused (release slot if held; keep session_id)
  paused + /resume      → closed (then if pending, transition to open)

Soft-cap (default 8) is enforced via a slot semaphore. Overflow waits FIFO.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

import discord
from claude_agent_sdk import (
    AssistantMessage,
    ClaudeAgentOptions,
    ClaudeSDKClient,
    ResultMessage,
    TextBlock,
    ToolUseBlock,
)

from bot.budget import Budget, TurnCost
from bot.mcp.discord_send import make_server
from bot.output import TypingHeartbeat, TurnFooter, post_chunked, post_turn

if TYPE_CHECKING:
    from bot.audit import Audit
    from bot.main import PawpadBot

logger = logging.getLogger("pawpad.sessions")

IDLE_TIMEOUT_SECONDS = 30 * 60
IDLE_SCAN_INTERVAL_SECONDS = 60
SESSION_STORE = Path("~/.pawpad/sessions.json").expanduser()

REPO_OWNER_ENV = "PAWPAD_GH_OWNER"
DEFAULT_REPO_OWNER = "alpacaswillrule"


# ---------------------------------------------------------------------------
# data
# ---------------------------------------------------------------------------


def slugify(name: str) -> str:
    """Discord channel name → safe filesystem slug (Discord already enforces most of this)."""
    s = re.sub(r"[^a-z0-9_-]+", "-", name.lower())
    s = re.sub(r"-+", "-", s).strip("-")
    return s or "untitled"


@dataclass
class ChannelSession:
    channel_id: int
    channel_name: str
    workspace: Path
    vault_project_dir: Path
    repo_url: str | None = None

    # SDK state
    session_id: str | None = None
    client: ClaudeSDKClient | None = None
    state: str = "closed"  # closed | open | queued | paused

    # activity tracking — any reset the idle timer
    last_tool_event_at: float = 0.0
    last_token_event_at: float = 0.0
    last_user_msg_at: float = 0.0
    last_turn_end_at: float = 0.0

    # pending user messages (drained at next turn start)
    pending: deque[str] = field(default_factory=deque)

    # per-session lock — only one turn at a time
    turn_lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    # ensures we don't schedule two turns concurrently
    drainer: asyncio.Task | None = None

    def latest_activity(self) -> float:
        return max(
            self.last_tool_event_at,
            self.last_token_event_at,
            self.last_user_msg_at,
            self.last_turn_end_at,
        )

    def mark_tool(self) -> None:
        self.last_tool_event_at = time.time()

    def mark_token(self) -> None:
        self.last_token_event_at = time.time()


# ---------------------------------------------------------------------------
# manager
# ---------------------------------------------------------------------------


class SessionManager:
    PROJECTS_CATEGORY = "projects"

    def __init__(
        self,
        *,
        bot: "PawpadBot",
        workspaces_root: Path,
        vault_root: Path,
        budget: Budget,
        audit: "Audit",
        soft_cap: int = 8,
        idle_timeout_seconds: int = IDLE_TIMEOUT_SECONDS,
        gh_owner: str = DEFAULT_REPO_OWNER,
        scripts_root: Path | None = None,
    ) -> None:
        self.bot = bot
        self.workspaces_root = workspaces_root
        self.vault_root = vault_root
        self.budget = budget
        self.audit = audit
        self.soft_cap = soft_cap
        self.idle_timeout = idle_timeout_seconds
        self.gh_owner = gh_owner
        self.scripts_root = scripts_root or Path(__file__).resolve().parent.parent / "scripts"

        self.sessions: dict[int, ChannelSession] = {}
        self.slot_sem = asyncio.Semaphore(soft_cap)
        self.holders: set[int] = set()  # channel_ids currently holding a slot
        self._idle_task: asyncio.Task | None = None
        self._store_lock = asyncio.Lock()

    # ---- lifecycle ---------------------------------------------------------

    async def start_background(self) -> None:
        self._idle_task = asyncio.create_task(self._idle_loop())

    async def stop_background(self) -> None:
        if self._idle_task is not None:
            self._idle_task.cancel()
            try:
                await self._idle_task
            except BaseException:  # expected during shutdown
                pass

    async def bootstrap_existing_channels(self, guild: discord.Guild) -> None:
        category = _find_projects_category(guild, self.PROJECTS_CATEGORY)
        if category is None:
            logger.warning(
                "no `%s` category in guild %s — bot will idle until you create one",
                self.PROJECTS_CATEGORY,
                guild.name,
            )
            return

        stored = _load_session_store()

        for channel in category.text_channels:
            slug = slugify(channel.name)
            workspace = self.workspaces_root / slug
            vault_dir = self.vault_root / "projects" / slug

            session_id = stored.get(str(channel.id))
            repo_url = f"https://github.com/{self.gh_owner}/{slug}"

            session = ChannelSession(
                channel_id=channel.id,
                channel_name=channel.name,
                workspace=workspace,
                vault_project_dir=vault_dir,
                repo_url=repo_url,
                session_id=session_id,
            )
            self.sessions[channel.id] = session

            if not workspace.exists():
                # channel exists but never got scaffolded → do it now
                try:
                    await self._scaffold_workspace(channel, session)
                    await self.audit.post_channel_created(
                        channel.name, session.repo_url or "", str(workspace)
                    )
                except Exception as exc:
                    logger.exception("scaffold failed for #%s", channel.name)
                    await self.audit.post_crash(channel.name, exc)

        logger.info("bootstrapped %d channels under #%s", len(self.sessions), category.name)

    # ---- channel events ----------------------------------------------------

    async def on_channel_created(self, channel: discord.abc.GuildChannel) -> None:
        if not isinstance(channel, discord.TextChannel):
            return
        if not _under_projects_category(channel, self.PROJECTS_CATEGORY):
            return
        if channel.id in self.sessions:
            return

        slug = slugify(channel.name)
        workspace = self.workspaces_root / slug
        vault_dir = self.vault_root / "projects" / slug

        session = ChannelSession(
            channel_id=channel.id,
            channel_name=channel.name,
            workspace=workspace,
            vault_project_dir=vault_dir,
        )
        self.sessions[channel.id] = session

        try:
            await self._scaffold_workspace(channel, session)
        except Exception as exc:
            logger.exception("scaffold failed for #%s", channel.name)
            await self.audit.post_crash(channel.name, exc)
            return

        repo_url = session.repo_url or ""
        await channel.send(
            f"workspace ready · repo {repo_url} · notes `obsidian-vault/projects/{slug}/`"
        )
        await self.audit.post_channel_created(channel.name, repo_url, str(workspace))

        if channel.topic and channel.topic.strip():
            session.pending.append(channel.topic.strip())
            session.last_user_msg_at = time.time()
            self._kick(session)

    async def on_channel_deleted(self, channel: discord.abc.GuildChannel) -> None:
        if channel.id not in self.sessions:
            return
        await self.archive_channel(channel.id, source="delete")

    # ---- message routing ---------------------------------------------------

    async def handle_message(self, msg: discord.Message) -> None:
        if msg.author.bot:
            return
        session = self.sessions.get(msg.channel.id)
        if session is None:
            return
        if session.state == "paused":
            return

        content = msg.content.strip()
        if not content and not msg.attachments:
            return

        if msg.attachments:
            attach_descs = "\n".join(
                f"[attachment: {a.filename} <{a.url}>]" for a in msg.attachments
            )
            content = f"{content}\n{attach_descs}" if content else attach_descs

        session.pending.append(f"<{msg.author.display_name}>: {content}")
        session.last_user_msg_at = time.time()
        self._kick(session)

    def _kick(self, session: ChannelSession) -> None:
        """Schedule a drainer if not already running."""
        if session.drainer is not None and not session.drainer.done():
            return  # already running; pending will be picked up at next turn boundary
        session.drainer = asyncio.create_task(self._drain(session))

    async def _drain(self, session: ChannelSession) -> None:
        """Run turns back-to-back until pending is empty or pause flips state."""
        try:
            while session.pending and session.state != "paused":
                if self.budget.is_over_cap():
                    await self._pause_for_budget(session)
                    return

                acquired = await self._acquire_slot(session)
                if not acquired:
                    return  # we got paused while waiting

                try:
                    await self._run_turn(session)
                except Exception as exc:
                    logger.exception("turn failed for #%s", session.channel_name)
                    await self.audit.post_crash(session.channel_name, exc)
                    # Drop the dead client so the next turn rebuilds it
                    await self._force_disconnect(session)
                    # Drop the pending messages that just crashed — otherwise
                    # the next iteration retries them and loops forever on the
                    # same fatal error. The user can re-send if they want.
                    if session.pending:
                        logger.warning(
                            "discarding %d pending msgs after crash in #%s",
                            len(session.pending), session.channel_name,
                        )
                        session.pending.clear()
                    return  # exit the drain loop; next message starts fresh
        finally:
            session.drainer = None
            # If we exited because pause was flipped mid-turn, release the slot now.
            if session.state == "paused":
                await self._force_disconnect(session)

    # ---- slot management ---------------------------------------------------

    async def _acquire_slot(self, session: ChannelSession) -> bool:
        """Acquire a concurrency slot, marking the session 'queued' if we wait."""
        if session.channel_id in self.holders:
            return True
        # Try non-blocking first; if it would block, mark queued and wait.
        try:
            await asyncio.wait_for(self.slot_sem.acquire(), timeout=0)
        except asyncio.TimeoutError:
            prev = session.state
            session.state = "queued"
            try:
                await self.slot_sem.acquire()
            except asyncio.CancelledError:
                if session.state == "queued":
                    session.state = prev
                raise
            if session.state == "paused":
                self.slot_sem.release()
                return False
        if session.state != "paused":
            session.state = "open"
        else:
            self.slot_sem.release()
            return False
        self.holders.add(session.channel_id)
        return True

    def _release_slot(self, session: ChannelSession) -> None:
        if session.channel_id in self.holders:
            self.holders.discard(session.channel_id)
            self.slot_sem.release()

    async def _save_session_id(self, channel_id: int, session_id: str) -> None:
        async with self._store_lock:
            SESSION_STORE.parent.mkdir(parents=True, exist_ok=True)
            store = _load_session_store()
            store[str(channel_id)] = session_id
            SESSION_STORE.write_text(json.dumps(store, indent=2, sort_keys=True))

    async def _forget_session_id(self, channel_id: int) -> None:
        async with self._store_lock:
            if not SESSION_STORE.exists():
                return
            store = _load_session_store()
            store.pop(str(channel_id), None)
            SESSION_STORE.write_text(json.dumps(store, indent=2, sort_keys=True))

    async def _force_disconnect(self, session: ChannelSession) -> None:
        """Close the SDK client and free the slot. Safe to call repeatedly."""
        client = session.client
        session.client = None
        if client is not None:
            try:
                await client.disconnect()
            except Exception as exc:  # noqa: BLE001
                logger.debug("disconnect (force) failed: %s", exc)
        if session.state == "open":
            session.state = "closed"
        self._release_slot(session)

    # ---- the turn ----------------------------------------------------------

    async def _run_turn(self, session: ChannelSession) -> None:
        async with session.turn_lock:
            channel = self.bot.get_channel(session.channel_id)
            if channel is None:
                logger.warning("channel %s vanished mid-turn", session.channel_id)
                return

            try:
                await self._ensure_client(session)
            except Exception:
                # Connect failed — release the slot we hold; pending is intact.
                self._release_slot(session)
                raise
            assert session.client is not None

            # Snapshot pending; restore on early failure so messages aren't lost.
            drained = list(session.pending)
            session.pending.clear()
            prompt = "\n\n".join(drained)

            footer = TurnFooter(tool_count=0, elapsed_seconds=0.0, usd=0.0)
            text_parts: list[str] = []
            usage: dict | None = None
            model: str = "claude-opus-4-7"
            t0 = time.monotonic()

            got_result = False
            try:
                async with TypingHeartbeat(channel):
                    await session.client.query(prompt)
                    async for message in session.client.receive_response():
                        if isinstance(message, AssistantMessage):
                            for block in message.content:
                                if isinstance(block, ToolUseBlock):
                                    footer.tool_count += 1
                                    session.mark_tool()
                                elif isinstance(block, TextBlock):
                                    text_parts.append(block.text)
                                    session.mark_token()
                        elif isinstance(message, ResultMessage):
                            got_result = True
                            if message.session_id:
                                session.session_id = message.session_id
                                await self._save_session_id(
                                    session.channel_id, message.session_id
                                )
                            usage = getattr(message, "usage", None) or {}
                            model = getattr(message, "model", model) or model
                            if not text_parts and getattr(message, "result", None):
                                text_parts.append(message.result)
                            break
            except Exception:
                # Failure during the turn — restore pending so the user's messages
                # aren't silently dropped. Outer except in _drain handles the post.
                for line in reversed(drained):
                    session.pending.appendleft(line)
                raise

            footer.elapsed_seconds = time.monotonic() - t0
            session.last_turn_end_at = time.time()

            if usage is not None:
                spent_before = self.budget.spent_today()
                in_tok = int(usage.get("input_tokens", 0))
                out_tok = int(usage.get("output_tokens", 0))
                cache_r = int(usage.get("cache_read_input_tokens", 0))
                cache_w = int(usage.get("cache_creation_input_tokens", 0))
                usd = Budget.price_usd(model, in_tok, out_tok, cache_r, cache_w)
                footer.usd = usd

                self.budget.record_turn(
                    TurnCost(
                        channel_id=session.channel_id,
                        model=model,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                        cache_read_tokens=cache_r,
                        cache_write_tokens=cache_w,
                        usd=usd,
                    )
                )

                spent_after = self.budget.spent_today()
                threshold = self.budget.warning_threshold_crossed(
                    spent_before=spent_before, spent_after=spent_after
                )
                if threshold is not None:
                    await self.audit.post_budget_warning(
                        threshold, spent_after, self.budget.daily_cap()
                    )
                if threshold == 1.0:
                    await self._pause_all_for_budget()

            text = "".join(text_parts).strip()
            if text:
                await post_turn(channel, text, footer=footer)
            else:
                await channel.send(footer.render())

    async def _ensure_client(self, session: ChannelSession) -> None:
        if session.client is not None:
            return

        # SDK requires an iterable for allowed_tools — `None` crashes inside
        # _apply_skills_defaults. Pass an explicit list of all known built-ins +
        # the custom MCP tool. (Permission_mode=bypassPermissions means none of
        # these prompt; the list is just gating membership.)
        allowed_tools = [
            "Read", "Write", "Edit", "MultiEdit", "Bash",
            "Glob", "Grep", "WebSearch", "WebFetch",
            "Task", "TodoWrite", "NotebookEdit",
            "mcp__pawpad__discord_send",
        ]

        options = ClaudeAgentOptions(
            cwd=str(session.workspace),
            permission_mode="bypassPermissions",
            system_prompt=self._build_system_prompt(session),
            mcp_servers={"pawpad": make_server(self.bot.get_channel(session.channel_id))},
            allowed_tools=allowed_tools,
            setting_sources=["project"],
            resume=session.session_id,
        )
        client = ClaudeSDKClient(options=options)
        await client.connect()
        session.client = client
        session.state = "open"
        if session.session_id:
            await self.audit.post_resume(session.channel_name)

    def _build_system_prompt(self, session: ChannelSession) -> str:
        return (
            f"You are running as Jojo in Discord channel #{session.channel_name}. "
            f"Workspace: {session.workspace}. "
            f"Obsidian vault: {self.vault_root} "
            f"(this channel's notes live at {session.vault_project_dir}). "
            f"The user 'jojo' may not be the only person in the channel. "
            f"The bot will auto-post your final reply each turn — call the "
            f"`mcp__pawpad__discord_send` tool only for mid-turn status updates. "
            f"Follow the VM-wide CLAUDE.md and this workspace's CLAUDE.md."
        )

    # ---- suspend / resume / pause / archive --------------------------------

    async def suspend(self, session: ChannelSession, *, reason: str = "idle") -> None:
        if session.client is None:
            return
        try:
            await session.client.disconnect()
        except Exception as exc:  # noqa: BLE001
            logger.warning("disconnect failed for #%s: %s", session.channel_name, exc)
        session.client = None
        if session.state == "open":
            session.state = "closed"
        self._release_slot(session)
        if reason == "idle":
            await self.audit.post_suspend(session.channel_name)

    async def pause(self, channel_id: int) -> bool:
        session = self.sessions.get(channel_id)
        if session is None:
            return False
        was = session.state
        session.state = "paused"

        if session.turn_lock.locked() and session.client is not None:
            # turn in flight — ask SDK to wind down cleanly; the drainer's
            # next iteration sees state=paused and exits, releasing the slot.
            try:
                await session.client.interrupt()
            except Exception as exc:  # noqa: BLE001
                logger.debug("interrupt failed: %s", exc)
        else:
            # idle between turns — disconnect now and free the slot
            await self._force_disconnect(session)

        logger.info("paused #%s (was %s)", session.channel_name, was)
        return True

    async def resume(self, channel_id: int) -> bool:
        session = self.sessions.get(channel_id)
        if session is None or session.state != "paused":
            return False
        session.state = "closed"
        if session.pending:
            self._kick(session)
        return True

    async def _pause_for_budget(self, session: ChannelSession) -> None:
        await self.audit.post_budget_hit(self.budget.spent_today(), self.budget.daily_cap())
        await self.pause(session.channel_id)

    async def _pause_all_for_budget(self) -> None:
        for cid in list(self.sessions):
            await self.pause(cid)

    async def archive_channel(self, channel_id: int, *, source: str = "manual") -> None:
        session = self.sessions.get(channel_id)
        if session is None:
            return
        # 1. close client + release slot while session is still findable
        await self.pause(channel_id)
        # 2. now remove from active sessions
        self.sessions.pop(channel_id, None)
        # 3. run archive script (bounded)
        try:
            proc = await asyncio.create_subprocess_exec(
                str(self.scripts_root / "archive-project.sh"),
                slugify(session.channel_name),
                env={
                    "HOME": str(Path.home()),
                    "PATH": "/usr/local/bin:/usr/bin:/bin",
                    "WORKSPACES_ROOT": str(self.workspaces_root),
                    "VAULT_ROOT": str(self.vault_root),
                },
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                out, err = await asyncio.wait_for(proc.communicate(), timeout=60)
                if proc.returncode != 0:
                    logger.error("archive script failed: %s", err.decode())
            except asyncio.TimeoutError:
                proc.kill()
                await proc.communicate()
                logger.error("archive script timed out for #%s", session.channel_name)
        except Exception:
            logger.exception("archive script crashed")
        await self._forget_session_id(channel_id)
        await self.audit.post_archived(session.channel_name, "_archived/")

    # ---- idle watcher ------------------------------------------------------

    async def _idle_loop(self) -> None:
        try:
            while True:
                await asyncio.sleep(IDLE_SCAN_INTERVAL_SECONDS)
                now = time.time()
                for cid in list(self.holders):
                    session = self.sessions.get(cid)
                    if session is None:
                        continue
                    if session.state != "open":
                        continue
                    if session.turn_lock.locked():
                        continue  # turn in flight; not idle
                    if now - session.latest_activity() > self.idle_timeout:
                        await self.suspend(session, reason="idle")
        except asyncio.CancelledError:
            pass

    # ---- scaffolding -------------------------------------------------------

    async def _scaffold_workspace(
        self, channel: discord.abc.GuildChannel, session: ChannelSession
    ) -> None:
        slug = slugify(channel.name)
        topic = (getattr(channel, "topic", None) or "").strip()
        env = {
            "HOME": str(Path.home()),
            "PATH": "/usr/local/bin:/usr/bin:/bin",
            "GH_OWNER": self.gh_owner,
            "WORKSPACES_ROOT": str(self.workspaces_root),
            "VAULT_ROOT": str(self.vault_root),
        }
        script = self.scripts_root / "new-project.sh"
        proc = await asyncio.create_subprocess_exec(
            str(script),
            slug,
            topic,
            env=env,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        try:
            out, err = await asyncio.wait_for(proc.communicate(), timeout=180)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.communicate()
            raise RuntimeError("new-project.sh timed out after 3 minutes") from None
        if proc.returncode != 0:
            raise RuntimeError(
                f"new-project.sh failed (rc={proc.returncode}): {err.decode()[:400]}"
            )
        session.repo_url = f"https://github.com/{self.gh_owner}/{slug}"


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _find_projects_category(
    guild: discord.Guild, name: str
) -> discord.CategoryChannel | None:
    for c in guild.categories:
        if c.name.lower() == name.lower():
            return c
    return None


def _under_projects_category(channel: discord.abc.GuildChannel, name: str) -> bool:
    category = getattr(channel, "category", None)
    return category is not None and category.name.lower() == name.lower()


def _load_session_store() -> dict[str, str]:
    if not SESSION_STORE.exists():
        return {}
    try:
        return json.loads(SESSION_STORE.read_text())
    except Exception:  # noqa: BLE001
        logger.warning("session store at %s is unreadable, ignoring", SESSION_STORE)
        return {}
