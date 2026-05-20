"""Spend ledger + hard-pause on budget hit.

Each turn returns a usage object; we convert to USD via the pricing table,
insert into sqlite, sum for the day, hard-pause if over cap. Warnings posted
at 80% / 95% / 100% of cap.

Ledger schema:
  turns(id INTEGER PK, channel_id INTEGER, model TEXT,
        in_tok INTEGER, out_tok INTEGER, cache_r INTEGER, cache_w INTEGER,
        usd REAL, ts REAL)
  caps(date TEXT PK, usd_cap REAL)
"""

from __future__ import annotations

import logging
import sqlite3
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("pawpad.budget")

DEFAULT_LEDGER = Path("~/.pawpad/budget.sqlite").expanduser()

# Anthropic pricing (USD per million tokens). Verify against
# https://www.anthropic.com/pricing periodically.
# Cache reads are charged at ~10% of base input; cache writes at ~125%.
PRICING: dict[str, dict[str, float]] = {
    # Opus 4.7
    "claude-opus-4-7": {"in": 15.0, "out": 75.0, "cache_r": 1.5, "cache_w": 18.75},
    # Sonnet 4.6
    "claude-sonnet-4-6": {"in": 3.0, "out": 15.0, "cache_r": 0.3, "cache_w": 3.75},
    # Haiku 4.5
    "claude-haiku-4-5": {"in": 1.0, "out": 5.0, "cache_r": 0.1, "cache_w": 1.25},
}
DEFAULT_PRICING = PRICING["claude-opus-4-7"]


@dataclass
class TurnCost:
    channel_id: int
    model: str
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    cache_write_tokens: int
    usd: float


class Budget:
    """Daily spend tracker + cap enforcer. Thread-safe (uses a lock around sqlite)."""

    def __init__(
        self,
        default_daily_cap_usd: float = 500.0,
        ledger_path: Path = DEFAULT_LEDGER,
    ) -> None:
        self.default_daily_cap_usd = default_daily_cap_usd
        self.ledger_path = ledger_path
        self._lock = threading.Lock()
        self._db: sqlite3.Connection | None = None

    # ---- lifecycle ---------------------------------------------------------

    def open(self) -> None:
        self.ledger_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self._open_inner()
        except sqlite3.DatabaseError:
            logger.exception("budget ledger at %s is corrupt; rotating", self.ledger_path)
            stamp = int(time.time())
            self.ledger_path.rename(
                self.ledger_path.with_suffix(f".corrupt.{stamp}.sqlite")
            )
            self._open_inner()

    def _open_inner(self) -> None:
        self._db = sqlite3.connect(
            self.ledger_path,
            check_same_thread=False,
            isolation_level=None,  # autocommit
        )
        self._db.execute("PRAGMA journal_mode=WAL")
        self._db.executescript(
            """
            CREATE TABLE IF NOT EXISTS turns (
                id          INTEGER PRIMARY KEY,
                channel_id  INTEGER NOT NULL,
                model       TEXT NOT NULL,
                in_tok      INTEGER NOT NULL,
                out_tok     INTEGER NOT NULL,
                cache_r     INTEGER NOT NULL,
                cache_w     INTEGER NOT NULL,
                usd         REAL NOT NULL,
                ts          REAL NOT NULL
            );
            CREATE INDEX IF NOT EXISTS turns_ts ON turns(ts);
            CREATE INDEX IF NOT EXISTS turns_channel_ts ON turns(channel_id, ts);

            CREATE TABLE IF NOT EXISTS caps (
                date        TEXT PRIMARY KEY,
                usd_cap     REAL NOT NULL
            );
            """
        )

    def close(self) -> None:
        if self._db is not None:
            self._db.close()
            self._db = None

    def _conn(self) -> sqlite3.Connection:
        if self._db is None:
            raise RuntimeError("Budget.open() not called")
        return self._db

    # ---- pricing -----------------------------------------------------------

    @staticmethod
    def price_usd(
        model: str,
        in_tok: int,
        out_tok: int,
        cache_r: int,
        cache_w: int,
    ) -> float:
        # Anthropic ships model IDs like `claude-opus-4-7-20251022` or
        # `claude-opus-4-7[1m]`. Match on longest prefix in the pricing table.
        m = model or ""
        rates = DEFAULT_PRICING
        for key in sorted(PRICING, key=len, reverse=True):
            if m.startswith(key):
                rates = PRICING[key]
                break
        in_tok = max(0, in_tok)
        out_tok = max(0, out_tok)
        cache_r = max(0, cache_r)
        cache_w = max(0, cache_w)
        return (
            in_tok * rates["in"]
            + out_tok * rates["out"]
            + cache_r * rates["cache_r"]
            + cache_w * rates["cache_w"]
        ) / 1_000_000

    # ---- cap mgmt ----------------------------------------------------------

    def set_daily_cap(self, usd: float, *, date: str | None = None) -> None:
        if usd <= 0:
            raise ValueError("cap must be positive")
        date = date or _today()
        with self._lock:
            self._conn().execute(
                "INSERT INTO caps(date, usd_cap) VALUES(?,?) "
                "ON CONFLICT(date) DO UPDATE SET usd_cap=excluded.usd_cap",
                (date, usd),
            )

    def daily_cap(self, date: str | None = None) -> float:
        date = date or _today()
        with self._lock:
            row = self._conn().execute(
                "SELECT usd_cap FROM caps WHERE date=?", (date,)
            ).fetchone()
        return float(row[0]) if row else self.default_daily_cap_usd

    # ---- record + report ---------------------------------------------------

    def record_turn(self, turn: TurnCost) -> None:
        with self._lock:
            self._conn().execute(
                "INSERT INTO turns(channel_id, model, in_tok, out_tok, cache_r, cache_w, usd, ts) "
                "VALUES(?,?,?,?,?,?,?,?)",
                (
                    turn.channel_id,
                    turn.model,
                    turn.input_tokens,
                    turn.output_tokens,
                    turn.cache_read_tokens,
                    turn.cache_write_tokens,
                    turn.usd,
                    time.time(),
                ),
            )

    def spent_today(self) -> float:
        start = _start_of_day_ts()
        with self._lock:
            row = self._conn().execute(
                "SELECT COALESCE(SUM(usd), 0) FROM turns WHERE ts >= ?", (start,)
            ).fetchone()
        return float(row[0])

    def spent_by_channel_today(self) -> dict[int, float]:
        start = _start_of_day_ts()
        with self._lock:
            rows = self._conn().execute(
                "SELECT channel_id, SUM(usd) FROM turns WHERE ts >= ? GROUP BY channel_id",
                (start,),
            ).fetchall()
        return {int(cid): float(usd) for cid, usd in rows}

    def spent_by_channel_week(self) -> dict[int, float]:
        start = time.time() - 7 * 86400
        with self._lock:
            rows = self._conn().execute(
                "SELECT channel_id, SUM(usd) FROM turns WHERE ts >= ? GROUP BY channel_id",
                (start,),
            ).fetchall()
        return {int(cid): float(usd) for cid, usd in rows}

    # ---- cap enforcement ---------------------------------------------------

    def is_over_cap(self) -> bool:
        return self.spent_today() >= self.daily_cap()

    def remaining_today(self) -> float:
        return max(0.0, self.daily_cap() - self.spent_today())

    def warning_threshold_crossed(
        self, *, spent_before: float, spent_after: float
    ) -> float | None:
        """Return the highest crossed threshold (0.8 / 0.95 / 1.0) or None."""
        cap = self.daily_cap()
        if cap <= 0:
            return None
        for t in (1.0, 0.95, 0.8):
            if spent_before < cap * t <= spent_after:
                return t
        return None


def _today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _start_of_day_ts() -> float:
    now = datetime.now(timezone.utc)
    return datetime(now.year, now.month, now.day, tzinfo=timezone.utc).timestamp()
