from __future__ import annotations

import cv2
import numpy as np

from color_space_analyzer import (
    ColorPalette,
    extract_crop_features,
    hex_to_rgb,
    match_color_lab,
    match_color_rgb,
    match_color_ycrcb,
    rgb_to_lab,
    rgb_to_ycrcb,
)


def test_hex_to_rgb():
    assert hex_to_rgb("#FFFFFF") == (255, 255, 255)
    assert hex_to_rgb("000000") == (0, 0, 0)
    assert hex_to_rgb("#C91A09") == (201, 26, 9)


def test_rgb_to_ycrcb():
    y, cr, cb = rgb_to_ycrcb(255, 255, 255)
    assert round(y) == 255
    assert round(cr) == 128
    assert round(cb) == 128

    # Pure green: Y should be moderate, Cr low, Cb low
    yg, crg, cbg = rgb_to_ycrcb(0, 255, 0)
    assert round(yg) == 150
    assert crg < 100
    assert cbg < 100


def test_color_matching_synthetic():
    palette = ColorPalette()
    # Test green piece: (35, 120, 65)
    rgb = (35.0, 120.0, 65.0)
    ycrcb = rgb_to_ycrcb(*rgb)
    lab = rgb_to_lab(*rgb)

    matches_rgb = match_color_rgb(rgb, palette)
    matches_ycrcb = match_color_ycrcb(ycrcb, palette)
    matches_lab = match_color_lab(lab, palette)

    assert len(matches_rgb) > 0
    assert len(matches_ycrcb) > 0
    assert len(matches_lab) > 0

    # Top match should be a green variant
    assert "Green" in matches_ycrcb[0].name or "Lime" in matches_ycrcb[0].name


def test_ycrcb_illuminant_tolerance():
    palette = ColorPalette()
    # Test Red in full light vs Red in shadow (reduced luminance)
    red_bright = (201.0, 26.0, 9.0)
    # Shadow drops all channels proportionally
    red_shadow = (100.0, 13.0, 4.0)

    ycrcb_bright = rgb_to_ycrcb(*red_bright)
    ycrcb_shadow = rgb_to_ycrcb(*red_shadow)

    # In YCrCb with low w_y, chroma still identifies Red as top candidate
    matches = match_color_ycrcb(ycrcb_shadow, palette, w_y=0.2)
    assert matches[0].name in ("Red", "Dark Red")


def test_extract_crop_features():
    # Synthetic BGR image (blue brick)
    bgr = np.zeros((100, 100, 3), dtype=np.uint8)
    bgr[:, :] = (191, 85, 0)  # B=191, G=85, R=0 (Blue)
    feat = extract_crop_features(bgr)
    assert feat is not None
    assert feat.rgb[2] > 180  # B channel high in RGB
    assert feat.ycrcb[2] > 150  # Cb channel high for Blue
