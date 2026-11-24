"""Color space analysis and evaluation for LEGO piece crops.

Provides comparison between standard RGB matching, YCrCb matching (with decoupled
luma/chroma weighting), and CIELAB matching.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Optional, Sequence

import cv2
import numpy as np

try:
    from subsystems.classification_channel.crop_quality import pieceMask
except ImportError:
    pieceMask = None

# Comprehensive BrickLink Palette with Solids, Metallics, Pearls, Chromes, and Transparent colors
FULL_BRICKLINK_PALETTE: list[dict[str, Any]] = [
    # --- Neutrals & Grays ---
    {"id": 1, "name": "White", "hex": "#FFFFFF", "is_trans": False},
    {"id": 49, "name": "Very Light Gray", "hex": "#E6E3E0", "is_trans": False},
    {"id": 99, "name": "Very Light Bluish Gray", "hex": "#E6E3DA", "is_trans": False},
    {"id": 9, "name": "Light Gray", "hex": "#9BA19D", "is_trans": False},
    {"id": 86, "name": "Light Bluish Gray", "hex": "#AFB5C7", "is_trans": False},
    {"id": 10, "name": "Dark Gray", "hex": "#6D6E5C", "is_trans": False},
    {"id": 85, "name": "Dark Bluish Gray", "hex": "#6C6E68", "is_trans": False},
    {"id": 11, "name": "Black", "hex": "#05131D", "is_trans": False},

    # --- Tans & Browns ---
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
    {"id": 160, "name": "Fabuland Brown", "hex": "#B3694E", "is_trans": False},

    # --- Yellows & Oranges ---
    {"id": 33, "name": "Light Yellow", "hex": "#FBE696", "is_trans": False},
    {"id": 103, "name": "Bright Light Yellow", "hex": "#FFF03A", "is_trans": False},
    {"id": 166, "name": "Neon Yellow", "hex": "#DCE000", "is_trans": False},
    {"id": 3, "name": "Yellow", "hex": "#F2CD37", "is_trans": False},
    {"id": 110, "name": "Bright Light Orange", "hex": "#F8BB3D", "is_trans": False},
    {"id": 31, "name": "Medium Orange", "hex": "#FFA70B", "is_trans": False},
    {"id": 4, "name": "Orange", "hex": "#FE8A18", "is_trans": False},
    {"id": 29, "name": "Earth Orange", "hex": "#FA9C1C", "is_trans": False},
    {"id": 165, "name": "Neon Orange", "hex": "#FA5900", "is_trans": False},

    # --- Reds & Pinks ---
    {"id": 5, "name": "Red", "hex": "#C91A09", "is_trans": False},
    {"id": 59, "name": "Dark Red", "hex": "#720E0F", "is_trans": False},
    {"id": 23, "name": "Pink", "hex": "#FECCCF", "is_trans": False},
    {"id": 104, "name": "Bright Pink", "hex": "#E4ADC8", "is_trans": False},
    {"id": 47, "name": "Dark Pink", "hex": "#C870A0", "is_trans": False},
    {"id": 71, "name": "Magenta", "hex": "#923978", "is_trans": False},
    {"id": 220, "name": "Coral", "hex": "#FF698F", "is_trans": False},

    # --- Purples & Violets ---
    {"id": 154, "name": "Lavender", "hex": "#E1D5ED", "is_trans": False},
    {"id": 157, "name": "Medium Lavender", "hex": "#AC78BA", "is_trans": False},
    {"id": 24, "name": "Purple", "hex": "#81007B", "is_trans": False},
    {"id": 89, "name": "Dark Purple", "hex": "#3F3691", "is_trans": False},
    {"id": 73, "name": "Medium Violet", "hex": "#9391E4", "is_trans": False},
    {"id": 97, "name": "Blue-Violet", "hex": "#4C61DB", "is_trans": False},

    # --- Blues & Aquas ---
    {"id": 152, "name": "Light Aqua", "hex": "#ADC3C0", "is_trans": False},
    {"id": 41, "name": "Aqua", "hex": "#B3D7D1", "is_trans": False},
    {"id": 105, "name": "Bright Light Blue", "hex": "#9FC3E9", "is_trans": False},
    {"id": 42, "name": "Medium Blue", "hex": "#5A93DB", "is_trans": False},
    {"id": 7, "name": "Blue", "hex": "#0055BF", "is_trans": False},
    {"id": 63, "name": "Dark Blue", "hex": "#0A3463", "is_trans": False},
    {"id": 55, "name": "Sand Blue", "hex": "#6074A1", "is_trans": False},
    {"id": 156, "name": "Medium Azure", "hex": "#36AEBF", "is_trans": False},
    {"id": 153, "name": "Dark Azure", "hex": "#078BC9", "is_trans": False},
    {"id": 39, "name": "Dark Turquoise", "hex": "#008F9B", "is_trans": False},
    {"id": 40, "name": "Light Turquoise", "hex": "#55A5AF", "is_trans": False},

    # --- Greens ---
    {"id": 34, "name": "Lime", "hex": "#BBE90B", "is_trans": False},
    {"id": 158, "name": "Yellowish Green", "hex": "#DFEEA5", "is_trans": False},
    {"id": 35, "name": "Light Green", "hex": "#C2DAB8", "is_trans": False},
    {"id": 36, "name": "Bright Green", "hex": "#4B9F4A", "is_trans": False},
    {"id": 37, "name": "Medium Green", "hex": "#73DCA1", "is_trans": False},
    {"id": 6, "name": "Green", "hex": "#237841", "is_trans": False},
    {"id": 80, "name": "Dark Green", "hex": "#184632", "is_trans": False},
    {"id": 48, "name": "Sand Green", "hex": "#A0BCAC", "is_trans": False},
    {"id": 155, "name": "Olive Green", "hex": "#9B9A5A", "is_trans": False},

    # --- Metallic, Pearl & Chrome (Shiny) ---
    {"id": 95, "name": "Flat Silver", "hex": "#898788", "is_trans": False},
    {"id": 115, "name": "Pearl Gold", "hex": "#AA7F2E", "is_trans": False},
    {"id": 178, "name": "Flat Dark Gold", "hex": "#B48441", "is_trans": False},
    {"id": 61, "name": "Pearl Light Gray", "hex": "#9CA3A8", "is_trans": False},
    {"id": 77, "name": "Pearl Dark Gray", "hex": "#575857", "is_trans": False},
    {"id": 235, "name": "Pearl Light Gold", "hex": "#DCBC81", "is_trans": False},
    {"id": 65, "name": "Metallic Gold", "hex": "#DBAC34", "is_trans": False},
    {"id": 67, "name": "Metallic Silver", "hex": "#A5A9B4", "is_trans": False},
    {"id": 84, "name": "Metallic Copper", "hex": "#A66444", "is_trans": False},
    {"id": 70, "name": "Metallic Green", "hex": "#5C8C6B", "is_trans": False},
    {"id": 72, "name": "Metallic Blue", "hex": "#4D6F99", "is_trans": False},
    {"id": 21, "name": "Chrome Gold", "hex": "#BBA53D", "is_trans": False},
    {"id": 22, "name": "Chrome Silver", "hex": "#E0E0E0", "is_trans": False},
    {"id": 57, "name": "Chrome Antique Brass", "hex": "#645A4C", "is_trans": False},
    {"id": 64, "name": "Chrome Black", "hex": "#1B1B1B", "is_trans": False},
    {"id": 62, "name": "Chrome Green", "hex": "#3CB371", "is_trans": False},
    {"id": 52, "name": "Chrome Blue", "hex": "#1E90FF", "is_trans": False},
    {"id": 119, "name": "Copper", "hex": "#AE7A59", "is_trans": False},
    {"id": 232, "name": "Satin White", "hex": "#F2F3F2", "is_trans": False},

    # --- Transparent Colors ---
    {"id": 12, "name": "Trans-Clear", "hex": "#FCFCFC", "is_trans": True},
    {"id": 13, "name": "Trans-Black", "hex": "#635F62", "is_trans": True},
    {"id": 14, "name": "Trans-Dark Blue", "hex": "#0020A0", "is_trans": True},
    {"id": 15, "name": "Trans-Light Blue", "hex": "#AEEFEC", "is_trans": True},
    {"id": 74, "name": "Trans-Medium Blue", "hex": "#5ECBE6", "is_trans": True},
    {"id": 16, "name": "Trans-Neon Green", "hex": "#F8F184", "is_trans": True},
    {"id": 17, "name": "Trans-Red", "hex": "#C91A09", "is_trans": True},
    {"id": 18, "name": "Trans-Neon Yellow", "hex": "#DBAC34", "is_trans": True},
    {"id": 19, "name": "Trans-Yellow", "hex": "#F5CD2F", "is_trans": True},
    {"id": 20, "name": "Trans-Green", "hex": "#84B68D", "is_trans": True},
    {"id": 108, "name": "Trans-Bright Green", "hex": "#56E646", "is_trans": True},
    {"id": 98, "name": "Trans-Orange", "hex": "#F08F1C", "is_trans": True},
    {"id": 164, "name": "Trans-Light Orange", "hex": "#FCA352", "is_trans": True},
    {"id": 182, "name": "Trans-Neon Orange", "hex": "#FF800D", "is_trans": True},
    {"id": 51, "name": "Trans-Purple", "hex": "#A5499C", "is_trans": True},
    {"id": 50, "name": "Trans-Dark Pink", "hex": "#DF6695", "is_trans": True},
    {"id": 107, "name": "Trans-Pink", "hex": "#E4ADC8", "is_trans": True},
    {"id": 113, "name": "Trans-Medium Purple", "hex": "#8D73B3", "is_trans": True},
    {"id": 114, "name": "Trans-Light Purple", "hex": "#96709F", "is_trans": True},
    {"id": 236, "name": "Trans-Light Green", "hex": "#A5DBDB", "is_trans": True},

    # --- Glow In The Dark & Special ---
    {"id": 46, "name": "Glow In Dark Opaque", "hex": "#D9E4A7", "is_trans": False},
    {"id": 118, "name": "Glow In Dark Trans", "hex": "#BDC6AD", "is_trans": True},
    {"id": 159, "name": "Glow In Dark White", "hex": "#F5F3D7", "is_trans": False},
    {"id": 101, "name": "Glitter Trans-Clear", "hex": "#EEEEEE", "is_trans": True},
    {"id": 100, "name": "Glitter Trans-Dark Pink", "hex": "#DF6695", "is_trans": True},
    {"id": 102, "name": "Glitter Trans-Purple", "hex": "#6B3F7C", "is_trans": True},
]

# Alias for backward compatibility
BRICKLINK_PALETTE_REFERENCE = FULL_BRICKLINK_PALETTE


def hex_to_rgb(hex_code: str) -> tuple[int, int, int]:
    clean = hex_code.strip().lstrip("#")
    if len(clean) != 6:
        return (128, 128, 128)
    return (int(clean[0:2], 16), int(clean[2:4], 16), int(clean[4:6], 16))


def rgb_to_ycrcb(r: float, g: float, b: float) -> tuple[float, float, float]:
    """Standard ITU-R BT.601 conversion (cv2.COLOR_BGR2YCrCb)."""
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
    is_trans: bool = False
    finish: str = "solid"


_SPECIAL = re.compile(r"glitter|glitr|speckle|glow|milky|opal|iridescent|holo", re.IGNORECASE)
_SHINY = re.compile(r"pearl|metallic|chrome|satin|copper|bronze|\bgold\b|\bsilver\b", re.IGNORECASE)


def get_finish(name: str, is_trans: bool) -> str:
    if is_trans or name.lower().startswith("trans-"):
        return "trans"
    if _SPECIAL.search(name):
        return "special"
    if _SHINY.search(name):
        return "shiny"
    return "solid"


class ColorPalette:
    def __init__(self, entries: Sequence[dict[str, Any]] | None = None, include_trans: bool = True) -> None:
        source = entries if entries is not None else FULL_BRICKLINK_PALETTE
        self.entries: list[PaletteEntry] = []
        self._by_id: dict[int, PaletteEntry] = {}
        self._by_name: dict[str, PaletteEntry] = {}

        for row in source:
            cid = int(row.get("id") or 0)
            name = str(row.get("name") or "")
            is_trans = bool(row.get("is_trans") or name.lower().startswith("trans-"))
            if not include_trans and is_trans:
                continue

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
                is_trans=is_trans,
                finish=get_finish(name, is_trans),
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
    finish: str = "solid"


@dataclass
class CropFeatures:
    rgb: tuple[float, float, float]
    ycrcb: tuple[float, float, float]
    lab: tuple[float, float, float]
    pixel_count: int


def extract_crop_features(bgr: np.ndarray, use_mask: bool = True) -> CropFeatures | None:
    if bgr is None or bgr.size == 0:
        return None

    pixels_bgr = None
    if use_mask and pieceMask is not None:
        try:
            mask = pieceMask(bgr)
            if mask is not None and mask.sum() > 30:
                pixels_bgr = bgr[mask > 0]
        except Exception:
            pixels_bgr = None

    if pixels_bgr is None or len(pixels_bgr) < 20:
        h, w = bgr.shape[:2]
        bx = int(w * 0.2)
        by = int(h * 0.2)
        cropped = bgr[by : h - by, bx : w - bx] if (h - 2 * by >= 2 and w - 2 * bx >= 2) else bgr
        small = cv2.resize(cropped, (48, 48), interpolation=cv2.INTER_AREA)
        pixels_bgr = small.reshape(-1, 3)

    b, g, r = pixels_bgr.mean(axis=0)
    rgb = (float(r), float(g), float(b))
    ycrcb = rgb_to_ycrcb(rgb[0], rgb[1], rgb[2])
    lab = rgb_to_lab(rgb[0], rgb[1], rgb[2])

    return CropFeatures(rgb=rgb, ycrcb=ycrcb, lab=lab, pixel_count=len(pixels_bgr))


def match_color_rgb(rgb: tuple[float, float, float], palette: ColorPalette, top_k: int = 3) -> list[ColorMatch]:
    scores: list[tuple[float, PaletteEntry]] = []
    r1, g1, b1 = rgb
    for p in palette.entries:
        r2, g2, b2 = p.rgb
        dist = math.sqrt((r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2)
        # Apply moderate penalty for non-solid finishes during automatic pixel matching
        if p.finish != "solid":
            dist += 15.0
        scores.append((dist, p))
    scores.sort(key=lambda s: s[0])

    matches = []
    for dist, entry in scores[:top_k]:
        conf = math.exp(-dist / 35.0)
        matches.append(
            ColorMatch(
                color_id=entry.id,
                name=entry.name,
                hex=entry.hex,
                distance=round(dist, 2),
                confidence=round(conf, 4),
                finish=entry.finish,
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
    scores: list[tuple[float, PaletteEntry]] = []
    y1, cr1, cb1 = ycrcb

    chroma_mag = math.hypot(cr1 - 128.0, cb1 - 128.0)
    adaptive_w_y = w_y if chroma_mag > 15.0 else max(w_y, 0.75 - chroma_mag * 0.03)

    for p in palette.entries:
        y2, cr2, cb2 = p.ycrcb
        dist_sq = (
            adaptive_w_y * ((y1 - y2) ** 2)
            + w_chroma * ((cr1 - cr2) ** 2)
            + w_chroma * ((cb1 - cb2) ** 2)
        )
        dist = math.sqrt(dist_sq)
        # Finish penalty for shiny / trans during auto matching
        if p.finish != "solid":
            dist += 15.0
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
                finish=entry.finish,
            )
        )
    return matches


def match_color_lab(lab: tuple[float, float, float], palette: ColorPalette, top_k: int = 3) -> list[ColorMatch]:
    scores: list[tuple[float, PaletteEntry]] = []
    l1, a1, b1 = lab
    for p in palette.entries:
        l2, a2, b2 = p.lab
        dist = math.sqrt((l1 - l2) ** 2 + (a1 - a2) ** 2 + (b1 - b2) ** 2)
        if p.finish != "solid":
            dist += 15.0
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
                finish=entry.finish,
            )
        )
    return matches
