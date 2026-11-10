#!/usr/bin/env python3
"""C13: does MTC show a planning capability the legacy dispatch path lacks?

FOUR runs, and the conclusion needs all of them:

  mtc-default   default world, dual_object      -> PASS 6/6
  legacy        fair constrained world          -> PASS 6/6
  mtc           fair constrained world          -> FAIL at PLACE_B
  plate030-*    over-sized plate (my bug)       -> both fail, MTC further

The MTC control matters: without it, "MTC failed on the constrained scene" could
equally mean "MTC fails dual_object generally". It does not - it passes the default
world. So the constrained scene really does separate the two arms, and the direction
is AGAINST the hypothesis: legacy completes, MTC does not.

The failure is also not a planning timeout: the recorded detail is
"measured start state differs from planned trajectory", raised by _consume_mtc.
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
            "trace": t.get("fsm_trace") or [], "world": d.get("world_sha256")}


def mtc_place_b_error():
    """Pull the real reason out of the MTC skill record, not the summary."""
    for f in glob.glob(str(HERE / "mtc" / "run-*" / "skills" / "move_to_pose.jsonl")):
        for line in Path(f).read_text().splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            if row.get("outcome") == "FAILED":
                return str(row.get("detail") or "")
    return ""


def main():
    ctl = load("mtc-default")
    fair_l, fair_m = load("legacy"), load("mtc")
    wide_l, wide_m = load("plate030-legacy"), load("plate030-mtc")

    # the control: MTC is not simply broken on dual_object
    assert ctl["status"] == "PASS", ctl["status"]
    assert len(ctl["trace"]) == 6, ctl["trace"]

    # each pair ran the same world; the two plate sizes are different worlds
    assert fair_l["world"] == fair_m["world"]
    assert wide_l["world"] == wide_m["world"]
    assert fair_l["world"] != wide_l["world"]
    assert fair_l["world"] != ctl["world"], "control must be the default world"

    # fair constrained world: legacy completes, MTC does not
    assert fair_l["status"] == "PASS", fair_l["status"]
    assert all(s.endswith(":OK") for s in fair_l["trace"])
    assert fair_m["status"] != "PASS", fair_m["status"]
    assert fair_m["trace"][-1] == "PLACE_B:FAIL", fair_m["trace"]

    # wide plate: the artefact I reported and then retracted
    assert wide_l["status"] != "PASS" and wide_m["status"] != "PASS"

    detail = mtc_place_b_error()
    assert "measured start state differs" in detail, detail[:200]

    print(json.dumps({
        "verdict": "C13_NO_MTC_ADVANTAGE_CONTROL_CONFIRMS_THE_SCENE_SEPARATES_THEM",
        "control_mtc_default_world": ctl["status"],
        "fair_constrained": {"legacy": fair_l["status"], "mtc": fair_m["status"]},
        "mtc_failure_is_not_a_timeout": "measured start state differs from planned "
                                        "trajectory (move_to_pose_server._consume_mtc)",
        "mechanism_question": "MTC does NOT show a capability FSM lacks here",
        "start_state_guard": "has a real 0.03 rad tolerance; it fired because the "
                             "handoff went stale between planning and consumption, "
                             "NOT because the comparison lacks a bound",
        "n_per_arm": 1,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
