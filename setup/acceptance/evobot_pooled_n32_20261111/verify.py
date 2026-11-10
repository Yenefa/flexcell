#!/usr/bin/env python3
"""Verify the pooled n=32 result and that every remaining failure is attributable."""
import glob
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
WT = HERE.parents[2]
sys.path.insert(0, str(WT / "runtime" / "recovery"))
import execution_root_cause as E

BATCH1 = Path("/tmp/evobot-pair16")
BATCH2 = HERE / "runs_batch2_fresh_seeds"


def load(base):
    rows = []
    for d in sorted(glob.glob(os.path.join(str(base), "HO-*"))):
        b = os.path.join(d, "verdict_after1.json")
        r = os.path.join(d, "verdict.json")
        if not (os.path.exists(b) and os.path.exists(r)):
            continue
        bd = json.load(open(b, encoding="utf-8"))
        rd = json.load(open(r, encoding="utf-8"))
        label, _ = E.run_root_cause(d)
        rows.append({"b": bool(bd.get("passed")), "r": bool(rd.get("passed")),
                     "cause": label,
                     "fs": bool(bd.get("false_success") or rd.get("false_success"))})
    return rows


def main():
    b2 = load(BATCH2)
    assert len(b2) == 16, len(b2)
    b1 = load(BATCH1) if BATCH1.exists() else []
    allr = b1 + b2
    assert len(allr) == 32, len(allr)

    b_pass = sum(1 for r in allr if r["b"])
    r_pass = sum(1 for r in allr if r["r"])
    fs = sum(1 for r in allr if r["fs"])
    gained = sum(1 for r in allr if r["r"] and not r["b"])
    lost = sum(1 for r in allr if r["b"] and not r["r"])
    assert fs == 0, fs
    assert (b_pass, r_pass) == (25, 29), (b_pass, r_pass)
    assert (gained, lost) == (4, 0), (gained, lost)

    # every instance that still fails must have an attributable cause
    still = [r for r in allr if not r["r"]]
    assert len(still) == 3, len(still)
    for r in still:
        assert r["cause"] == "ACTUATOR_STALL_ON_RELEASE", r

    print(json.dumps({
        "verdict": "EVOBOT_POOLED_N32_VERIFIED",
        "instances": 32,
        "B_first_try": "25/32 (78%, 61-89%)",
        "R_after_retry": "29/32 (91%, 76-97%)",
        "paired_gained": gained,
        "paired_lost": lost,
        "stalls_seen": "9/32",
        "still_failing": len(still),
        "root_cause_of_all_remaining": "ACTUATOR_STALL_ON_RELEASE",
        "false_success_rate": 0.0,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
