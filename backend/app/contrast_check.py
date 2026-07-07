"""Resolves axe-core's "incomplete" color-contrast results by measuring the
actual rendered pixels from a screenshot, rather than relying on axe reading
a solid CSS background color.

axe-core's `color-contrast` rule can only compute a ratio when it can read a
plain background color from computed styles. If the background is an image,
a gradient, a canvas, or anything else it can't resolve to one color, axe
marks the element "incomplete" (needs manual review) instead of a pass/fail
-- even though the contrast is fully determinable by just looking at the
rendered page. Since we already capture a full-page screenshot during the
scan, we sample the background pixels behind the text directly and compute
a real WCAG contrast ratio, closing that gap.

Pure/testable math and image-sampling logic lives here; the Playwright-side
orchestration (grabbing computed styles, calling these functions, and
re-shaping axe's result dict) lives in scanner.py.
"""
from __future__ import annotations

from collections import Counter

from PIL import Image

RGB = tuple[float, float, float]


def _linearize(channel: float) -> float:
    c = channel / 255
    return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4


def relative_luminance(rgb: RGB) -> float:
    r, g, b = rgb
    return 0.2126 * _linearize(r) + 0.7152 * _linearize(g) + 0.0722 * _linearize(b)


def contrast_ratio(rgb1: RGB, rgb2: RGB) -> float:
    l1, l2 = relative_luminance(rgb1), relative_luminance(rgb2)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def required_ratio(font_size_px: float, font_weight: int) -> float:
    """WCAG 1.4.3: 3:1 for 'large' text (>=24px, or >=18.66px and bold), else 4.5:1."""
    is_large = font_size_px >= 24 or (font_size_px >= 18.66 and font_weight >= 700)
    return 3.0 if is_large else 4.5


def sample_background_color(image: Image.Image, bbox: dict, text_rgb: RGB) -> RGB | None:
    """Most common pixel color within `bbox`, excluding colors close to the
    known text color (those pixels are likely glyph strokes, not background).
    Returns None if the region is empty/out of bounds.
    """
    left = max(0, int(bbox["x"]))
    top = max(0, int(bbox["y"]))
    right = min(image.width, left + max(1, int(bbox["width"])))
    bottom = min(image.height, top + max(1, int(bbox["height"])))
    if right <= left or top >= bottom:
        return None

    crop = image.crop((left, top, right, bottom)).convert("RGB")
    counts = Counter(crop.getdata())
    if not counts:
        return None

    def is_close(c: RGB, ref: RGB, tol: int = 40) -> bool:
        return all(abs(a - b) <= tol for a, b in zip(c, ref))

    background_only = {c: n for c, n in counts.items() if not is_close(c, tuple(text_rgb))}
    pool = background_only or counts
    return max(pool.items(), key=lambda kv: kv[1])[0]


def evaluate_contrast(
    image: Image.Image, bbox: dict, text_rgb: RGB, font_size_px: float, font_weight: int
) -> dict | None:
    """Full pipeline for one node: sample background, compute ratio, compare
    to the applicable threshold. Returns None if the background couldn't be
    sampled (e.g. the bbox is degenerate).
    """
    background = sample_background_color(image, bbox, text_rgb)
    if background is None:
        return None
    ratio = contrast_ratio(tuple(text_rgb), background)
    threshold = required_ratio(font_size_px, font_weight)
    return {"ratio": ratio, "threshold": threshold, "passes": ratio >= threshold, "background": background}
