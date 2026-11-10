#!/usr/bin/env python3
"""Classify execution failures from the EPISODE file, not from the policy wrapper.

WHY THIS EXISTS: for many rounds the remaining failures were reported as
"err 62 native terminal/verification unconfirmed", and then as "grasp failure". Both are
the POLICY wrapper talking. The episode file records what the executor actually did, and
for every remaining failure in the 16-instance batch it says the same thing:

    gripper did not open (position=-0.011, requested=0.02, stalled=True)

That is an actuator-level event - the jaws stalled on an obstacle while trying to RELEASE
 - not a planning error and not an experience problem. A stall during an OPEN command
means something is pinching the jaws, so the box is never released and the stage cannot
commit.

This module reads episodes only. It changes no grading and writes nothing.
"""
import glob
import json
import os
import sys

STALL_OPEN = "gripper did not open"
STALL_CLOSE = "gripper did not close"


def episode_failures(episode_path):
    try:
        doc = json.load(open(episode_path, encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    out = []
    for st in doc.get("steps") or []:
        er = st.get("executor_result") or {}
        if er.get("outcome") == 1:
            out.append({"detail": str(er.get("detail") or ""),
                        "error_code": er.get("error_code")})
    return out


def classify(detail):
    d = (detail or "").lower()
    if STALL_OPEN in d:
        return "ACTUATOR_STALL_ON_RELEASE"
    if STALL_CLOSE in d:
        return "ACTUATOR_STALL_ON_GRASP"
    if "ik" in d or "unreachable" in d:
        return "KINEMATICS"
    return "OTHER"


def run_root_cause(run_dir):
    for ep in sorted(glob.glob(os.path.join(run_dir, "sim", "episodes", "*.json"))):
        for f in episode_failures(ep):
            label = classify(f["detail"])
            if label != "OTHER":
                return label, f["detail"]
    return "OTHER", None


def main():
    base = sys.argv[1] if len(sys.argv) > 1 else "/tmp/evobot-pair16"
    counts = {}
    rows = []
    for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
        label, detail = run_root_cause(d)
        rows.append((os.path.basename(d), label, detail))
        counts[label] = counts.get(label, 0) + 1
    print("%-20s %-26s %s" % ("run", "root cause", "detail"))
    for oid, label, detail in rows:
        print("%-20s %-26s %s" % (oid, label, (detail or "")[:60]))
    print()
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print("  %-26s %d" % (k, v))
    return 0


if __name__ == "__main__":
    sys.exit(main())
