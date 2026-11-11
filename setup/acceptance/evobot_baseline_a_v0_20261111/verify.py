#!/usr/bin/env python3
"""Verify the Baseline A v0 freeze.

Every check here can fail; that is the point. A freeze that cannot be falsified is a decoration.

Checks
  1. the frozen components still hash to the recorded values (the baseline definition did not drift)
  2. the invalid r1 batch is marked invalid, so nobody cites 1/6 as a capability number
  3. the graded summary is internally consistent (passed <= graded, rate matches, no fabrication)
  4. false_success_count is 0 (the one safety property that may never regress)
  5. every GRADED instance carries a real measurement, not an empty clause list

Usage: verify.py [summary.json ...]   (defaults to every summary recorded below)
Exit 0 = all checks pass; 1 = at least one failed, with the reason printed.
"""
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
# .../wt-comp/setup/acceptance/<this>/verify.py -> parents[2] is wt-comp, parents[3] is the project root
WT = HERE.parents[2]
PROJ = HERE.parents[3]
INVALID_R1 = PROJ / "ci-public-window" / "evidence" / "baseline_a_batch_20261111"
SUMMARY_R2 = PROJ / "ci-public-window" / "evidence" / "baseline_a_batch_20261111_r2" / "summary.json"
SUMMARY_FULL = PROJ / "ci-public-window" / "evidence" / "baseline_a_v0_full_20261111" / "summary.json"

FAILED = []


def check(name, ok, detail=""):
    print(("PASS  " if ok else "FAIL  ") + name + (("  :: " + detail) if detail and not ok else ""))
    if not ok:
        FAILED.append(name)


def sha256(path):
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def main():
    cfg = json.loads((HERE / "config.json").read_text(encoding="utf-8"))

    # 1. the MEASUREMENT must not drift. These are the components a verdict depends on:
    #    what plan is built, what world is generated, how the robot is driven, how it is graded.
    drift = []
    for rel, want in cfg["definition_sha256"].items():
        p = PROJ / rel
        if not p.is_file():
            drift.append(rel + ": missing")
        elif sha256(p) != want:
            drift.append(rel + ": hash changed")
    check("measurement-critical components unchanged", not drift, "; ".join(drift))

    # 1b. the HARNESS may change, but only visibly. A batch driver swap mid-campaign is
    #     exactly the kind of thing that gets found months later and destroys trust, so a
    #     drift here is reported loudly and the recorded history must explain it.
    harness_notes = []
    for rel, info in cfg.get("harness_sha256", {}).items():
        p = PROJ / rel
        if not p.is_file():
            harness_notes.append(rel + ": missing")
            continue
        got = sha256(p)
        known = {h["sha256"] for h in info.get("history", [])}
        if got not in known:
            harness_notes.append(rel + ": current hash matches NO recorded version")
        elif got != info.get("current"):
            harness_notes.append(rel + ": running an older recorded version")
    check("batch harness is a recorded version (drift allowed, undocumented drift not)",
          not harness_notes, "; ".join(harness_notes))

    # 2. the invalid batch stays marked invalid
    check("r1 batch marked INVALID_MEASUREMENT",
          (INVALID_R1 / "INVALID_MEASUREMENT.md").is_file(),
          str(INVALID_R1))

    summaries = sys.argv[1:] or [str(p) for p in (SUMMARY_R2, SUMMARY_FULL) if p.is_file()]
    if not summaries:
        check("at least one summary exists", False, "no summary.json found")
    for s in summaries:
        path = Path(s)
        label = path.parent.name
        if not path.is_file():
            check(label + ": summary exists", False, str(path))
            continue
        d = json.loads(path.read_text(encoding="utf-8"))

        # 3. internal consistency -- a summary that disagrees with itself is not evidence
        ok = (isinstance(d.get("graded"), int) and isinstance(d.get("passed"), int)
              and isinstance(d.get("runs_attempted"), int)
              and 0 <= d["passed"] <= d["graded"] <= d["runs_attempted"])
        check(label + ": counts are consistent", ok, json.dumps(
            {k: d.get(k) for k in ("runs_attempted", "graded", "passed")}))
        if d.get("graded"):
            rate = d["passed"] / d["graded"]
            check(label + ": pass rate matches counts",
                  abs((d.get("pass_rate_over_graded") or 0) - rate) < 1e-9,
                  "%.6f vs %.6f" % (d.get("pass_rate_over_graded") or 0, rate))
            lo, hi = d.get("wilson_95_over_graded") or [0, 0]
            check(label + ": CI brackets the rate", lo <= rate <= hi, "%s %s" % (lo, hi))

        # 4. the safety property
        check(label + ": false_success_count is 0", d.get("false_success_count") == 0,
              str(d.get("false_success_count")))

        # 5. a pass must carry a measurement, not an empty claim
        hollow = []
        for e in d.get("per_instance", []):
            if e.get("status") != "GRADED":
                continue
            v = path.parent / e["instance"] / "verdict.json"
            if not v.is_file():
                hollow.append(e["instance"] + ": no verdict")
                continue
            vd = json.loads(v.read_text(encoding="utf-8"))
            clauses = vd.get("clauses") or []
            if not clauses:
                hollow.append(e["instance"] + ": no clauses at all")
                continue
            # Metric clauses must carry a measured number. Categorical clauses (e.g. "visit:")
            # legitimately carry only zone names -- requiring a float from them is a bug in this
            # checker, found by the checker itself on T05. Both kinds must carry *something*.
            bad = [c for c in clauses
                   if not (isinstance(c.get("evidence"), dict) and c["evidence"])]
            metric = [c for c in clauses
                      if str(c.get("clause", "")).split(":")[0] in ("placement", "unmoved")]
            for c in metric:
                if not any(isinstance(val, (int, float)) for val in c["evidence"].values()):
                    bad.append(c)
            if not any(isinstance(val, (int, float))
                       for c in clauses for val in (c.get("evidence") or {}).values()):
                bad.append({"clause": "verdict carries no measured number"})
            if bad:
                hollow.append(e["instance"] + ": " + str(bad[0].get("clause")))
        check(label + ": every graded verdict carries numbers", not hollow,
              "; ".join(hollow[:3]))

    print()
    print("%d failed" % len(FAILED))
    return 1 if FAILED else 0


if __name__ == "__main__":
    sys.exit(main())
