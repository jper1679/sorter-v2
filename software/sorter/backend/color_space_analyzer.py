"""Color space analysis and evaluation for LEGO piece crops.

Provides comparison between standard RGB matching, YCrCb matching (with decoupled
luma/chroma weighting), and CIELAB matching.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import cv2
import numpy as np


# Default BrickLink palette reference mapping
BRICKLINK_PALETTE_REFERENCE: list[dict[str, Any]] = [
    # Neutrals
    {"id": 1, "name": "White", "hex": "#FFFFFF", "is_trans": False},
    {"id": 49, "name": "Very Light Gray", "hex": "#E6E3E0", "is_trans": False},
    {"id": 99, "name": "Very Light Bluish Gray", "hex": "#E6E3DA", "is_trans": False},
    {"id": 9, "name": "Light Gray", "hex": "#9BA19D", "is_trans": False},
    {"id": 86, "name": "Light Bluish Gray", "hex": "#AFB5C7", "is_trans": False},
    {"id": 10, "name": "Dark Gray", "hex": "#6D6E5C", "is_trans": False},
    {"id": 85, "name": "Dark Bluish Gray", "hex": "#6C6E68", "is_trans": False},
    {"id": 11, "name": "Black", "hex": "#05131D", "is_trans": False},
    # Tans & Browns
    {"id": 2, "name": "Tan", "hex": "#E4CD9E", "is_trans": False},
    {"id": 69, "name": "Dark Tan", "hex": "#958A73", "is_trans": False},
    {"id": 90, "name": "Light Nougat", "hex": "#F6D7B3", "is_trans": False},
    {"id": 28, "name": "Nougat", "hex": "#D09168", "is_trans": False},
    {"id": 150, "name": "Medium Nougat", "hex": "#AA7D55", "is_trans": False},
    {"id": 58, "name": "Sand Red", "hex": "#D67572", "is_trans": False},
    {"id": 68, "name": "Dark Orange", "hex": "#A95500", "is_trans": False},
    {"id": 91, "name": "Medium Brown", "hex": "#755945", "is_trans": False},
    {"id": 88, "name": "Reddish Brown", "hex": "#582A12", "is_trans": False},
    {"id": 8, "name": "Brown", "hex": "#583927", "is_trans": False},
    {"id": 120, "name": "Dark Brown", "hex": "#352100", "is_trans": False},
    # Yellows, Oranges & Reds
    {"id": 33, "name": "Light Yellow", "hex": "#FBE696", "is_trans": False},
    {"id": 103, "name": "Bright Light Yellow", "hex": "#FFF03A", "is_trans": False},
    {"id": 166, "name": "Neon Yellow", "hex": "#DCE000", "is_trans": False},
    {"id": 3, "name": "Yellow", "hex": "#F2CD37", "is_trans": False},
    {"id": 105, "name": "Bright Light Orange", "hex": "#F8BB3D", "is_trans": False},
    {"id": 31, "name": "Medium Orange", "hex": "#FFA70B", "is_trans": False},
    {"id": 4, "name": "Orange", "hex": "#FE8A18", "is_trans": False},
    {"id": 5, "name": "Red", "hex": "#C91A09", "is_trans": False},
    {"id": 59, "name": "Dark Red", "hex": "#720E0F", "is_trans": False},
    # Pinks & Purples
    {"id": 23, "name": "Pink", "hex": "#FECCCF", "is_trans": False},
    {"id": 104, "name": "Bright Pink", "hex": "#E4ADC8", "is_trans": False},
    {"id": 47, "name": "Dark Pink", "hex": "#C870A0", "is_trans": False},
    {"id": 71, "name": "Magenta", "hex": "#923978", "is_trans": False},
    {"id": 220, "name": "Coral", "hex": "#FF698F", "is_trans": False},
    {"id": 154, "name": "Lavender", "hex": "#E1D5ED", "is_trans": False},
    {"id": 157, "name": "Medium Lavender", "hex": "#AC78BA", "is_trans": False},
    {"id": 24, "name": "Purple", "hex": "#81007B", "is_trans": False},
    {"id": 89, "name": "Dark Purple", "hex": "#3F3691", "is_trans": False},
    # Blues
    {"id": 152, "name": "Light Aqua", "hex": "#ADC3C0", "is_trans": False},
    {"id": 41, "name": "Aqua", "hex": "#B3D7D1", "is_trans": False},
    {"id": 105, "name": "Bright Light Blue", "hex": "#9FC3E9", "is_trans": False},
    {"id": 42, "name": "Medium Blue", "hex": "#5A93DB", "is_trans": False},
    {"id": 7, "name": "Blue", "hex": "#0055BF", "is_trans": False},
    {"id": 63, "name": "Dark Blue", "hex": "#0A3463", "is_trans": False},
    {"id": 55, "name": "Sand Blue", "hex": "#6074A1", "is_trans": False},
    # Greens
    {"id": 34, "name": "Lime", "hex": "#BBE90B", "is_trans": False},
    {"id": 158, "name": "Yellowish Green", "hex": "#DFEEA5", "is_trans": False},
    {"id": 35, "name": "Light Green", "hex": "#C2DAB8", "is_trans": False},
    {"id": 37, "name": "Medium Green", "hex": "#73DCA1", "is_trans": False},
    {"id": 6, "name": "Green", "hex": "#237841", "is_trans": False},
    {"id": 80, "name": "Dark Green", "hex": "#184632", "is_trans": False},
    {"id": 48, "name": "Sand Green", "hex": "#A0BCAC", "is_trans": False},
    {"id": 39, "name": "Dark Turquoise", "hex": "#008F9B", "is_trans": False},
]


def hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
    clean = hex_code.strip().lstrip("#")
    if len(clean) != 6:
        return (128, 128, 128)
    return (int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))


def rgb_to_ycrcb(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Standard ITU-R BT.601 conversion (same as cv2.COLOR_BGR2YCrCb)."""
    y = 0.299 * r + 0.587 * g + 0.114 * b
    cr = (r - y) * 0.713 + 128.0
    cb = (b - y) * 0.564 + 128.0
    return (y, cr, cb)


def rgb_to_lab(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Convert sRGB (0-255) to CIELAB (D65)."""
    channels = [c / 255.0 for c in (r, g, b)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    rl, gl, bl = lin
    x = (rl * 0.4124 + gl * 0.3576 + bl * 0.1805) / 0.95047
    y = rl * 0.2126 + gl * 0.7152 + bl * 0.0722
    z = (rl * 0.0193 + gl * 0.1192 + bl * 0.9505) / 1.08883
    fx, fy, fz = [t ** (1.0 / 3.0) if t > 0.008856 else 7.787 * t + 16.0 / 116.0 for t in (x, y, z)]
    return (116.0 * fy - 16.0, 500.0 * (fx - fy), 200.0 * (fy - fz))


@dataclass
class PaletteEntry:
    id: int
    name: str
    hex: str
    rgb: tuple[float, float, float]
    ycrcb: tuple[float, float, float]
    lab: tuple[float, float, float]


class ColorPalette:
    def __init__(self, entries: Sequence[dict[str, Any]] | None = None) -> None:
        source = entries if entries is not None else BRICKLINK_PALETTE_REFERENCE
        self.entries: list[PaletteEntry] = []
        self._by_id: dict[int, PaletteEntry] = {}
        self._by_name: dict[str, PaletteEntry] = {}

        for row in source:
            cid = int(row.get("id") or 0)
            name = str(row.get("name") or "")
            hex_val = str(row.get("hex") or row.get("rgb") or "#808080")
            if not hex_val.startswith("#"):
                hex_val = f"#{hex_val}"
            rgb = hex_to_rgb(hex_val)
            r, g, b = float(rgb[0]), float(rgb[1]), float(rgb[2])
            entry = PaletteEntry(
                id=cid,
                name=name,
                hex=hex_val,
                rgb=(r, g, b),
                ycrcb=rgb_to_ycrcb(r, g, b),
                lab=rgb_to_lab(r, g, b),
            )
            self.entries.append(entry)
            self._by_id[cid] = entry
            self._by_name[name.lower()] = entry

    def get_by_id(self, color_id: int | str) -> PaletteEntry | None:
        try:
            return self._by_id.get(int(color_id))
        except (ValueError, TypeError):
            return None

    def get_by_name(self, name: str) -> PaletteEntry | None:
        return self._by_name.get(name.lower().strip())


@dataclass
class ColorMatch:
    color_id: int
    name: str
    hex: str
    distance: float
    confidence: float


@dataclass
class CropFeatures:
    rgb: tuple[float, float, float]
    ycrcb: tuple[float, float, float]
    lab: tuple[float, float, float]
    pixel_count: int


def extract_crop_features(bgr: np.ndarray, center_fraction: float = 0.6) -> CropFeatures | None:
    """Extract representative color in RGB, YCrCb, and CIELAB from a crop."""
    if bgr is None or bgr.size == 0:
        return None

    h, w = bgr.shape[:2]
    bx = int(w * (1.0 - center_fraction) / 2.0)
    by = int(h * (1.0 - center_fraction) / 2.0)
    cropped = bgr[by : h - by, bx : w - bx] if (h - 2 * by >= 2 and w - 2 * bx >= 2) else bgr

    # Downsample for fast robust averaging
    small = cv2.resize(cropped, (48, 48), interpolation=cv2.INTER_AREA)

    # Average in BGR, then convert to RGB
    b, g, r = small.reshape(-1, 3).mean(axis=0)
    rgb = (float(r), float(g), float(b))

    # YCrCb directly from RGB
    ycrcb = rgb_to_ycrcb(rgb[0], rgb[1], rgb[2])

    # CIELAB directly from RGB
    lab = rgb_to_lab(rgb[0], rgb[1], rgb[2])

    return CropFeatures(rgb=rgb, ycrcb=ycrcb, lab=lab, pixel_count=small.shape[0] * small.shape[1])


def match_color_rgb(rgb: tuple[float, float, float], palette: ColorPalette, top_k: int = 3) -> list[ColorMatch]:
    """Nearest neighbor search in sRGB Euclidean distance."""
    scores: list[tuple[float, PaletteEntry]] = []
    r1, g1, b1 = rgb
    for p in palette.entries:
        r2, g2, b2 = p.rgb
        dist = math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2)
        scores.append((dist, p))
    scores.sort(key=lambda s: s[0])

    matches = []
    best_dist = scores[0][0] if scores else 0.0
    for dist, entry in scores[:top_k]:
        conf = math.exp(-dist / 35.0)
        matches.append(
            ColorMatch(
                color_id=entry.id,
                name=entry.name,
                hex=entry.hex,
                distance=round(dist, 2),
                confidence=round(conf, 4),
            )
        )
    return matches


def match_color_ycrcb(
    ycrcb: tuple[float, float, float],
    palette: ColorPalette,
    *,
    w_y: float = 0.25,
    w_chroma: float = 1.0,
    top_k: int = 3,
) -> list[ColorMatch]:
    """Nearest neighbor search in YCrCb with decoupled Luma and Chroma.

    Chrominance (Cr, Cb) represents pigment tone invariant to illumination.
    Luminance (Y) is down-weighted to tolerate shadows, reflections, and
    illumination variations across the channel chute. For neutral colors
    (where chroma is low), luma weight is adaptively restored.
    """
    scores: list[tuple[float, PaletteEntry]] = []
    y1, cr1, cb1 = ycrcb

    # Chroma magnitude relative to neutral gray (128, 128)
    chroma_mag = math.hypot(cr1 - 128.0, cb1 - 128.0)
    # If the piece is near neutral (white, gray, black), increase Y sensitivity
    adaptive_w_y = w_y if chroma_mag > 15.0 else max(w_y, 0.75 - chroma_mag * 0.03)

    for p in palette.entries:
        y2, cr2, cb2 = p.ycrcb
        dist_sq = (
            adaptive_w_y * ((y1 - y2) ** 2)
            + w_chroma * ((cr1 - cr2) ** 2)
            + w_chroma * ((cb1 - cb2) ** 2)
        )
        dist = math.sqrt(dist_sq)
        scores.append((dist, p))
    scores.sort(key=lambda s: s[0])

    matches = []
    for dist, entry in scores[:top_k]:
        conf = math.exp(-dist / 25.0)
        matches.append(
            ColorMatch(
                color_id=entry.id,
                name=entry.name,
                hex=entry.hex,
                distance=round(dist, 2),
                confidence=round(conf, 4),
            )
        )
    return matches


def match_color_lab(lab: tuple[float, float, float], palette: ColorPalette, top_k: int = 3) -> list[ColorMatch]:
    """Nearest neighbor search in CIELAB (Delta E 1976)."""
    scores: list[tuple[float, PaletteEntry]] = []
    l1, a1, b1 = lab
    for p in palette.entries:
        l2, a2, b2 = p.lab
        dist = math.sqrt((l1 - l2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)
        scores.append((dist, p))
    scores.sort(key=lambda s: s[0])

    matches = []
    for dist, entry in scores[:top_k]:
        conf = math.exp(-dist / 20.0)
        matches.append(
            ColorMatch(
                color_id=entry.id,
                name=entry.name,
                hex=entry.hex,
                distance=round(dist, 2),
                confidence=round(conf, 4),
            )
        )
    return matches


@dataclass
class PieceEvaluation:
    uuid: str
    part_id: str | None
    recorded_color_id: str | None
    recorded_color_name: str | None
    crop_count: int
    mean_rgb: tuple[float, float, float]
    mean_ycrcb: tuple[float, float, float]
    mean_lab: tuple[float, float, float]
    rgb_matches: list[ColorMatch]
    ycrcb_matches: list[ColorMatch]
    lab_matches: list[ColorMatch]
    rgb_agrees: bool
    ycrcb_agrees: bool
    lab_agrees: bool
    sample_crop_relpath: str | None = None
