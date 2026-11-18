#!/usr/bin/env python3
"""Operating envelope of the contact grasp backend: grasp error, transport, release.

Reads one transport-stage run (per-trial steps.jsonl + meta.json) and reports, per
trial, whether the box was lifted, carried without slip, released, and where it landed.

Usage:
  python3 envelope.py --run-dir results/transport-v1 --md-out results/transport-v1/ENVELOPE.md
"""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path

CHR = chr(10)
LIFT_OK_M = 0.10
DRIFT_LIMIT_MM = 2.0
CARRY_OK_M = 0.20
LAND_ERROR_LIMIT_MM = 20.0
RELEASE_Z_TOL_M = 0.005


def read_steps(path: Path) -> list[dict]:
    if not path.is_file() or path.stat().st_size == 0:
        raise SystemExit(f"{path}: missing or empty")
    rows = []
    for line in path.read_text().splitlines():
        if line.strip():
            rows.append(json.loads(line))
    if not rows:
        raise SystemExit(f"{path}: no samples")
    for key in ("t", "phase", "obj", "base", "rel", "contacts", "joints"):
        if key not in rows[0]:
            raise SystemExit(f"{path}: missing field {key}")
    return rows


def phases(rows: list[dict]) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for row in rows:
        out.setdefault(row["phase"], []).append(row)
    return out


def quat_angle_deg(a: list[float], b: list[float]) -> float:
    dot = abs(sum(x * y for x, y in zip(a, b)))
    dot = min(1.0, max(-1.0, dot))
    return math.degrees(2.0 * math.acos(dot))


def evaluate(cell: Path) -> dict:
    rows = read_steps(cell / "steps.jsonl")
    meta = json.loads((cell / "meta.json").read_text())
    by = phases(rows)
    for needed in ("settle", "close", "lift", "transport", "lower", "release"):
        if needed not in by:
            raise SystemExit(f"{cell}: missing phase {needed}")

    start = by["settle"][0]
    start_z = start["obj"]["p"][2]
    start_xy = (start["obj"]["p"][0], start["obj"]["p"][1])

    close_tail = by["close"][-25:]
    ref_p = [sum(s["rel"]["p"][i] for s in close_tail) / len(close_tail) for i in range(3)]
    ref_q = [sum(s["rel"]["q"][i] for s in close_tail) / len(close_tail) for i in range(4)]
    norm = math.sqrt(sum(v * v for v in ref_q)) or 1.0
    ref_q = [v / norm for v in ref_q]

    carried = by["lift"] + by["transport"] + by["lower"]
    drift_mm = 0.0
    rot_deg = 0.0
    for sample in carried:
        p, q = sample["rel"]["p"], sample["rel"]["q"]
        drift_mm = max(drift_mm, 1000.0 * math.dist(p, ref_p))
        rot_deg = max(rot_deg, quat_angle_deg(q, ref_q))

    lifted = max(s["obj"]["p"][2] for s in by["lift"]) >= start_z + LIFT_OK_M
    carried_m = max(s["obj"]["p"][0] for s in by["transport"] + by["lower"]) - start_xy[0]
    # The object legitimately descends during the lower phase, so "dropped in
    # flight" can only be judged while it is supposed to stay at lift height.
    drop_mid = min(s["obj"]["p"][2] for s in by["transport"]) < start_z + LIFT_OK_M

    final = rows[-1]
    released = (final["contacts"]["left_pad"] == 0 and final["contacts"]["right_pad"] == 0
                and abs(final["obj"]["p"][2] - start_z) <= RELEASE_Z_TOL_M)
    # Where the object *should* land: the commanded transport target in the world,
    # not "wherever it was grabbed". A grasp offset therefore costs placement
    # accuracy, which is what a real task would feel.
    target = (float(meta.get("transport_m", 0.25)), 0.0)
    land_error_mm = 1000.0 * math.dist((final["obj"]["p"][0], final["obj"]["p"][1]), target)

    size = float(meta.get("size_m", 0.035))
    lift_tail = by["lift"][-50:]
    gap = sum(s.get("gap_actual", size) for s in lift_tail) / len(lift_tail)
    penetration_mm = 500.0 * max(0.0, size - gap)  # per side

    success = (lifted and drift_mm < DRIFT_LIMIT_MM and carried_m >= CARRY_OK_M
               and released and not drop_mid and land_error_mm < LAND_ERROR_LIMIT_MM)
    return {
        "trial": cell.name,
        "jitter_mm": (round(1000 * meta.get("jitter", {}).get("x", 0.0), 2),
                      round(1000 * meta.get("jitter", {}).get("y", 0.0), 2)),
        "yaw_deg": meta.get("jitter", {}).get("yaw_deg", 0.0),
        "transport_s": meta.get("transport_s"),
        "lifted": lifted,
        "drift_mm": drift_mm,
        "rot_deg": rot_deg,
        "carried_m": carried_m,
        "drop_mid": drop_mid,
        "released": released,
        "land_error_mm": land_error_mm,
        "penetration_mm": penetration_mm,
        "success": success,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    cells = sorted(p for p in args.run_dir.iterdir() if p.is_dir() and (p / "steps.jsonl").is_file())
    if not cells:
        raise SystemExit(f"{args.run_dir}: no trial directories")
    results = [evaluate(cell) for cell in cells]

    lines = [
        "# 接触抓取的操作包络（抓取误差 / 搬运 / 释放）",
        "",
        "每一行是一次完整 pick-lift(0.15 m)-transport(0.25 m)-lower-release 周期；",
        "判据：抓起 ≥0.10 m、搬运全程相对漂移 < 2 mm、搬出 ≥0.20 m、释放后指垫脱离且落地、",
        "落点误差 < 20 mm。",
        "",
        "| trial | 位移误差 x/y (mm) | yaw | 搬运 s | 抓起 | 漂移 mm | 单侧挤压 mm | 搬出 m | 中途掉 | 释放 | 落点误差 mm | 判定 |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        lines.append("| {} | {}/{} | {:.0f}° | {:.2f} | {} | {:.3f} | {:.2f} | {:.3f} | {} | {} | {:.2f} | {} |".format(
            r["trial"], r["jitter_mm"][0], r["jitter_mm"][1], r["yaw_deg"], r["transport_s"],
            "是" if r["lifted"] else "**否**", r["drift_mm"], r["penetration_mm"], r["carried_m"],
            "是" if r["drop_mid"] else "否", "是" if r["released"] else "**否**",
            r["land_error_mm"], "PASS" if r["success"] else "**FAIL**"))

    passed = [r for r in results if r["success"]]
    lines += ["", "## 结论", "",
              "- 成功 {}/{}。".format(len(passed), len(results)),
              "- 通过的最大横向（y）误差：{} mm。".format(
                  max((abs(r["jitter_mm"][1]) for r in passed), default=0)),
              "- 通过的最大沿指（x）误差：{} mm。".format(
                  max((abs(r["jitter_mm"][0]) for r in passed), default=0)),
              "- 通过的最大 yaw：{}°。".format(max((abs(r["yaw_deg"]) for r in passed), default=0)),
              ""]
    text = CHR.join(lines)
    if args.md_out:
        args.md_out.write_text(text + CHR)
    if args.json_out:
        args.json_out.write_text(json.dumps({"trials": results}, indent=2) + CHR)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
