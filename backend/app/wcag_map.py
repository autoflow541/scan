"""Maps axe-core's `wcagNNN` tags to human-readable WCAG success criterion labels.

axe-core tags each rule with a `wcag2a`/`wcag2aa`/`wcag21aa`/`wcag22aa`-style
*level* tag (which we use to select what to run) plus a specific `wcagNNN`
*criterion* tag where NNN is the SC number with dots removed (e.g. 1.4.3 ->
"wcag143", 2.4.11 -> "wcag2411"). This table is built once from the published
WCAG 2.2 success criteria list, not generated at runtime.
"""
from __future__ import annotations

# Level tags that describe a *category* rather than one specific criterion --
# never treated as the "primary" criterion for an issue.
_LEVEL_TAGS = {
    "wcag2a", "wcag2aa", "wcag2aaa",
    "wcag21a", "wcag21aa", "wcag21aaa",
    "wcag22a", "wcag22aa", "wcag22aaa",
    "best-practice", "cat.aria", "cat.color", "cat.forms", "cat.keyboard",
    "cat.language", "cat.name-role-value", "cat.parsing", "cat.semantics",
    "cat.sensory-and-visual-cues", "cat.structure", "cat.tables",
    "cat.text-alternatives", "cat.time-and-media", "experimental",
}

WCAG_TAG_LABELS: dict[str, str] = {
    "wcag111": "1.1.1 Non-text Content",
    "wcag121": "1.2.1 Audio-only and Video-only (Prerecorded)",
    "wcag122": "1.2.2 Captions (Prerecorded)",
    "wcag123": "1.2.3 Audio Description or Media Alternative (Prerecorded)",
    "wcag124": "1.2.4 Captions (Live)",
    "wcag125": "1.2.5 Audio Description (Prerecorded)",
    "wcag131": "1.3.1 Info and Relationships",
    "wcag132": "1.3.2 Meaningful Sequence",
    "wcag133": "1.3.3 Sensory Characteristics",
    "wcag134": "1.3.4 Orientation",
    "wcag135": "1.3.5 Identify Input Purpose",
    "wcag141": "1.4.1 Use of Color",
    "wcag142": "1.4.2 Audio Control",
    "wcag143": "1.4.3 Contrast (Minimum)",
    "wcag144": "1.4.4 Resize Text",
    "wcag145": "1.4.5 Images of Text",
    "wcag1410": "1.4.10 Reflow",
    "wcag1411": "1.4.11 Non-text Contrast",
    "wcag1412": "1.4.12 Text Spacing",
    "wcag1413": "1.4.13 Content on Hover or Focus",
    "wcag211": "2.1.1 Keyboard",
    "wcag212": "2.1.2 No Keyboard Trap",
    "wcag214": "2.1.4 Character Key Shortcuts",
    "wcag221": "2.2.1 Timing Adjustable",
    "wcag222": "2.2.2 Pause, Stop, Hide",
    "wcag231": "2.3.1 Three Flashes or Below Threshold",
    "wcag241": "2.4.1 Bypass Blocks",
    "wcag242": "2.4.2 Page Titled",
    "wcag243": "2.4.3 Focus Order",
    "wcag244": "2.4.4 Link Purpose (In Context)",
    "wcag245": "2.4.5 Multiple Ways",
    "wcag246": "2.4.6 Headings and Labels",
    "wcag247": "2.4.7 Focus Visible",
    "wcag2411": "2.4.11 Focus Not Obscured (Minimum)",
    "wcag251": "2.5.1 Pointer Gestures",
    "wcag252": "2.5.2 Pointer Cancellation",
    "wcag253": "2.5.3 Label in Name",
    "wcag254": "2.5.4 Motion Actuation",
    "wcag257": "2.5.7 Dragging Movements",
    "wcag258": "2.5.8 Target Size (Minimum)",
    "wcag311": "3.1.1 Language of Page",
    "wcag312": "3.1.2 Language of Parts",
    "wcag321": "3.2.1 On Focus",
    "wcag322": "3.2.2 On Input",
    "wcag326": "3.2.6 Consistent Help",
    "wcag331": "3.3.1 Error Identification",
    "wcag332": "3.3.2 Labels or Instructions",
    "wcag337": "3.3.7 Redundant Entry",
    "wcag338": "3.3.8 Accessible Authentication (Minimum)",
    "wcag411": "4.1.1 Parsing",
    "wcag412": "4.1.2 Name, Role, Value",
    "wcag413": "4.1.3 Status Messages",
}


def primary_criterion(tags: list[str]) -> str | None:
    """Pick the most specific wcagNNN criterion tag present (skipping level/
    category tags) and map it to a human-readable label. Returns None if no
    specific criterion tag is present.
    """
    for tag in tags:
        if tag in _LEVEL_TAGS or not tag.startswith("wcag"):
            continue
        label = WCAG_TAG_LABELS.get(tag)
        if label:
            return label
    return None
