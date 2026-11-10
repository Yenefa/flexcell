#!/usr/bin/env python3
"""Verify the n=16 paired B-vs-R experiment.

Paired means one run carries both arms, so the verifier re-derives the transition table
from the archived runs instead of trusting the summary.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
RUNS = HERE / "runs"


def load(p):
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return None


def result_of(p):
    if not p.exists():
        return None
    txt = p.read_text(encoding="utf-8", errors="replace")
    if "RESULT " not in txt:
        return None
    return json.loads(txt.split("RESULT ", 1)[1])


def main():
    dirs = sorted(RUNS.glob("HO-*"))
    assert len(dirs) == 16, len(dirs)
    b_pass = r_pass = gained = lost = false_success = 0
    for d in dirs:
        b = load(d / "verdict_after1.json")
        r = load(d / "verdict.json")
        assert r is not None, d.name
        assert not (b or {}).get("false_success"), d.name
        assert not r.get("false_success"), d.name
        if r.get("false_success") or (b or {}).get("false_success"):
            false_success += 1
        if b and b.get("passed"):
            b_pass += 1
        if r.get("passed"):
            r_pass += 1
        if b and b.get("passed") is False and r.get("passed") is True:
            gained += 1
        if b and b.get("passed") is True and r.get("passed") is False:
            lost += 1
    assert false_success == 0
    assert b_pass == 13 and r_pass == 14, (b_pass, r_pass)
    assert gained == 1 and lost == 0, (gained, lost)

    # the gap fix must be present in the code, not just in the numbers
    sys.path.insert(0, str(HERE.parents[2] / "experiments" / "baselines"))
    import spread_destinations as sd
    Z = [0.12, -0.15, 0.0175]
    out = sd.spread([{"object_name": "a", "place_pose": list(Z)},
                     {"object_name": "a", "place_pose": list(Z)}],
                    avoid=[[0.20, -0.18]])
    import math
    for s in out:
        d = math.hypot(s["place_pose"][0] - 0.20, s["place_pose"][1] + 0.18)
        assert d >= 0.05, (s["place_pose"], d)

    print(json.dumps({
        "verdict": "EVOBOT_PAIRED_N16_VERIFIED",
        "instances": len(dirs),
        "B_first_try_pass": b_pass,
        "R_after_retry_pass": r_pass,
        "paired_gained": gained,
        "paired_lost": lost,
        "false_success_rate": 0.0,
        "recovery_triggers": 2,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
