#!/usr/bin/env python3
"""Read-only mechanism discrimination for issue #121 (post-release drift).

The place skill records ``object_before_release`` (position + quaternion) and
``box_after`` (settled position). This module recomputes, without ROS or a
simulator, the quantity that the current pre-release gate does NOT check:

    the tilt of the box's local Z axis away from world Z at the moment of
    release, and the direction of the horizontal shift that follows.

A 35 mm cube released above the table with a tilted attitude lands on one
edge/corner first and tips over. For a rock-back (tilt <= 45 deg) the centre-of
-mass shift along the tilt direction is, to first order,

    shift = h * (1 - cos(t) + sin(t)),  h = half edge = 17.5 mm

This is a geometric prediction, not a fitted parameter. It is compared with
recorded shifts; the direction cosine against the up-vector's horizontal
projection is the discriminator between tipping and the two competing
mechanisms (residual velocity, gripper retreat contact): tipping predicts a
deterministic -1 alignment, the other two do not.

This script does not change production code, does not dispatch motion goals,
does not replay or replace any evidence, and does not declare an acceptance
result. It only reads already-recorded logs.

Usage:
  python3 scripts/release_drift_analysis.py --logs-root /home/ros --json out.json
  python3 scripts/release_drift_analysis.py --issue121-only
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import statistics
from pathlib import Path

BOX_EDGE_M = 0.035
HALF_EDGE_MM = BOX_EDGE_M * 1000.0 / 2.0  # 17.5 mm
TIP_THRESHOLD_DEG = 45.0
TILT_FLOOR_DEG = 2.0  # below this the horizontal up-vector is too small to orient
MIN_SHIFT_MM = 0.1  # sub-0.1 mm shifts are numeric noise, not a physical direction

# Transcribed verbatim from issue #121. These are NOT local measurements:
# the /workspace/flexcell-119-results/raw records live on the cloud runner.
ISSUE121 = {
    "layout1_B": {
        "tilt_deg": 26.13,
        "pre_release_error_mm": 0.426,
        "settled_error_mm": 10.533,
        "quaternion": None,
    },
    "layout2_C": {
        "tilt_deg": 52.74,
        "pre_release_error_mm": 0.731,
        "settled_error_mm": 27.284,
        "object_before_release": [0.120181, 0.040127, 0.030197,
                                  0.094056, 0.434123, 0.472795, 0.761023],
        "box_after": [0.093507, 0.033481, 0.017266],
        "target": [0.12, 0.04, 0.0175],
    },
}


def up_vector(q):
    """Box local +Z expressed in world frame, for quaternion (x, y, z, w)."""
    x, y, z, w = (float(v) for v in q)
    return (2.0 * (x * z + w * y),
            2.0 * (y * z - w * x),
            1.0 - 2.0 * (x * x + y * y))


def tilt_deg(q):
    """Angle between box local +Z and world +Z. Yaw about Z contributes zero."""
    ux, uy, uz = up_vector(q)
    norm = math.sqrt(ux * ux + uy * uy + uz * uz)
    if norm <= 0.0:
        raise ValueError("zero quaternion")
    return math.degrees(math.acos(max(-1.0, min(1.0, uz / norm))))


def geometric_shift_mm(tilt, half_edge_mm=HALF_EDGE_MM):
    """Predicted horizontal centre-of-mass shift of a tipped rock-back cube."""
    t = math.radians(tilt)
    return half_edge_mm * (1.0 - math.cos(t) + math.sin(t))


def tipping_regime(tilt):
    if tilt < TIP_THRESHOLD_DEG:
        return "ROCK_BACK"
    if tilt > TIP_THRESHOLD_DEG:
        return "ROLL_OVER_BEYOND_LOCAL_SAMPLE_RANGE"
    return "THRESHOLD"


def horizontal_shift(before, after):
    return (after[0] - before[0], after[1] - before[1])


def direction_cosine(q, before, after):
    """Cosine between measured horizontal shift and up-vector horizontal part.

    -1 means the box moved exactly opposite to its tilt (tip-over fingerprint).
    """
    ux, uy, _ = up_vector(q)
    dx, dy = horizontal_shift(before, after)
    n = math.hypot(ux, uy)
    m = math.hypot(dx, dy)
    if n < 1e-6 or m < 1e-6:
        return None
    return (dx * ux + dy * uy) / (m * n)


def analyze_record(rec, source=""):
    before = rec.get("object_before_release")
    after = rec.get("box_after")
    if not before or len(before) < 7 or not after or len(after) < 2:
        return None
    q = before[3:7]
    t = tilt_deg(q)
    dx, dy = horizontal_shift(before, after)
    shift_mm = math.hypot(dx, dy) * 1000.0
    err = rec.get("place_error_m")
    row = {
        "source": source,
        "tilt_deg": round(t, 4),
        "shift_mm": round(shift_mm, 4),
        "direction_cosine": direction_cosine(q, before, after),
        "predicted_shift_mm": round(geometric_shift_mm(t), 4),
        "place_error_mm": round(err * 1000.0, 4) if err is not None else None,
        "release_z_mm": round(before[2] * 1000.0, 3),
        "backend": rec.get("skill_backend"),
        "regime": tipping_regime(t),
    }
    if row["direction_cosine"] is not None:
        row["direction_cosine"] = round(row["direction_cosine"], 5)
    return row


def load_records(logs_root):
    pattern = os.path.join(logs_root, "**", "place.jsonl")
    files = sorted(glob.glob(pattern, recursive=True))
    rows = []
    for path in files:
        try:
            with open(path, "r", errors="replace") as handle:
                for line in handle:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except ValueError:
                        continue
                    row = analyze_record(rec, path)
                    if row is not None:
                        rows.append(row)
        except OSError:
            continue
    return files, rows


def gate_simulation(rows, limits=(10, 15, 20, 25, 30)):
    """Retrodict what a pre-release tilt gate would have admitted.

    This is a replay over already-recorded releases, NOT a controlled
    experiment: it cannot establish a success rate or justify a threshold on
    its own. It only shows which recorded runs would have been refused.
    """
    out = []
    for limit in limits:
        passed = [r for r in rows
                  if r["tilt_deg"] <= limit and r["place_error_mm"] is not None]
        errs = sorted(r["place_error_mm"] for r in passed)
        out.append({
            "tilt_limit_deg": limit,
            "admitted": len(passed),
            "refused": sum(1 for r in rows if r["tilt_deg"] > limit),
            "max_settled_error_mm": round(errs[-1], 3) if errs else None,
            "p95_settled_error_mm": round(errs[int(0.95 * (len(errs) - 1))], 3) if errs else None,
            "admitted_over_10mm": sum(1 for e in errs if e > 10.0),
        })
    return out


def summarize(files, rows, max_tilt_observed=None):
    oriented = [r for r in rows
                if r["direction_cosine"] is not None
                and r["tilt_deg"] >= TILT_FLOOR_DEG
                and r["shift_mm"] >= MIN_SHIFT_MM]
    cosines = [r["direction_cosine"] for r in oriented]
    residuals = [r["shift_mm"] - r["predicted_shift_mm"]
                 for r in oriented if r["regime"] == "ROCK_BACK"]
    rmse = math.sqrt(sum(v * v for v in residuals) / len(residuals)) if residuals else None
    bins = {}
    for r in rows:
        key = int(r["tilt_deg"] // 5) * 5
        bins.setdefault(key, []).append(r["shift_mm"])
    binned = []
    for key in sorted(bins):
        values = bins[key]
        binned.append({"tilt_bin_deg": key, "n": len(values),
                       "mean_shift_mm": round(statistics.mean(values), 3),
                       "sd_shift_mm": round(statistics.pstdev(values), 3),
                       "min_shift_mm": round(min(values), 3),
                       "max_shift_mm": round(max(values), 3)})
    return {
        "files_scanned": len(files),
        "records_with_release_pose": len(rows),
        "records_usable_for_direction": len(oriented),
        "noise_level_records_excluded": len(rows) - len(oriented),
        "max_tilt_observed_deg": max_tilt_observed if max_tilt_observed is not None
                                 else max((r["tilt_deg"] for r in rows), default=None),
        "direction_cosine_mean": round(statistics.mean(cosines), 5) if cosines else None,
        "direction_cosine_median": round(statistics.median(cosines), 5) if cosines else None,
        "aligned_with_minus_up": sum(1 for c in cosines if c < -0.5),
        "aligned_with_plus_up": sum(1 for c in cosines if c > 0.5),
        "ambiguous_direction": sum(1 for c in cosines if -0.5 <= c <= 0.5),
        "rockback_model_rmse_mm": round(rmse, 4) if rmse is not None else None,
        "rockback_model_n": len(residuals),
        "tilt_bins": binned,
        "tilt_gate_retrodiction": gate_simulation(rows),
    }


def issue121_check():
    c = ISSUE121["layout2_C"]
    q = c["object_before_release"][3:7]
    before = c["object_before_release"]
    after = c["box_after"]
    t = tilt_deg(q)
    cos = direction_cosine(q, before, after)
    dx, dy = horizontal_shift(before, after)
    shift_mm = math.hypot(dx, dy) * 1000.0
    target_shift = math.dist(before[:2], c["target"][:2]) * 1000.0
    settled = math.dist(after, c["target"]) * 1000.0
    b = ISSUE121["layout1_B"]
    return {
        "note": "issue #121 values transcribed from the issue body; cloud raw logs unavailable on this host",
        "layout2_C": {
            "quaternion_recomputed_tilt_deg": round(t, 3),
            "issue_reported_tilt_deg": c["tilt_deg"],
            "recomputed_horizontal_shift_mm": round(shift_mm, 3),
            "recomputed_settled_error_mm": round(settled, 3),
            "issue_reported_settled_error_mm": c["settled_error_mm"],
            "direction_cosine": round(cos, 5) if cos is not None else None,
            "geometric_prediction_mm": round(geometric_shift_mm(t), 3),
            "regime": tipping_regime(t),
            "release_clearance_above_target_mm": round((before[2] - c["target"][2]) * 1000.0, 3),
            "pre_release_position_error_mm": round(target_shift, 3),
        },
        "layout1_B": {
            "issue_reported_tilt_deg": b["tilt_deg"],
            "issue_reported_settled_error_mm": b["settled_error_mm"],
            "geometric_prediction_mm": round(geometric_shift_mm(b["tilt_deg"]), 3),
            "regime": tipping_regime(b["tilt_deg"]),
        },
    }


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--logs-root", default=None,
                    help="directory to scan recursively for place.jsonl")
    ap.add_argument("--json", default=None, help="write the full report as JSON here")
    ap.add_argument("--issue121-only", action="store_true",
                    help="only recompute the two issue #121 reference points")
    args = ap.parse_args(argv)

    report = {"issue121": issue121_check()}
    if not args.issue121_only:
        if not args.logs_root:
            ap.error("--logs-root is required unless --issue121-only is given")
        files, rows = load_records(args.logs_root)
        report["summary"] = summarize(files, rows)
        report["records"] = rows

    text = json.dumps(report, indent=2, ensure_ascii=False)
    print(text)
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(text + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
