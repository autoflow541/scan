"""The complete list of WCAG 2.2 Level A and AA success criteria.

A VPAT / Accessibility Conformance Report must account for *every* applicable
success criterion -- not just the ones an automated tool happened to exercise.
This catalog is the authoritative spine the VPAT builder walks: axe-core
results are mapped onto it, and any criterion axe cannot evaluate is reported
honestly as "Not Evaluated" rather than silently omitted or assumed to pass.

Level AAA criteria are intentionally excluded -- a VPAT's WCAG report tables
cover A and AA; AAA is out of scope for standard conformance claims.
"""
from __future__ import annotations

from typing import NamedTuple


class Criterion(NamedTuple):
    num: str  # e.g. "1.4.3"
    title: str  # e.g. "Contrast (Minimum)"
    level: str  # "A" | "AA"


# Ordered by success-criterion number. Source: WCAG 2.2 Recommendation.
WCAG_22_A_AA: tuple[Criterion, ...] = (
    # ── 1. Perceivable ──
    Criterion("1.1.1", "Non-text Content", "A"),
    Criterion("1.2.1", "Audio-only and Video-only (Prerecorded)", "A"),
    Criterion("1.2.2", "Captions (Prerecorded)", "A"),
    Criterion("1.2.3", "Audio Description or Media Alternative (Prerecorded)", "A"),
    Criterion("1.2.4", "Captions (Live)", "AA"),
    Criterion("1.2.5", "Audio Description (Prerecorded)", "AA"),
    Criterion("1.3.1", "Info and Relationships", "A"),
    Criterion("1.3.2", "Meaningful Sequence", "A"),
    Criterion("1.3.3", "Sensory Characteristics", "A"),
    Criterion("1.3.4", "Orientation", "AA"),
    Criterion("1.3.5", "Identify Input Purpose", "AA"),
    Criterion("1.4.1", "Use of Color", "A"),
    Criterion("1.4.2", "Audio Control", "A"),
    Criterion("1.4.3", "Contrast (Minimum)", "AA"),
    Criterion("1.4.4", "Resize Text", "AA"),
    Criterion("1.4.5", "Images of Text", "AA"),
    Criterion("1.4.10", "Reflow", "AA"),
    Criterion("1.4.11", "Non-text Contrast", "AA"),
    Criterion("1.4.12", "Text Spacing", "AA"),
    Criterion("1.4.13", "Content on Hover or Focus", "AA"),
    # ── 2. Operable ──
    Criterion("2.1.1", "Keyboard", "A"),
    Criterion("2.1.2", "No Keyboard Trap", "A"),
    Criterion("2.1.4", "Character Key Shortcuts", "A"),
    Criterion("2.2.1", "Timing Adjustable", "A"),
    Criterion("2.2.2", "Pause, Stop, Hide", "A"),
    Criterion("2.3.1", "Three Flashes or Below Threshold", "A"),
    Criterion("2.4.1", "Bypass Blocks", "A"),
    Criterion("2.4.2", "Page Titled", "A"),
    Criterion("2.4.3", "Focus Order", "A"),
    Criterion("2.4.4", "Link Purpose (In Context)", "A"),
    Criterion("2.4.5", "Multiple Ways", "AA"),
    Criterion("2.4.6", "Headings and Labels", "AA"),
    Criterion("2.4.7", "Focus Visible", "AA"),
    Criterion("2.4.11", "Focus Not Obscured (Minimum)", "AA"),
    Criterion("2.5.1", "Pointer Gestures", "A"),
    Criterion("2.5.2", "Pointer Cancellation", "A"),
    Criterion("2.5.3", "Label in Name", "A"),
    Criterion("2.5.4", "Motion Actuation", "A"),
    Criterion("2.5.7", "Dragging Movements", "AA"),
    Criterion("2.5.8", "Target Size (Minimum)", "AA"),
    # ── 3. Understandable ──
    Criterion("3.1.1", "Language of Page", "A"),
    Criterion("3.1.2", "Language of Parts", "AA"),
    Criterion("3.2.1", "On Focus", "A"),
    Criterion("3.2.2", "On Input", "A"),
    Criterion("3.2.3", "Consistent Navigation", "AA"),
    Criterion("3.2.4", "Consistent Identification", "AA"),
    Criterion("3.2.6", "Consistent Help", "A"),
    Criterion("3.3.1", "Error Identification", "A"),
    Criterion("3.3.2", "Labels or Instructions", "A"),
    Criterion("3.3.3", "Error Suggestion", "AA"),
    Criterion("3.3.4", "Error Prevention (Legal, Financial, Data)", "AA"),
    Criterion("3.3.7", "Redundant Entry", "A"),
    Criterion("3.3.8", "Accessible Authentication (Minimum)", "AA"),
    # ── 4. Robust ──
    # 4.1.1 Parsing was removed in WCAG 2.2; not included as a testable row.
    Criterion("4.1.2", "Name, Role, Value", "A"),
    Criterion("4.1.3", "Status Messages", "AA"),
)


def sc_sort_key(num: str) -> tuple[int, ...]:
    """Numeric sort so '1.4.10' follows '1.4.3' rather than preceding it."""
    return tuple(int(p) for p in num.split("."))
