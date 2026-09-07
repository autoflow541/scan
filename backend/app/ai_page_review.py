"""AI-assisted judgment for the WCAG criteria axe-core structurally cannot
evaluate: whether alt text actually DESCRIBES an image (not just that one is
present), whether link text makes sense out of context, whether headings are
genuinely descriptive. axe can only check presence/structure; these are
judgment calls, so they show up as "Not Evaluated" in the VPAT no matter how
thorough the automated pass is.

Design boundaries (read before changing this file):

  1. This NEVER changes vpat.py's conformance verdicts. "Not Evaluated" stays
     "Not Evaluated" in the exported VPAT -- that status is deliberately
     honest (see vpat.py's docstring) and is also the tool's paid-audit
     upsell hook. AI findings are surfaced as a SEPARATE, clearly-labeled
     layer (ScanResult.ai_review) -- assistive, not a conformance claim.
  2. Opt-in, not on by default. /scan is a free, public, unauthenticated,
     rate-limited endpoint -- unlike the PDF tool's user-initiated remediate,
     every anonymous visitor's request would otherwise trigger a paid API
     call. Set AI_PAGE_REVIEW=on to enable.
  3. Never blocks the event loop or blows the scan's timeout budget. Uses the
     ASYNC Anthropic client (run_scan is async; a sync HTTP call here would
     stall every other concurrent scan) and a hard per-call timeout well
     inside main.py's 35s overall scan budget.
  4. Best-effort, like every other enrichment step in scanner.py (contrast
     resolution, mobile axe pass, screenshot capture): any failure here
     degrades gracefully to "unavailable", never fails the scan itself.
  5. One page, one bounded call, Sonnet-tier -- never Opus (STRATEGY lesson
     from the PDF tool's cost incident applies here too).
"""
from __future__ import annotations

import json
import logging
import os

log = logging.getLogger(__name__)

_MODEL = os.environ.get("AI_PAGE_REVIEW_MODEL", "claude-sonnet-5")
_MAX_TOKENS = 1200
_CALL_TIMEOUT_S = 10.0
# Bounds on how much DOM context goes into the prompt -- keeps the request
# small/cheap/fast regardless of how large the scanned page is.
_MAX_HEADINGS = 20
_MAX_IMAGES = 15
_MAX_LINKS = 20

_SCHEMA = {
    "type": "object",
    "properties": {
        "summary": {"type": "string"},
        "findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {
                        "type": "string",
                        "enum": ["1.1.1", "2.4.4", "2.4.6"],
                        "description": "1.1.1 Non-text Content, 2.4.4 Link Purpose, or 2.4.6 Headings and Labels.",
                    },
                    "verdict": {"type": "string", "enum": ["ok", "concern"]},
                    "subject": {"type": "string", "description": "The specific alt text, link text, or heading text being judged, verbatim."},
                    "detail": {"type": "string", "description": "One sentence: why it's fine, or what's wrong."},
                },
                "required": ["criterion", "verdict", "subject", "detail"],
                "additionalProperties": False,
            },
        },
    },
    "required": ["summary", "findings"],
    "additionalProperties": False,
}

_INSTRUCTIONS = """You are reviewing a rendered webpage screenshot for three WCAG success \
criteria that automated tools can only check mechanically, not judge: whether alt text \
actually describes what an image shows (1.1.1 Non-text Content), whether link text makes \
sense out of context rather than "click here" / a bare URL (2.4.4 Link Purpose), and \
whether headings genuinely describe the section that follows rather than being generic or \
duplicated (2.4.6 Headings and Labels).

You are given the render and lists of the page's current alt texts, link texts, and \
headings. For each one you can confidently judge from what's visible, return a finding: \
verdict "ok" if it's genuinely fine, "concern" if it's missing meaning, misleading, or \
generic (e.g. alt="image123.jpg", link text "click here", heading "Section 2"). Skip items \
you can't confidently judge (illegible, ambiguous, or not visible in the render) rather than \
guessing -- do not fabricate a verdict for a subject you're not confident about. Keep each \
detail to one sentence. Only reference items actually in the provided lists."""


def _is_enabled() -> bool:
    return os.environ.get("AI_PAGE_REVIEW", "off").lower() in ("on", "1", "true")


def build_page_context(headings: list[str], alt_texts: list[str], link_texts: list[str]) -> dict:
    """Bound and shape the DOM context sent to the model. Pure function, no
    I/O -- kept separate from extraction (a Playwright eval) so it's directly
    unit-testable."""
    return {
        "headings": [h.strip() for h in headings if h and h.strip()][:_MAX_HEADINGS],
        "altTexts": [a.strip() for a in alt_texts if a and a.strip()][:_MAX_IMAGES],
        "linkTexts": [l.strip() for l in link_texts if l and l.strip()][:_MAX_LINKS],
    }


def _has_any_context(context: dict) -> bool:
    return bool(context.get("headings") or context.get("altTexts") or context.get("linkTexts"))


def parse_ai_response(text: str) -> dict | None:
    """Parse and lightly validate the model's JSON output. Returns None (not
    a raised exception) on any malformed response -- the caller treats that
    the same as any other unavailable-AI outcome."""
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, TypeError):
        return None
    if not isinstance(parsed, dict) or "findings" not in parsed:
        return None
    findings = [
        f for f in parsed.get("findings", [])
        if isinstance(f, dict) and f.get("criterion") in ("1.1.1", "2.4.4", "2.4.6")
        and f.get("verdict") in ("ok", "concern")
    ]
    return {"summary": str(parsed.get("summary", ""))[:500], "findings": findings}


async def run_ai_page_review(
    screenshot_bytes: bytes | None,
    headings: list[str],
    alt_texts: list[str],
    link_texts: list[str],
) -> dict | None:
    """Best-effort AI review of alt-text/link/heading quality. Returns None
    when disabled, unconfigured, or on any failure -- the caller (scanner.py)
    treats None as "no AI review available" and the scan proceeds unaffected.

    Never raises. Bounded to _CALL_TIMEOUT_S so a slow model response can't
    meaningfully eat into main.py's overall scan timeout.
    """
    if not _is_enabled():
        return None
    if screenshot_bytes is None:
        return None
    key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        return None

    context = build_page_context(headings, alt_texts, link_texts)
    if not _has_any_context(context):
        return None

    try:
        import anthropic
    except ImportError:
        log.debug("ai_page_review: anthropic SDK not installed")
        return None

    import asyncio
    import base64

    content: list[dict] = [
        {"type": "text", "text": "Page render:"},
        {
            "type": "image",
            "source": {"type": "base64", "media_type": "image/jpeg",
                       "data": base64.standard_b64encode(screenshot_bytes).decode()},
        },
        {"type": "text", "text": "Page content to judge:\n" + json.dumps(context, ensure_ascii=False)},
    ]

    client = anthropic.AsyncAnthropic(api_key=key)
    try:
        response = await asyncio.wait_for(
            client.messages.create(
                model=_MODEL,
                max_tokens=_MAX_TOKENS,
                system=_INSTRUCTIONS,
                output_config={"format": {"type": "json_schema", "schema": _SCHEMA}},
                messages=[{"role": "user", "content": content}],
            ),
            timeout=_CALL_TIMEOUT_S,
        )
    except asyncio.TimeoutError:
        log.warning("ai_page_review: timed out after %.0fs", _CALL_TIMEOUT_S)
        return None
    except Exception as exc:
        log.warning("ai_page_review: API call failed: %s", exc)
        return None

    if getattr(response, "stop_reason", None) == "refusal":
        return None
    text = next((b.text for b in response.content if getattr(b, "type", None) == "text"), "")
    parsed = parse_ai_response(text)
    if parsed is None:
        return None

    usage = getattr(response, "usage", None)
    parsed["model"] = _MODEL
    parsed["inputTokens"] = int(getattr(usage, "input_tokens", 0) or 0)
    parsed["outputTokens"] = int(getattr(usage, "output_tokens", 0) or 0)
    parsed["disclaimer"] = (
        "AI-assisted preliminary judgment on alt text, link, and heading quality -- "
        "not a conformance determination. Does not affect the VPAT report above."
    )
    return parsed
