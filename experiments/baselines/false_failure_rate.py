#!/usr/bin/env python3
"""Measure the FALSE FAILURE rate at the task level: the FSM reported failure while the
independent evaluator says the goal was satisfied.

WHY THIS IS A DISTINCT METRIC FROM FALSE SUCCESS: false success is the agent claiming success
the world does not support. This is the mirror image - the agent reports failure while the
world satisfies the goal. It matters because:
  * the recovery driver acts on task.out, so it retries work that is already done;
  * arm R looks exercised when it was never needed;
  * a downstream consumer would repeat a task that already succeeded.
The evaluator is untouched; both facts are read from artefacts.

Only batches whose structure validates are counted, because a number from a pipeline that
did not run is not a measurement.
"""
import glob
import json
import math
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BATCHES = sys.argv[1:] or ["/tmp/evobot-batch1", "/tmp/evobot-batch2"]


def wilson(k, n, z=1.96):
    if n == 0:
        return 0.0, 0.0, 0.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d
    return p, max(0.0, c - h), min(1.0, c + h)


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def task_reported_failure(d):
    """What the FSM itself concluded, from task.out."""
    out = os.path.join(d, "task.out")
    if not os.path.exists(out):
        return None
    txt = open(out, encoding="utf-8", errors="replace").read()
    i = txt.rfind("RESULT ")
    if i < 0:
        return None
    try:
        return json.loads(txt[i + 7:]).get("outcome") != 0
    except Exception:
        return None


def main():
    v = os.path.join(WT, "experiments", "baselines", "validate_batch.py")
    rows = []
    for base in BATCHES:
        if not os.path.isdir(base):
            print("missing", base)
            continue
        import subprocess
        rc = subprocess.run([sys.executable, v, base], capture_output=True, text=True)
        if rc.returncode != 0:
            print("REFUSING: %s failed validation" % base)
            return 1
        for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
            v1 = read(os.path.join(d, "verdict_after1.json")) or {}
            failed = task_reported_failure(d)
            if failed is None:
                continue
            rows.append({
                "batch": os.path.basename(base),
                "id": os.path.basename(d),
                "task_said_failure": failed,
                "evaluator_passed": bool(v1.get("passed")),
                "retried": os.path.exists(os.path.join(d, "plan_retry.json")),
            })

    n = len(rows)
    ff = [r for r in rows if r["task_said_failure"] and r["evaluator_passed"]]
    fs = [r for r in rows if (not r["task_said_failure"]) and not r["evaluator_passed"]]
    agree = [r for r in rows if r["task_said_failure"] == (not r["evaluator_passed"])]

    print("%-10s %-20s %-12s %-12s %s" % ("batch", "run", "task_said",
                                          "evaluator", "note"))
    for r in rows:
        note = ""
        if r["task_said_failure"] and r["evaluator_passed"]:
            note = "FALSE_FAILURE (retried=%s)" % r["retried"]
        elif (not r["task_said_failure"]) and not r["evaluator_passed"]:
            note = "FALSE_SUCCESS"
        print("%-10s %-20s %-12s %-12s %s" % (
            r["batch"].replace("evobot-", ""), r["id"],
            "FAIL" if r["task_said_failure"] else "ok",
            "passed" if r["evaluator_passed"] else "failed", note))

    print()
    print("runs                                   : %d" % n)
    print("task verdict agrees with evaluator     : %d/%d" % (len(agree), n))
    for label, k in (("FALSE FAILURE (task said fail, world ok)", len(ff)),
                     ("FALSE SUCCESS (task said ok, world bad)", len(fs))):
        p, lo, hi = wilson(k, n)
        print("%-40s %2d/%-2d = %5.1f%% (%.1f-%.1f%%)" % (label, k, n,
                                                          100 * p, 100 * lo, 100 * hi))
    if ff:
        print()
        print("The false failures are the ones that trigger pointless recovery. They are")
        print("not evaluator errors: the evaluator is reading the world, the FSM is reading")
        print("its own skill's success flag.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
