"""Benchmark script evaluating RGB vs YCrCb vs CIELAB on recorded machine piece crops."""

from __future__ import annotations

import base64
import json
import sqlite3
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from color_space_analyzer import (
    ColorPalette,
    extract_crop_features,
    match_color_lab,
    match_color_rgb,
    match_color_ycrcb,
)


def run_benchmark(
    db_path: str = "software/sorter/backend/local_state.sqlite",
    images_dir: str = "software/sorter/backend/piece_images",
    max_pieces: int = 150,
    export_json_path: str | None = None,
) -> dict[str, Any]:
    palette = ColorPalette()
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    rows = cur.execute(
        "SELECT uuid, part_id, part_name, color_id, color_name, color_corrected_id "
        "FROM piece_records "
        "WHERE color_id IS NOT NULL AND color_id != 'any_color' "
        "ORDER BY seen_at DESC"
    ).fetchall()

    img_base = Path(images_dir)
    evaluated_pieces: list[dict[str, Any]] = []

    rgb_correct = 0
    ycrcb_correct = 0
    lab_correct = 0
    total = 0

    confusion_rgb_to_ycrcb: list[dict[str, Any]] = []

    for uuid, part_id, part_name, color_id, color_name, color_corrected_id in rows:
        target_color_id = int(color_corrected_id) if color_corrected_id and str(color_corrected_id).isdigit() else int(color_id) if str(color_id).isdigit() else None
        if target_color_id is None:
            continue

        p_dir = img_base / uuid
        if not p_dir.exists():
            continue

        crop_files = sorted(list(p_dir.glob("*.jpg")))
        if not crop_files:
            continue

        features_list = []
        sample_b64 = None

        for idx, cf in enumerate(crop_files):
            bgr = cv2.imread(str(cf))
            if bgr is None:
                continue

            feat = extract_crop_features(bgr)
            if feat is not None:
                features_list.append(feat)

            if sample_b64 is None:
                # Thumbnail for the validation UI
                h, w = bgr.shape[:2]
                scale = min(120.0 / max(w, 1), 120.0 / max(h, 1))
                thumb = cv2.resize(bgr, (max(1, int(w * scale)), max(1, int(h * scale))))
                ok, buf = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ok:
                    sample_b64 = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode("ascii")

        if not features_list:
            continue

        total += 1
        mean_rgb = tuple(np.mean([f.rgb for f in features_list], axis=0))
        mean_ycrcb = tuple(np.mean([f.ycrcb for f in features_list], axis=0))
        mean_lab = tuple(np.mean([f.lab for f in features_list], axis=0))

        matches_rgb = match_color_rgb(mean_rgb, palette, top_k=3)
        matches_ycrcb = match_color_ycrcb(mean_ycrcb, palette, top_k=3, w_y=0.25)
        matches_lab = match_color_lab(mean_lab, palette, top_k=3)

        rgb_match_id = matches_rgb[0].color_id if matches_rgb else None
        ycrcb_match_id = matches_ycrcb[0].color_id if matches_ycrcb else None
        lab_match_id = matches_lab[0].color_id if matches_lab else None

        rgb_ok = (rgb_match_id == target_color_id)
        ycrcb_ok = (ycrcb_match_id == target_color_id)
        lab_ok = (lab_match_id == target_color_id)

        if rgb_ok:
            rgb_correct += 1
        if ycrcb_ok:
            ycrcb_correct += 1
        if lab_ok:
            lab_correct += 1

        piece_entry = {
            "uuid": uuid,
            "part_id": part_id,
            "part_name": part_name,
            "ground_truth_id": target_color_id,
            "ground_truth_name": color_name,
            "crop_count": len(crop_files),
            "mean_rgb": [round(float(c), 1) for c in mean_rgb],
            "mean_ycrcb": [round(float(c), 1) for c in mean_ycrcb],
            "rgb_pred": {
                "id": matches_rgb[0].color_id,
                "name": matches_rgb[0].name,
                "hex": matches_rgb[0].hex,
                "dist": matches_rgb[0].distance,
                "ok": rgb_ok,
            },
            "ycrcb_pred": {
                "id": matches_ycrcb[0].color_id,
                "name": matches_ycrcb[0].name,
                "hex": matches_ycrcb[0].hex,
                "dist": matches_ycrcb[0].distance,
                "ok": ycrcb_ok,
            },
            "lab_pred": {
                "id": matches_lab[0].color_id,
                "name": matches_lab[0].name,
                "hex": matches_lab[0].hex,
                "dist": matches_lab[0].distance,
                "ok": lab_ok,
            },
            "thumbnail_b64": sample_b64,
        }
        evaluated_pieces.append(piece_entry)

        if total >= max_pieces:
            break

    summary = {
        "total_evaluated": total,
        "rgb_accuracy": round(rgb_correct / max(1, total) * 100.0, 1),
        "ycrcb_accuracy": round(ycrcb_correct / max(1, total) * 100.0, 1),
        "lab_accuracy": round(lab_correct / max(1, total) * 100.0, 1),
        "rgb_correct": rgb_correct,
        "ycrcb_correct": ycrcb_correct,
        "lab_correct": lab_correct,
        "pieces": evaluated_pieces,
    }

    if export_json_path:
        with open(export_json_path, "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

    return summary


if __name__ == "__main__":
    res = run_benchmark(export_json_path="color_benchmark_results.json")
    print(f"Evaluated {res['total_evaluated']} pieces:")
    print(f"  RGB Accuracy:   {res['rgb_accuracy']}% ({res['rgb_correct']}/{res['total_evaluated']})")
    print(f"  YCrCb Accuracy: {res['ycrcb_accuracy']}% ({res['ycrcb_correct']}/{res['total_evaluated']})")
    print(f"  CIELAB Accuracy:{res['lab_accuracy']}% ({res['lab_correct']}/{res['total_evaluated']})")
