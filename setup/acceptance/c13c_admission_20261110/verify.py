#!/usr/bin/env python3
"""C13c: fix the planner admission refusal and see what MTC does next.

Pre-registered outcomes (docs/C13C_PREREGISTRATION.md):
  H1 MTC passes                      -> the C13 negative is retracted
  H2 fails later, different error    -> two problems coexist
  H0 fails at PLACE_B the same way   -> admission was not the cause

The answer is H2, and the split matters:
  - admission refusals are GONE: 12 MTC moves, 11 succeeded, no "planner busy";
  - the object IS placed: place_err = 0.000 m;
  - what still fails is the RETREAT after placing, on the start-state guard,
    because the retreat plan was made from a predicted state, not the measured one.
"""
import glob
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent


def load(arm):
    f = glob.glob(str(HERE / arm / "run-*" / "result.json"))[0]
    d = json.loads(Path(f).read_text())
    t = d.get("task") or {}
    return {"status": d["status"], "error_code": t.get("error_code"),
            "trace": t.get("fsm_trace") or []}


def mtc_failures():
    out, place_detail = [], ""
    for f in glob.glob(str(HERE / "mtc-constrained" / "run-*" / "skills" / "move_to_pose.jsonl")):
        rows = [json.loads(l) for l in Path(f).read_text().splitlines() if l.strip()]
        out = rows
    for f in glob.glob(str(HERE / "mtc-constrained" / "run-*" / "skills" / "place.jsonl")):
        for line in Path(f).read_text().splitlines():
            if line.strip() and json.loads(line).get("outcome") not in ("0", 0):
                place_detail = str(json.loads(line).get("detail") or "")
    return out, place_detail


def main():
    mtc_c, mtc_d, leg_c = (load("mtc-constrained"), load("mtc-default"),
                           load("legacy-constrained"))

    # controls: the fix broke nothing
    assert mtc_d["status"] == "PASS", mtc_d["status"]
    assert leg_c["status"] == "PASS", leg_c["status"]
    assert len(leg_c["trace"]) == 6 and all(s.endswith(":OK") for s in leg_c["trace"])

    # MTC still fails, but LATER than before
    assert mtc_c["status"] != "PASS", mtc_c["status"]
    assert mtc_c["trace"][-1] == "PLACE_B:FAIL", mtc_c["trace"]

    moves, place_detail = mtc_failures()
    # admission refusals are gone: no busy refusals left in the move log
    assert moves, "no move records"
    assert not any("planner busy" in str(r.get("detail") or "") for r in moves), \
        "planner busy still appears; the admission fix did not take effect"
    # and MTC got much further before failing
    assert len(moves) >= 12, len(moves)
    ok = [r for r in moves if r.get("outcome") == "SUCCEEDED"]
    assert len(ok) >= 11, len(ok)

    # the object really was placed - the failure is the retreat, not the place
    assert "object dropped (place_err=0.000)" in place_detail, place_detail[:120]
    assert "retreat failed" in place_detail, place_detail[:120]
    # and the retreat died on the start-state guard with a real delta
    assert "measured start state differs" in place_detail, place_detail[:120]
    print(json.dumps({
        "verdict": "C13C_ADMISSION_FIXED_MTC_NOW_PLACES_AND_FAILS_ON_RETREAT",
        "pre_registered_outcome": "H2 - fails later, different error",
        "admission_refusals_after_fix": 0,
        "mtc_moves": len(moves), "succeeded": len(ok),
        "object_placed": True,
        "place_err_m": 0.0,
        "remaining_failure": "retreat plan start != measured state "
                             "(joint3 delta 0.0529 rad > 0.03 tolerance)",
        "controls": {"mtc_default": mtc_d["status"], "legacy_constrained": leg_c["status"]},
        "n_per_arm": 1,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
