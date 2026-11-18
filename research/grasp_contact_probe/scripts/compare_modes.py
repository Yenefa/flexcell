#!/usr/bin/env python3
"""Put the contact backend and the magnet (detachable joint) backend on one load ladder.

Both runs come from the same world, the same jaw geometry, the same lift profile
and the same acceptance thresholds; the only difference is what carries the
object: friction between the pads, or a rigid joint.

Usage:
  python3 compare_modes.py --contact results/stress-v3 --magnet results/magnet-v1 --md-out results/mode-comparison/MODE_COMPARISON.md
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

CHR = chr(10)


def load_summary(run_dir: Path) -> dict:
    path = run_dir / "summary.json"
    if not path.is_file():
        raise SystemExit(f"missing {path}; run scripts/analyze.py first")
    return json.loads(path.read_text())


def ladder_rows(summary: dict, prefix: str) -> dict:
    rows: dict = {}
    for trial in summary["trials"]:
        if not trial["trial"].startswith(prefix):
            continue
        mass = round(float(trial["meta"]["mass_kg"]), 3)
        pad = trial["contacts"]["pad_fraction"]["lift"]
        rows[mass] = {
            "trial": trial["trial"],
            "drift_mm": float(trial["drift"]["translation_mm"]),
            "dropped": bool(trial["drop"]["drop"]),
            "pad_contact": float(pad["both"]),
        }
    if not rows:
        raise SystemExit(f"no trials with prefix {prefix!r}")
    return rows


def outcome(row: dict) -> str:
    if row["dropped"]:
        return "脱落"
    if row["drift_mm"] >= 2.0:
        return "滑移 {:.2f} mm".format(row["drift_mm"])
    return "托住 {:.3f} mm".format(row["drift_mm"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contact", type=Path, required=True)
    parser.add_argument("--contact-prefix", default="stress-load-")
    parser.add_argument("--magnet", type=Path, required=True)
    parser.add_argument("--magnet-prefix", default="magnet-")
    parser.add_argument("--md-out", type=Path)
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args()

    contact = ladder_rows(load_summary(args.contact), args.contact_prefix)
    magnet = ladder_rows(load_summary(args.magnet), args.magnet_prefix)
    masses = sorted(set(contact) | set(magnet))

    out = [
        "# 接触 vs 磁吸：同一载荷阶梯",
        "",
        "- 接触后端：{}（试次前缀 {}）".format(args.contact, args.contact_prefix),
        "- 磁吸后端：{}（试次前缀 {}，DetachableJoint）".format(args.magnet, args.magnet_prefix),
        "- 判据完全一样：相对漂移 < 2 mm、无掉落；载荷从 0.05 kg 扫到 5 kg。",
        "",
        "| 载荷 / kg | 接触（摩擦） | 指垫接触 | 磁吸（刚性连接） | 指垫接触 |",
        "| --- | --- | --- | --- | --- |",
    ]
    summary_rows = []
    for mass in masses:
        c = contact.get(mass)
        m = magnet.get(mass)
        c_text = outcome(c) if c else "未测"
        c_pad = "{:.0f}%".format(c["pad_contact"] * 100) if c else "—"
        m_text = outcome(m) if m else "未测"
        m_pad = "{:.0f}%".format(m["pad_contact"] * 100) if m else "—"
        out.append("| {:g} | {} | {} | {} | {} |".format(mass, c_text, c_pad, m_text, m_pad))
        summary_rows.append({"mass_kg": mass, "contact": c, "magnet": m})

    contact_fail = [
        row["mass_kg"] for row in summary_rows
        if row["contact"] and (row["contact"]["dropped"] or row["contact"]["drift_mm"] >= 2.0)
    ]
    magnet_fail = [
        row["mass_kg"] for row in summary_rows if row["magnet"] and row["magnet"]["dropped"]
    ]
    magnet_note = (
        "无，扫到 {:g} kg 仍全过".format(max(magnet)) if not magnet_fail else str(magnet_fail)
    )
    out += [
        "",
        "## 读法",
        "",
        "- 接触后端从 {:g} kg 起失效（滑移或脱落）；磁吸后端失效质量：{}。".format(
            min(contact_fail), magnet_note),
        "- 磁吸一侧指垫接触恒为 0%：物体不是被夹住，是被接住的——这既不是夹持，也不是物理能力。",
        "- 两条曲线不是谁更好：一条是物理（有 mu、有 N、有边界），另一条是删除物理（无 mu、无边界、无失效模式）。",
        "- 所以磁吸的适用场景是仿真流水线 / 回归 / demo；不能用于 D3 准入、真机迁移，也不能回答真实抓取稳不稳。",
        "",
    ]
    text = CHR.join(out)
    if args.md_out:
        args.md_out.parent.mkdir(parents=True, exist_ok=True)
        args.md_out.write_text(text + CHR)
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps({"rows": summary_rows}, indent=2) + CHR)
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
