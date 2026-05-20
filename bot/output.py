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


class TypingHeartbeat:
    """Context manager that keeps the typing indicator alive for long turns.

    Discord's typing indicator only lasts ~10 seconds. We refresh every 8s.
    """

    def __init__(self, channel: discord.abc.Messageable) -> None:
        self._channel = channel
        self._task: asyncio.Task | None = None
        self._stop = asyncio.Event()

    async def __aenter__(self) -> "TypingHeartbeat":
        self._task = asyncio.create_task(self._loop())
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        self._stop.set()
        if self._task is not None:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()

    async def _loop(self) -> None:
        try:
            while not self._stop.is_set():
                try:
                    await self._channel.trigger_typing()
                except discord.HTTPException as exc:
                    logger.warning("trigger_typing failed: %s", exc)
                try:
                    await asyncio.wait_for(self._stop.wait(), timeout=8.0)
                except asyncio.TimeoutError:
                    continue
        except asyncio.CancelledError:
            pass
