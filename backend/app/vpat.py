"""Builds a Digital VPAT / Accessibility Conformance Report (ACR).

Where `conformance.py` summarizes only the criteria axe-core actually
exercised, this walks the *full* WCAG 2.2 Level A + AA catalog and produces a
standard VPAT report table: one row per success criterion, each assigned a
conformance level (Supports / Partially Supports / Does Not Support /
Not Evaluated) with remarks.

Integrity note: this is generated from a single automated scan of one page.
Automated testing can only cover a subset of the criteria, so any criterion
axe cannot evaluate is reported as "Not Evaluated" -- never silently assumed
to conform. This honesty is the whole point of shipping a real VPAT rather
than a green checkmark.
"""
from __future__ import annotations

import html
from datetime import datetime, timezone

from .wcag_catalog import WCAG_22_A_AA, sc_sort_key

# Standard VPAT 2.x conformance terms, plus "Not Evaluated" for criteria
# outside the reach of automated tooling (disclosed, never inferred).
SUPPORTS = "Supports"
PARTIALLY = "Partially Supports"
DOES_NOT = "Does Not Support"
NOT_EVALUATED = "Not Evaluated"

_AUTOMATED_NOTE = "Based on automated testing only; manual evaluation still required to claim conformance."
_NOT_TESTABLE_NOTE = (
    "Not determinable by automated tooling. Requires manual evaluation "
    "(assistive-technology, keyboard, and human judgement)."
)


def _by_number(conformance_rows: list[dict]) -> dict[str, dict]:
    """Index conformance rows by SC number ('1.4.3') parsed from the label."""
    out: dict[str, dict] = {}
    for row in conformance_rows:
        num = row.get("criterion", "").split(" ", 1)[0]
        if num:
            out[num] = row
    return out


def _row_for(criterion, conf: dict | None) -> dict:
    num, title, level = criterion.num, criterion.title, criterion.level
    if conf is None:
        return {
            "num": num,
            "title": title,
            "level": level,
            "conformance": NOT_EVALUATED,
            "remarks": _NOT_TESTABLE_NOTE,
        }

    failed = conf.get("failed_rules", [])
    passed = conf.get("passed_rules", [])
    review = conf.get("review_rules", [])

    if failed and passed:
        level_out, remark = PARTIALLY, f"Automated checks found failures ({', '.join(failed)}) alongside passing checks."
    elif failed:
        level_out, remark = DOES_NOT, f"Automated checks found failures: {', '.join(failed)}."
    elif review and not passed:
        level_out, remark = NOT_EVALUATED, "Only manual-review checks apply; automated tooling could not determine conformance."
    elif review:
        level_out, remark = PARTIALLY, f"Passed automated checks, but items need manual review ({', '.join(review)})."
    else:
        level_out, remark = SUPPORTS, f"Passed automated checks ({', '.join(passed)}). {_AUTOMATED_NOTE}"

    return {"num": num, "title": title, "level": level, "conformance": level_out, "remarks": remark}


def build_vpat(conformance_rows: list[dict]) -> list[dict]:
    """Return one VPAT row per WCAG 2.2 A/AA success criterion."""
    conf_by_num = _by_number(conformance_rows)
    rows = [_row_for(c, conf_by_num.get(c.num)) for c in WCAG_22_A_AA]
    return sorted(rows, key=lambda r: sc_sort_key(r["num"]))


def vpat_summary(rows: list[dict]) -> dict[str, int]:
    """Count rows by conformance level for an at-a-glance header."""
    out = {SUPPORTS: 0, PARTIALLY: 0, DOES_NOT: 0, NOT_EVALUATED: 0}
    for r in rows:
        out[r["conformance"]] = out.get(r["conformance"], 0) + 1
    return out


# ── Digital VPAT (HTML) export ──────────────────────────────────────────────

_CONF_CLASS = {
    SUPPORTS: "c-supports",
    PARTIALLY: "c-partial",
    DOES_NOT: "c-fail",
    NOT_EVALUATED: "c-na",
}


def _table(rows: list[dict], level: str) -> str:
    body = []
    for r in (x for x in rows if x["level"] == level):
        cls = _CONF_CLASS.get(r["conformance"], "")
        body.append(
            "<tr>"
            f'<th scope="row">{html.escape(r["num"])} {html.escape(r["title"])}</th>'
            f'<td class="{cls}">{html.escape(r["conformance"])}</td>'
            f'<td>{html.escape(r["remarks"])}</td>'
            "</tr>"
        )
    return "\n".join(body)


def render_vpat_html(
    *,
    url: str,
    page_title: str,
    scanned_at: datetime | None,
    rows: list[dict],
) -> str:
    """Render a standalone, self-contained, accessible HTML VPAT document."""
    when = (scanned_at or datetime.now(timezone.utc)).strftime("%Y-%m-%d %H:%M UTC")
    summary = vpat_summary(rows)
    safe_url = html.escape(url)
    safe_title = html.escape(page_title or url)
    summary_line = " · ".join(f"{v} {k}" for k, v in summary.items())

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Accessibility Conformance Report (VPAT) — {safe_title}</title>
<style>
  :root {{ color-scheme: light dark; }}
  body {{ font-family: system-ui, -apple-system, "Segoe UI", sans-serif; line-height: 1.6; max-width: 1000px; margin: 2rem auto; padding: 0 1.25rem; color: #16130e; background: #fff; }}
  h1 {{ font-size: 1.6rem; }} h2 {{ font-size: 1.2rem; margin-top: 2.5rem; }}
  caption {{ text-align: left; font-weight: 700; padding: 0.5rem 0; }}
  table {{ width: 100%; border-collapse: collapse; margin-bottom: 1.5rem; }}
  th, td {{ border: 1px solid #c9c2b5; padding: 0.5rem 0.65rem; text-align: left; vertical-align: top; font-size: 0.92rem; }}
  thead th {{ background: #f3ece0; }}
  tbody th {{ font-weight: 600; width: 34%; }}
  td.c-supports {{ color: #0f6e39; font-weight: 700; }}
  td.c-partial  {{ color: #8a5a00; font-weight: 700; }}
  td.c-fail     {{ color: #a3232b; font-weight: 700; }}
  td.c-na       {{ color: #5a5348; font-weight: 700; }}
  .meta {{ background: #faf8f4; border: 1px solid #e0d4c0; border-radius: 8px; padding: 1rem 1.25rem; }}
  .meta dt {{ font-weight: 700; }} .meta dd {{ margin: 0 0 0.5rem; }}
  .note {{ font-size: 0.85rem; color: #5a5348; }}
  .cta {{ background: #fff9d6; border: 1px solid #ffd966; border-radius: 8px; padding: 1rem 1.25rem; margin: 1.5rem 0; }}
  .cta a {{ color: #6b4e00; font-weight: 700; }}
</style>
</head>
<body>
<h1>Accessibility Conformance Report</h1>
<p class="note">Based on the VPAT&reg; 2.5 format (ITI). WCAG 2.2 Level A &amp; AA.</p>

<dl class="meta">
  <dt>Page evaluated</dt><dd><a href="{safe_url}">{safe_url}</a></dd>
  <dt>Page title</dt><dd>{safe_title}</dd>
  <dt>Date</dt><dd>{when}</dd>
  <dt>Evaluation method</dt><dd>Automated scan (headless Chromium + axe-core 4.10.2), single page.</dd>
  <dt>Standard</dt><dd>WCAG 2.2, conformance levels A and AA.</dd>
  <dt>Summary</dt><dd>{html.escape(summary_line)}</dd>
</dl>

<p class="note"><strong>Scope &amp; limitations:</strong> {html.escape(_AUTOMATED_NOTE)}
Criteria marked "{NOT_EVALUATED}" are outside the reach of automated tooling and require manual review; they are not conformance claims.</p>

<p class="cta">This report covers one page, automated checks only. For a conformance report you can stand behind --
full-site coverage, manual keyboard/screen-reader testing, and every criterion marked "{NOT_EVALUATED}" here
actually evaluated -- <a href="https://auto-flow.co">Auto-Flow Automations Inc. offers manual accessibility audits</a>.</p>

<h2>Table 1: Success Criteria, Level A</h2>
<table>
  <caption>WCAG 2.2 Level A</caption>
  <thead><tr><th scope="col">Criteria</th><th scope="col">Conformance Level</th><th scope="col">Remarks and Explanations</th></tr></thead>
  <tbody>
{_table(rows, "A")}
  </tbody>
</table>

<h2>Table 2: Success Criteria, Level AA</h2>
<table>
  <caption>WCAG 2.2 Level AA</caption>
  <thead><tr><th scope="col">Criteria</th><th scope="col">Conformance Level</th><th scope="col">Remarks and Explanations</th></tr></thead>
  <tbody>
{_table(rows, "AA")}
  </tbody>
</table>

<p class="note">Generated by <a href="https://auto-flow.co">Auto-Flow Automations Inc.</a> — scan.auto-flow.co. VPAT&reg; is a registered trademark of the Information Technology Industry Council (ITI).</p>
</body>
</html>
"""
