#!/usr/bin/env python3
"""Check BOTH directions of the goal_check fix on the same 16 instances.

WHY BOTH DIRECTIONS: the fix makes recovery skip a retry when the goal is already met. That
has an obvious benefit (no pointless retry) and an obvious danger (if it skips a retry that
was needed, it deletes the only measured capability gain this project has). A comparison
that only shows "fewer retries" would look like success even if it had destroyed the gains.
So this prints:
  * did pointless retries disappear?  (retried_after_pass should fall to 0)
  * did productive retries survive?   (gained must not fall)

Both batches are gated on structural validation first. Numbers from a pipeline that did not
run are not measurements.
"""
import glob
import json
import os
import subprocess
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
BEFORE = "/tmp/evobot-batch2"     # same instances, goal_check absent
AFTER = "/tmp/evobot-batch3"      # same instances, goal_check active


def read(p):
    try:
        return json.load(open(p, encoding="utf-8"))
    except Exception:
        return None


def task_said_failure(d):
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


def score(base):
    rows = {}
    for d in sorted(glob.glob(os.path.join(base, "HO-*"))):
        oid = os.path.basename(d)
        b = read(os.path.join(d, "verdict_after1.json")) or {}
        r = read(os.path.join(d, "verdict.json")) or {}
        dec = read(os.path.join(d, "recovery_decision.json")) or {}
        dec = dec.get("decision") or dec
        gc = read(os.path.join(d, "goal_check.json")) or {}
        rows[oid] = {
            "b": bool(b.get("passed")),
            "r": bool(r.get("passed")),
            "retried": os.path.exists(os.path.join(d, "plan_retry.json")),
            "action": dec.get("action"),
            "reason": dec.get("reason"),
            "task_failed": task_said_failure(d),
            "goal_refused": "REFUSED" in str(gc.get("decision", "")),
        }
    return rows


def main():
    v = os.path.join(WT, "experiments", "baselines", "validate_batch.py")
    for label, base in (("BEFORE", BEFORE), ("AFTER", AFTER)):
        if not os.path.isdir(base):
            print("%s: missing %s - cannot compare yet" % (label, base))
            return 1
        rc = subprocess.run([sys.executable, v, base], capture_output=True, text=True)
        print("%s validation rc=%d" % (label, rc.returncode))
        if rc.returncode != 0:
            print(rc.stdout.strip()[:700])
            return 1

    before, after = score(BEFORE), score(AFTER)
    shared = sorted(set(before) & set(after))
    print("\nsame instances in both batches: %d" % len(shared))
    print()
    print("%-20s %-22s %-22s" % ("run", "BEFORE (no goal_check)", "AFTER (goal_check)"))
    for oid in shared:
        x, y = before[oid], after[oid]
        def fmt(z):
            if z["retried"]:
                return "B=%s retry=%s" % (z["b"], z["action"])
            return "B=%s no retry" % z["b"]
        print("%-20s %-22s %-22s" % (oid, fmt(x), fmt(y)))

    def stats(rows):
        n = len(rows)
        return {
            "n": n,
            "b": sum(1 for z in rows.values() if z["b"]),
            "r": sum(1 for z in rows.values() if z["r"]),
            "retried": sum(1 for z in rows.values() if z["retried"]),
            "retried_after_pass": sum(1 for z in rows.values()
                                      if z["retried"] and z["b"]),
            "gained": sum(1 for z in rows.values() if not z["b"] and z["r"]),
            "lost": sum(1 for z in rows.values() if z["b"] and not z["r"]),
            "goal_skips": sum(1 for z in rows.values()
                              if z["action"] == "no_recovery"
                              and "satisfied" in str(z["reason"])),
            "goal_refusals": sum(1 for z in rows.values() if z["goal_refused"]),
        }

    sb, sa = stats(before), stats(after)
    print()
    print("%-26s %-12s %s" % ("metric", "BEFORE", "AFTER"))
    for k, label in (("b", "arm B pass"), ("r", "arm R pass"),
                     ("retried", "retries issued"),
                     ("retried_after_pass", "RETRY AFTER PASS (pointless)"),
                     ("gained", "paired gains"),
                     ("lost", "paired losses"),
                     ("goal_skips", "skipped: goal already met"),
                     ("goal_refusals", "goal_check refused")):
        print("%-26s %-12s %s" % (label, sb[k], sa[k]))

    print()
    ok_pointless = sa["retried_after_pass"] == 0
    ok_gains = sa["gained"] >= sb["gained"] if sb["gained"] else True
    print("pointless retries eliminated :", ok_pointless)
    print("productive retries preserved :", ok_gains)
    if not ok_pointless:
        print("  -> the fix did not take effect; pointless retries remain")
    if not ok_gains:
        print("  -> WARNING: gains fell, the check may be skipping needed recoveries")
    return 0 if (ok_pointless and ok_gains) else 1


if __name__ == "__main__":
    sys.exit(main())
