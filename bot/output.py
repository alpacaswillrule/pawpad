"""Discord output formatting.

The Discord client cuts off messages at 2000 chars. We chunk text on
boundaries (line > word > hard) and preserve fenced code blocks across
chunks. Code blocks larger than 1800 chars get attached as files instead
of inlined.
"""

from __future__ import annotations

import asyncio
import io
import logging
import re
import time
from dataclasses import dataclass

import discord

logger = logging.getLogger("pawpad.output")

DISCORD_LIMIT = 2000
CODE_INLINE_LIMIT = 1800
SAFE_CHUNK = 1900  # leave headroom under DISCORD_LIMIT for fence/footer

_FENCE_RE = re.compile(r"^```(\w*)\s*$", re.MULTILINE)


@dataclass
class TurnFooter:
    tool_count: int
    elapsed_seconds: float
    usd: float

    def render(self) -> str:
        return f"-# • {self.tool_count} tools · {self.elapsed_seconds:.0f}s · ${self.usd:.2f}"


def extract_big_code_blocks(text: str) -> tuple[str, list[tuple[str, str]]]:
    """Pull code blocks > CODE_INLINE_LIMIT out of text into attachments.

    Returns (text_with_placeholders, [(filename, content), ...]). Each extracted
    block becomes `[attached: <filename>]` inline.
    """
    parts: list[str] = []
    attachments: list[tuple[str, str]] = []
    pos = 0
    counter = 0

    while True:
        m_open = _FENCE_RE.search(text, pos)
        if not m_open:
            parts.append(text[pos:])
            break

        parts.append(text[pos : m_open.start()])
        lang = m_open.group(1) or ""
        body_start = m_open.end()

        m_close = _FENCE_RE.search(text, body_start)
        if not m_close:
            parts.append(text[m_open.start() :])
            break

        body = text[body_start : m_close.start()].rstrip("\n")
        block_full = text[m_open.start() : m_close.end()]

        if len(block_full) > CODE_INLINE_LIMIT:
            counter += 1
            ext = (lang or "txt").lower()
            fname = f"output-{counter}.{ext}"
            attachments.append((fname, body))
            parts.append(f"[attached: {fname}]")
        else:
            parts.append(block_full)

        pos = m_close.end()

    return "".join(parts), attachments


def split_for_discord(text: str, limit: int = SAFE_CHUNK) -> list[str]:
    """Split text into chunks under `limit` chars.

    Preference order: paragraph boundary > line boundary > word boundary > hard cut.
    Open code fences are re-opened on the next chunk so syntax highlighting survives.
    """
    if len(text) <= limit:
        return [text] if text else []

    chunks: list[str] = []
    remaining = text
    open_fence: str | None = None  # if we cut inside a fence, this is the lang

    while len(remaining) > limit:
        cut = _find_split_point(remaining, limit)
        chunk = remaining[:cut].rstrip()
        remaining = remaining[cut:].lstrip("\n")

        # detect unterminated fence in this chunk
        fences = _FENCE_RE.findall(chunk)
        if open_fence is not None:
            chunk = f"```{open_fence}\n" + chunk
        if len(fences) % 2 == 1:
            # odd → we opened a fence and didn't close it
            new_open = fences[-1] if open_fence is None else open_fence
            chunk = chunk + "\n```"
            open_fence = new_open
        elif open_fence is not None and len(fences) % 2 == 0:
            # we were already inside a fence and didn't close it
            chunk = chunk + "\n```"
        else:
            open_fence = None

        chunks.append(chunk)

    if remaining:
        if open_fence is not None:
            remaining = f"```{open_fence}\n" + remaining
        chunks.append(remaining)

    return chunks


def _find_split_point(text: str, limit: int) -> int:
    """Best split point under `limit` chars."""
    window = text[:limit]
    for sep in ("\n\n", "\n", ". ", " "):
        idx = window.rfind(sep)
        if idx > limit // 2:
            return idx + len(sep)
    return limit


async def post_turn(
    channel: discord.abc.Messageable,
    text: str,
    *,
    footer: TurnFooter | None = None,
) -> None:
    """Post a complete agent turn to a Discord channel."""
    if not text or not text.strip():
        if footer:
            await channel.send(footer.render())
        return

    cleaned, attachments = extract_big_code_blocks(text)
    chunks = split_for_discord(cleaned)

    files = [
        discord.File(io.BytesIO(content.encode("utf-8")), filename=fname)
        for fname, content in attachments
    ]

    for i, chunk in enumerate(chunks):
        is_last = i == len(chunks) - 1
        send_kwargs: dict = {"content": chunk}
        if is_last and footer:
            footer_str = f"\n{footer.render()}"
            if len(chunk) + len(footer_str) <= DISCORD_LIMIT:
                send_kwargs["content"] = chunk + footer_str
            # else: fall through, post footer separately below
        if is_last and files:
            send_kwargs["files"] = files
            files = []  # consumed
        await channel.send(**send_kwargs)

    if files:
        await channel.send(files=files)

    if footer and chunks and len(chunks[-1]) + len(f"\n{footer.render()}") > DISCORD_LIMIT:
        await channel.send(footer.render())


async def post_chunked(channel: discord.abc.Messageable, text: str) -> None:
    """Send arbitrary text to a channel, chunked. No footer, no attachment extraction."""
    for chunk in split_for_discord(text):
        await channel.send(chunk)


class LiveMessage:
    """A Discord message that grows in place as the agent streams text.

    First `append` posts a new message. Subsequent appends edit it (rate-limited
    to ~1 edit/sec to stay under Discord's edit limit). When the message hits
    the chunk size, finalize it and start a new one. `finalize` flushes any
    pending buffer and optionally appends a footer.

    Designed so a 2000-character agent response shows up word-by-word in the
    channel instead of dumping all at once at turn end — and so something is
    visible even if the SDK never emits a ResultMessage.
    """

    def __init__(
        self,
        channel: discord.abc.Messageable,
        *,
        chunk_size: int = SAFE_CHUNK,
        min_edit_interval: float = 1.2,
    ) -> None:
        self._channel = channel
        self._chunk_size = chunk_size
        self._min_edit_interval = min_edit_interval
        self._lock = asyncio.Lock()
        # Current "live" message + its content so far.
        self._current: discord.Message | None = None
        self._current_text: str = ""
        # Pending text not yet pushed to Discord.
        self._buffer: str = ""
        self._last_edit_at: float = 0.0
        self._closed = False

    async def append(self, text: str) -> None:
        """Add text. Posts/edits if rate budget allows; else just buffers."""
        if not text or self._closed:
            return
        async with self._lock:
            self._buffer += text
            now = time.monotonic()
            # Flush if no current message yet, or enough time has passed,
            # or we have enough buffered to start a new chunk.
            if self._current is None or (now - self._last_edit_at) >= self._min_edit_interval:
                await self._flush_locked()
            elif len(self._current_text) + len(self._buffer) >= self._chunk_size:
                await self._flush_locked()

    async def finalize(self, footer: str | None = None) -> None:
        """Flush any buffered text and append the footer."""
        async with self._lock:
            self._closed = True
            await self._flush_locked(force=True)
            if footer:
                # Try to append footer to last message if it fits, else send standalone.
                if (
                    self._current is not None
                    and len(self._current_text) + len(footer) + 1 <= self._chunk_size
                ):
                    new_text = self._current_text + "\n" + footer
                    try:
                        await self._current.edit(content=new_text)
                        self._current_text = new_text
                    except discord.HTTPException as exc:
                        logger.warning("footer edit failed: %s", exc)
                        await self._send_safe(footer)
                else:
                    await self._send_safe(footer)

    async def _flush_locked(self, *, force: bool = False) -> None:
        """Push as much of self._buffer as we can. Caller must hold self._lock."""
        if not self._buffer:
            return

        # If there's no current message, create one.
        if self._current is None:
            head, rest = self._take(self._buffer, self._chunk_size)
            self._buffer = rest
            msg = await self._send_safe(head)
            if msg is not None:
                self._current = msg
                self._current_text = head
                self._last_edit_at = time.monotonic()

        # If we still have buffer, decide: edit current or spill to new message.
        while self._buffer:
            if self._current is None:
                # send_safe failed — stop trying for now
                return
            available = self._chunk_size - len(self._current_text)
            if available > 0:
                fit, overflow = self._take(self._buffer, available)
                new_text = self._current_text + fit
                try:
                    await self._current.edit(content=new_text)
                    self._current_text = new_text
                    self._last_edit_at = time.monotonic()
                    self._buffer = overflow
                except discord.HTTPException as exc:
                    logger.warning("edit failed (%s), spilling to new message", exc)
                    available = 0
            if available == 0:
                # Current is full → start a new message
                head, rest = self._take(self._buffer, self._chunk_size)
                self._buffer = rest
                msg = await self._send_safe(head)
                if msg is None:
                    return
                self._current = msg
                self._current_text = head
                self._last_edit_at = time.monotonic()
            # If we processed something but didn't fill the message, and there's
            # no more buffer, we're done.
            if force and not self._buffer:
                break

    async def _send_safe(self, content: str) -> discord.Message | None:
        if not content:
            return None
        try:
            return await self._channel.send(content)
        except discord.HTTPException as exc:
            logger.warning("send failed: %s", exc)
            return None

    @staticmethod
    def _take(text: str, n: int) -> tuple[str, str]:
        """Take up to n chars from text, preferring a clean boundary."""
        if len(text) <= n:
            return text, ""
        # Prefer paragraph > line > sentence > word > hard
        window = text[:n]
        for sep in ("\n\n", "\n", ". ", " "):
            idx = window.rfind(sep)
            if idx > n // 2:
                return text[: idx + len(sep)], text[idx + len(sep) :]
        return text[:n], text[n:]


class TypingHeartbeat:
    """Async context manager that holds the channel typing indicator.

    Uses discord.py 2.x's `channel.typing()` which auto-refreshes internally
    (the 10s expiry is handled by the context manager).
    """

    def __init__(self, channel: discord.abc.Messageable) -> None:
        self._channel = channel
        self._cm = None  # type: ignore[assignment]

    async def __aenter__(self) -> "TypingHeartbeat":
        try:
            self._cm = self._channel.typing()
            await self._cm.__aenter__()
        except discord.HTTPException as exc:
            logger.warning("typing() failed: %s", exc)
            self._cm = None
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self._cm is not None:
            try:
                await self._cm.__aexit__(exc_type, exc, tb)
            except Exception as e:  # noqa: BLE001
                logger.debug("typing() exit failed: %s", e)
