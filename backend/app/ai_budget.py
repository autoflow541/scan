"""ai_budget.py — process-wide daily USD ceiling on AI page review spend.

rate_limit.py caps request RATE per IP (5 burst, ~1/30s) but nothing caps
total dollar SPEND: a wide botnet, or one IP grinding at the rate limit's
edge for hours, could still run the AI review path (Sonnet vision + json
schema, real money per call) an unbounded number of times with zero circuit
breaker. The PDF remediation tool hit a real ~$1000 surprise bill from
exactly this class of gap before ai_config.CostTracker was wired in there;
this is the same fix, adapted to a free/anonymous/opt-in single-page
scanner instead of an authenticated per-job pipeline.

In-memory only, same tradeoff rate_limit.py already accepts: single
container instance, resets on restart. That's fine here -- this is a
circuit breaker whose job is "never again silently blow past what we're
willing to spend in a day," not precise accounting (billing truth always
lives in the Anthropic console). AI_DAILY_USD_BUDGET is deliberately a
env-overridable ceiling, not a soft warning.
"""
from __future__ import annotations

import os
import threading
import time

# USD per 1M tokens, (input, output). Mirrors the PDF remediation tool's
# ai_config.PRICING -- duplicated rather than shared since these are two
# separate deployable services with no shared package.
_PRICING: dict[str, tuple[float, float]] = {
    "claude-haiku-4-5-20251001": (1.00, 5.00),
    "claude-sonnet-5": (3.00, 15.00),
    "claude-opus-4-8": (15.00, 75.00),
}
_DEFAULT_PRICE = (3.00, 15.00)  # unknown model -> assume Sonnet-class


def cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    pin, pout = _PRICING.get(model, _DEFAULT_PRICE)
    return (input_tokens / 1_000_000) * pin + (output_tokens / 1_000_000) * pout


class DailyBudget:
    """A rolling-window USD ceiling shared by every AI review call in this
    process. Old entries age out of the window on their own, so long-running
    processes don't need a separate reset job."""

    def __init__(self, usd_budget: float, window_seconds: float = 86400.0):
        self.usd_budget = usd_budget
        self.window_seconds = window_seconds
        self._spend: list[tuple[float, float]] = []  # [(monotonic_ts, usd), ...]
        self._lock = threading.Lock()

    def _prune_locked(self, now: float) -> None:
        cutoff = now - self.window_seconds
        while self._spend and self._spend[0][0] < cutoff:
            self._spend.pop(0)

    def spent_usd(self) -> float:
        with self._lock:
            self._prune_locked(time.monotonic())
            return sum(usd for _, usd in self._spend)

    def over_budget(self) -> bool:
        return self.usd_budget > 0 and self.spent_usd() >= self.usd_budget

    def record(self, model: str, input_tokens: int, output_tokens: int) -> float:
        usd = cost_usd(model, input_tokens, output_tokens)
        with self._lock:
            now = time.monotonic()
            self._prune_locked(now)
            self._spend.append((now, usd))
        return usd


def _budget_from_env() -> float:
    raw = os.environ.get("AI_DAILY_USD_BUDGET", "20.0")
    try:
        return float(raw)
    except ValueError:
        return 20.0


# One process-wide instance, like rate_limit.py's module-level RateLimiter --
# every concurrent scan's AI review call shares this ceiling.
daily_budget = DailyBudget(usd_budget=_budget_from_env())
