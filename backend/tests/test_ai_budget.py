"""Tests for ai_budget.py -- the process-wide daily USD ceiling on AI page
review spend (the same class of gap that caused the PDF tool's real ~$1000
surprise bill, fixed here for the free/anonymous scan endpoint)."""

from __future__ import annotations

import time

import pytest

from app.ai_budget import DailyBudget, cost_usd, _budget_from_env


def test_cost_usd_sonnet_pricing():
    # 1M input + 1M output tokens on Sonnet-5: $3 + $15
    assert cost_usd("claude-sonnet-5", 1_000_000, 1_000_000) == pytest.approx(18.0)


def test_cost_usd_unknown_model_falls_back_to_sonnet_class_pricing():
    assert cost_usd("some-future-model", 1_000_000, 0) == pytest.approx(3.0)


def test_cost_usd_zero_tokens_is_free():
    assert cost_usd("claude-sonnet-5", 0, 0) == 0.0


class TestDailyBudget:
    def test_starts_with_zero_spend_and_not_over_budget(self):
        b = DailyBudget(usd_budget=10.0)
        assert b.spent_usd() == 0.0
        assert not b.over_budget()

    def test_record_accumulates_spend(self):
        b = DailyBudget(usd_budget=100.0)
        b.record("claude-sonnet-5", 1_000_000, 0)  # $3
        b.record("claude-sonnet-5", 1_000_000, 0)  # +$3
        assert b.spent_usd() == pytest.approx(6.0)

    def test_over_budget_flips_once_ceiling_is_reached(self):
        b = DailyBudget(usd_budget=5.0)
        assert not b.over_budget()
        b.record("claude-sonnet-5", 1_000_000, 0)  # $3, still under
        assert not b.over_budget()
        b.record("claude-sonnet-5", 1_000_000, 0)  # $6 total, now over
        assert b.over_budget()

    def test_record_returns_the_usd_it_charged(self):
        b = DailyBudget(usd_budget=100.0)
        charged = b.record("claude-sonnet-5", 1_000_000, 0)
        assert charged == pytest.approx(3.0)

    def test_entries_outside_the_window_age_out(self):
        # A near-zero window means "record" immediately falls outside the
        # window on the next check -- proves pruning actually happens rather
        # than spend accumulating forever.
        b = DailyBudget(usd_budget=100.0, window_seconds=0.01)
        b.record("claude-sonnet-5", 1_000_000, 0)
        time.sleep(0.05)
        assert b.spent_usd() == pytest.approx(0.0)

    def test_zero_budget_disables_the_ceiling_rather_than_always_tripping(self):
        """usd_budget=0 is treated as 'no ceiling configured', not 'block
        everything' -- an operator who unsets AI_DAILY_USD_BUDGET shouldn't
        silently kill the feature; _budget_from_env's own default (20.0)
        is what actually protects against that, this just documents the
        DailyBudget-level contract independently."""
        b = DailyBudget(usd_budget=0.0)
        b.record("claude-sonnet-5", 1_000_000, 1_000_000)
        assert not b.over_budget()

    def test_thread_safety_smoke(self):
        import threading
        b = DailyBudget(usd_budget=1_000_000.0)

        def hammer():
            for _ in range(50):
                b.record("claude-sonnet-5", 1000, 0)

        threads = [threading.Thread(target=hammer) for _ in range(8)]
        for t in threads: t.start()
        for t in threads: t.join()
        assert len(b._spend) == 400


def test_budget_from_env_defaults_to_20_dollars(monkeypatch):
    monkeypatch.delenv("AI_DAILY_USD_BUDGET", raising=False)
    assert _budget_from_env() == 20.0


def test_budget_from_env_honours_override(monkeypatch):
    monkeypatch.setenv("AI_DAILY_USD_BUDGET", "5.5")
    assert _budget_from_env() == 5.5


def test_budget_from_env_falls_back_on_garbage(monkeypatch):
    monkeypatch.setenv("AI_DAILY_USD_BUDGET", "not-a-number")
    assert _budget_from_env() == 20.0
