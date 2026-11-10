#!/usr/bin/env python3
"""Separate what the EXISTING retry already recovers from what a new one could add.

WHY: after the actuator proposal I claimed a bounded release retry would help. Then I
measured the stall base rate and realised my own resume path ALREADY recovers most stalls.
If that is true the proposal buys SPEED, not pass rate, and saying otherwise would be an
overclaim. This script attributes each stall-resolved run to whoever resolved it.
"""
import glob
import json
import os
import sys

BATCHES = ["/tmp/evobot-pair16", "/tmp/evobot-pair32"]


def stall_in_attempt(run_dir, attempt_prefix):
    """Any release stall inside in-run attempts (episodes before the retry)?"""
    n = 0
    for ep in glob.glob(os.path.join(run_dir, "sim", "episodes", "*.json")):
        try:
            doc = json.load(open(ep, encoding="utf-8"))
        except Exception:
            continue
        for st in doc.get("steps") or []:
            det = str((st.get("executor_result") or {}).get("detail") or "")
            if "did not open" in det:
                n += 1
                break
    return n


def main():
    rows = []
    for base in BATCHES:
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            eps = glob.glob(os.path.join(d, "sim", "episodes", "*.json"))
            if not eps:
                continue
            b = os.path.join(d, "verdict_after1.json")
            r = os.path.join(d, "verdict.json")
            if not (os.path.exists(b) and os.path.exists(r)):
                continue
            bd = json.load(open(b, encoding="utf-8"))
            rd = json.load(open(r, encoding="utf-8"))
            retry_plan = os.path.exists(os.path.join(d, "plan_retry.json"))
            stalled = stall_in_attempt(d, "") > 0
            rows.append({"id": os.path.basename(d), "b": bool(bd.get("passed")),
                         "r": bool(rd.get("passed")), "stalled": stalled,
                         "had_retry": retry_plan})

    stalled = [x for x in rows if x["stalled"]]
    print("runs with a release stall:", len(stalled))
    print()
    already = [x for x in stalled if x["r"] and not x["b"]]
    absorbed = [x for x in stalled if x["r"] and x["b"]]
    lost = [x for x in stalled if not x["r"]]
    print("  resolved by the EXISTING bounded retry (B fail -> R pass): %d" % len(already))
    print("  resolved inside the run (B already passed)            : %d" % len(absorbed))
    print("  still failing (never resolved)                        : %d" % len(lost))
    print()
    n = len(stalled)
    if n:
        print("ALREADY recovered by existing mechanisms: %d/%d = %.0f%%"
              % (len(already) + len(absorbed), n,
                 100.0 * (len(already) + len(absorbed)) / n))
        print("So a NEW skill-layer retry cannot add that share; it can only")
        print("change HOW FAST a stall is resolved, or reach stalls the plan-level")
        print("retry cannot, since that retry re-runs the whole stage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
