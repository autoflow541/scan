"""ai_page_review -- AI-assisted judgment for criteria axe can only check
mechanically (alt-text quality, link purpose, heading descriptiveness).
Covers the pure helpers directly and the async orchestration via
asyncio.run() (no pytest-asyncio dependency, matching this codebase's
existing test style of keeping async orchestration thin around pure logic)."""

from __future__ import annotations

import asyncio
import json

import pytest

from app.ai_page_review import (
    build_page_context,
    parse_ai_response,
    run_ai_page_review,
    _is_enabled,
    _resize_for_model,
)


# ── pure helpers ─────────────────────────────────────────────────────────────

def test_build_page_context_strips_blanks_and_bounds_counts():
    ctx = build_page_context(
        headings=["  Intro  ", "", None, "Details"],
        alt_texts=["a photo of a cat", "", "  "],
        link_texts=["Read more", "click here"],
    )
    assert ctx["headings"] == ["Intro", "Details"]
    assert ctx["altTexts"] == ["a photo of a cat"]
    assert ctx["linkTexts"] == ["Read more", "click here"]


def test_build_page_context_caps_each_list():
    ctx = build_page_context(
        headings=[f"h{i}" for i in range(50)],
        alt_texts=[f"a{i}" for i in range(50)],
        link_texts=[f"l{i}" for i in range(50)],
    )
    assert len(ctx["headings"]) == 20
    assert len(ctx["altTexts"]) == 15
    assert len(ctx["linkTexts"]) == 20


def test_build_page_context_truncates_long_items():
    """A real alt text can legitimately run a few hundred characters (a
    thorough logo/banner description) -- must be capped, not sent whole,
    since the schema also asks the model to echo it back verbatim, doubling
    the token cost of an uncapped string."""
    long_alt = "A " * 300  # 600 chars
    ctx = build_page_context(headings=[], alt_texts=[long_alt], link_texts=[])
    assert len(ctx["altTexts"][0]) == 200


def test_parse_ai_response_valid():
    raw = json.dumps({
        "summary": "Mostly fine.",
        "findings": [
            {"criterion": "1.1.1", "verdict": "concern", "subject": "image1.jpg", "detail": "Filename as alt text."},
            {"criterion": "2.4.4", "verdict": "ok", "subject": "View the 2026 accessibility report", "detail": "Clear out of context."},
        ],
    })
    parsed = parse_ai_response(raw)
    assert parsed["summary"] == "Mostly fine."
    assert len(parsed["findings"]) == 2


def test_parse_ai_response_drops_malformed_findings_but_keeps_valid_ones():
    raw = json.dumps({
        "summary": "s",
        "findings": [
            {"criterion": "1.1.1", "verdict": "concern", "subject": "x", "detail": "d"},
            {"criterion": "9.9.9", "verdict": "concern", "subject": "bad criterion", "detail": "d"},
            {"criterion": "2.4.4", "verdict": "maybe", "subject": "bad verdict", "detail": "d"},
            "not even a dict",
        ],
    })
    parsed = parse_ai_response(raw)
    assert len(parsed["findings"]) == 1
    assert parsed["findings"][0]["subject"] == "x"


def test_parse_ai_response_invalid_json_returns_none():
    assert parse_ai_response("not json") is None
    assert parse_ai_response("") is None


def test_parse_ai_response_missing_findings_key_returns_none():
    assert parse_ai_response(json.dumps({"summary": "s"})) is None


def test_is_enabled_defaults_off(monkeypatch):
    monkeypatch.delenv("AI_PAGE_REVIEW", raising=False)
    assert _is_enabled() is False


def test_is_enabled_recognises_on_values(monkeypatch):
    for v in ("on", "ON", "1", "true", "True"):
        monkeypatch.setenv("AI_PAGE_REVIEW", v)
        assert _is_enabled() is True
    monkeypatch.setenv("AI_PAGE_REVIEW", "off")
    assert _is_enabled() is False


def _make_jpeg(width, height):
    from PIL import Image
    import io
    img = Image.new("RGB", (width, height), color=(120, 130, 140))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_resize_shrinks_wide_screenshot():
    from PIL import Image
    import io
    original = _make_jpeg(1280, 2000)  # a real full-page screenshot shape
    resized = _resize_for_model(original)
    img = Image.open(io.BytesIO(resized))
    assert img.width == 900
    assert img.height == round(2000 * 900 / 1280)
    assert len(resized) < len(original)


def test_resize_leaves_already_small_screenshot_unchanged():
    original = _make_jpeg(600, 400)
    assert _resize_for_model(original) == original


def test_resize_falls_back_to_original_on_bad_input():
    garbage = b"not an image"
    assert _resize_for_model(garbage) == garbage


# ── async orchestration ──────────────────────────────────────────────────────

def test_disabled_by_default_returns_none_without_touching_network(monkeypatch):
    monkeypatch.delenv("AI_PAGE_REVIEW", raising=False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-unused")
    result = asyncio.run(run_ai_page_review(b"fakejpeg", ["Intro"], ["a photo"], ["Read more"]))
    assert result is None


def test_enabled_but_no_api_key_returns_none(monkeypatch):
    monkeypatch.setenv("AI_PAGE_REVIEW", "on")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    result = asyncio.run(run_ai_page_review(b"fakejpeg", ["Intro"], ["a photo"], ["Read more"]))
    assert result is None


def test_no_screenshot_returns_none(monkeypatch):
    monkeypatch.setenv("AI_PAGE_REVIEW", "on")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-unused")
    result = asyncio.run(run_ai_page_review(None, ["Intro"], ["a photo"], ["Read more"]))
    assert result is None


def test_empty_page_context_returns_none_without_a_call(monkeypatch):
    """Nothing to judge -- must not spend an API call on an empty context."""
    monkeypatch.setenv("AI_PAGE_REVIEW", "on")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-unused")
    result = asyncio.run(run_ai_page_review(b"fakejpeg", [], [], []))
    assert result is None


class _FakeUsage:
    def __init__(self, inp, out):
        self.input_tokens = inp
        self.output_tokens = out


class _FakeTextBlock:
    type = "text"

    def __init__(self, text):
        self.text = text


class _FakeResponse:
    def __init__(self, payload, inp=500, out=100, stop_reason="end_turn"):
        self.stop_reason = stop_reason
        self.content = [_FakeTextBlock(json.dumps(payload))]
        self.usage = _FakeUsage(inp, out)


class _FakeMessages:
    def __init__(self, response=None, exc=None, delay=0.0):
        self._response = response
        self._exc = exc
        self._delay = delay

    async def create(self, **kwargs):
        if self._delay:
            await asyncio.sleep(self._delay)
        if self._exc:
            raise self._exc
        return self._response


class _FakeAsyncAnthropicClient:
    def __init__(self, response=None, exc=None, delay=0.0, api_key=None):
        self.messages = _FakeMessages(response=response, exc=exc, delay=delay)


def _enable(monkeypatch, client):
    monkeypatch.setenv("AI_PAGE_REVIEW", "on")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-unused")
    import anthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic", lambda api_key=None: client)


def test_successful_call_returns_findings_and_disclaimer(monkeypatch):
    payload = {
        "summary": "One weak alt text.",
        "findings": [{"criterion": "1.1.1", "verdict": "concern", "subject": "IMG_4821.jpg", "detail": "Filename, not a description."}],
    }
    _enable(monkeypatch, _FakeAsyncAnthropicClient(response=_FakeResponse(payload)))

    result = asyncio.run(run_ai_page_review(b"fakejpeg", ["Intro"], ["IMG_4821.jpg"], ["Read more"]))

    assert result is not None
    assert result["summary"] == "One weak alt text."
    assert len(result["findings"]) == 1
    assert "disclaimer" in result
    assert result["inputTokens"] == 500 and result["outputTokens"] == 100


def test_api_failure_degrades_to_none(monkeypatch):
    _enable(monkeypatch, _FakeAsyncAnthropicClient(exc=RuntimeError("network down")))
    result = asyncio.run(run_ai_page_review(b"fakejpeg", ["Intro"], ["a photo"], ["Read more"]))
    assert result is None


def test_refusal_returns_none(monkeypatch):
    payload = {"summary": "", "findings": []}
    _enable(monkeypatch, _FakeAsyncAnthropicClient(response=_FakeResponse(payload, stop_reason="refusal")))
    result = asyncio.run(run_ai_page_review(b"fakejpeg", ["Intro"], ["a photo"], ["Read more"]))
    assert result is None


def test_slow_call_times_out_and_returns_none(monkeypatch):
    import app.ai_page_review as m
    monkeypatch.setattr(m, "_CALL_TIMEOUT_S", 0.05)
    _enable(monkeypatch, _FakeAsyncAnthropicClient(
        response=_FakeResponse({"summary": "", "findings": []}), delay=1.0,
    ))
    result = asyncio.run(run_ai_page_review(b"fakejpeg", ["Intro"], ["a photo"], ["Read more"]))
    assert result is None


def test_explicit_timeout_s_overrides_the_default(monkeypatch):
    """scanner.py passes a dynamically-computed remaining-budget timeout;
    that value must actually govern the call, not the fixed default."""
    _enable(monkeypatch, _FakeAsyncAnthropicClient(
        response=_FakeResponse({"summary": "", "findings": []}), delay=0.2,
    ))
    # Default _CALL_TIMEOUT_S (18s) would easily cover a 0.2s delay; an
    # explicit 0.05s override must NOT, proving the parameter is honoured.
    result = asyncio.run(run_ai_page_review(
        b"fakejpeg", ["Intro"], ["a photo"], ["Read more"], timeout_s=0.05,
    ))
    assert result is None


def test_too_little_budget_left_skips_without_a_call(monkeypatch):
    """A page that took most of the scan's budget to navigate/settle should
    skip the AI call outright rather than attempt a doomed-to-timeout one."""
    calls = {"n": 0}

    class _CountingMessages:
        async def create(self, **kwargs):
            calls["n"] += 1
            return _FakeResponse({"summary": "", "findings": []})

    class _CountingClient:
        def __init__(self, api_key=None):
            self.messages = _CountingMessages()

    monkeypatch.setenv("AI_PAGE_REVIEW", "on")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-unused")
    import anthropic
    monkeypatch.setattr(anthropic, "AsyncAnthropic", _CountingClient)

    result = asyncio.run(run_ai_page_review(
        b"fakejpeg", ["Intro"], ["a photo"], ["Read more"], timeout_s=1.0,
    ))
    assert result is None
    assert calls["n"] == 0  # never even attempted the call
