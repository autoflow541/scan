from PIL import Image

from app.contrast_check import (
    contrast_ratio,
    evaluate_contrast,
    relative_luminance,
    required_ratio,
    sample_background_color,
)


def test_relative_luminance_white_is_one():
    assert relative_luminance((255, 255, 255)) == 1.0


def test_relative_luminance_black_is_zero():
    assert relative_luminance((0, 0, 0)) == 0.0


def test_contrast_ratio_black_on_white_is_21_to_1():
    assert round(contrast_ratio((0, 0, 0), (255, 255, 255)), 2) == 21.0


def test_contrast_ratio_is_symmetric():
    a = contrast_ratio((0, 0, 0), (128, 128, 128))
    b = contrast_ratio((128, 128, 128), (0, 0, 0))
    assert a == b


def test_required_ratio_normal_text():
    assert required_ratio(font_size_px=16, font_weight=400) == 4.5


def test_required_ratio_large_by_size():
    assert required_ratio(font_size_px=24, font_weight=400) == 3.0


def test_required_ratio_large_by_bold_and_size():
    assert required_ratio(font_size_px=19, font_weight=700) == 3.0


def test_required_ratio_bold_but_too_small_is_not_large():
    assert required_ratio(font_size_px=16, font_weight=700) == 4.5


def test_sample_background_color_solid_fill():
    img = Image.new("RGB", (50, 50), (10, 20, 30))
    bbox = {"x": 0, "y": 0, "width": 50, "height": 50}
    bg = sample_background_color(img, bbox, text_rgb=(255, 255, 255))
    assert bg == (10, 20, 30)


def test_sample_background_color_excludes_text_color():
    img = Image.new("RGB", (10, 10), (200, 200, 200))
    pixels = img.load()
    # Paint a small "glyph" of the text color in one corner -- background color
    # (more common) should still win over the text color.
    for x in range(2):
        for y in range(2):
            pixels[x, y] = (0, 0, 0)
    bbox = {"x": 0, "y": 0, "width": 10, "height": 10}
    bg = sample_background_color(img, bbox, text_rgb=(0, 0, 0))
    assert bg == (200, 200, 200)


def test_sample_background_color_out_of_bounds_returns_none():
    img = Image.new("RGB", (10, 10), (255, 255, 255))
    bbox = {"x": 100, "y": 100, "width": 10, "height": 10}
    assert sample_background_color(img, bbox, text_rgb=(0, 0, 0)) is None


def test_evaluate_contrast_passes_on_good_contrast():
    img = Image.new("RGB", (20, 20), (255, 255, 255))
    result = evaluate_contrast(img, {"x": 0, "y": 0, "width": 20, "height": 20}, (0, 0, 0), 16, 400)
    assert result["passes"] is True
    assert result["ratio"] > 4.5


def test_evaluate_contrast_fails_on_low_contrast():
    img = Image.new("RGB", (20, 20), (210, 210, 210))
    result = evaluate_contrast(img, {"x": 0, "y": 0, "width": 20, "height": 20}, (200, 200, 200), 16, 400)
    assert result["passes"] is False
