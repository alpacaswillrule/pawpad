"""Spend ledger + hard-pause on budget hit.

Tracks token usage per session, converts to USD using Anthropic pricing
(model-dependent), enforces a daily cap with hard-pause on hit. Ledger
persisted to ~/.pawpad/budget.sqlite so restarts don't lose state.

Warning thresholds posted to #jojo-audit at 80% / 95% / 100% of daily cap.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

LEDGER_PATH = Path("~/.pawpad/budget.sqlite").expanduser()


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
    """Daily spend tracker + cap enforcer."""

    def __init__(self, default_daily_cap_usd: float = 500.0) -> None:
        self.default_daily_cap_usd = default_daily_cap_usd
        self._db: sqlite3.Connection | None = None

    def open(self) -> None:
        LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(LEDGER_PATH)
        # TODO: create tables
        #   turns(id, channel_id, model, in_tok, out_tok, cache_r, cache_w, usd, ts)
        #   caps(date, usd_cap)
        raise NotImplementedError

    def set_daily_cap(self, usd: float) -> None:
        # TODO: upsert into caps for today's date
        raise NotImplementedError

    def record_turn(self, turn: TurnCost) -> None:
        # TODO: insert into turns
        raise NotImplementedError

    def spent_today(self) -> float:
        # TODO: SUM(usd) WHERE ts >= start of VM-local day
        raise NotImplementedError

    def spent_by_channel_today(self) -> dict[int, float]:
        # TODO
        raise NotImplementedError

    def is_over_cap(self) -> bool:
        return self.spent_today() >= self._daily_cap()

    def _daily_cap(self) -> float:
        # TODO: SELECT from caps WHERE date = today, fallback to default
        raise NotImplementedError

    @staticmethod
    def price_usd(model: str, in_tok: int, out_tok: int, cache_r: int, cache_w: int) -> float:
        # TODO: pricing table per Anthropic model
        #   Opus 4.7: $15/M in, $75/M out  (placeholder — verify current pricing)
        #   Sonnet 4.6: $3/M in, $15/M out
        #   Haiku 4.5: $1/M in, $5/M out
        # cache reads ~10% of input, cache writes ~125% of input
        raise NotImplementedError
