#!/usr/bin/env python3
"""C13: under one constrained world, does MTC reach a phase the legacy stack cannot?

Both arms ran the SAME generated world (identical sha256), same case (dual_object),
same backend, decision policy fsm; only skill_backend differs. So any difference in
how far the task gets is attributable to the planner, not to the scene.

The honest verdict is deliberately narrow: MTC is NOT shown to solve the scene.
It is shown to complete one object where legacy fails at the first place, and then
to fail on the second pick - the ceiling was sized for box A and obstructs box B.
"""
import glob
import hashlib
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


def main():
    legacy, mtc = load("legacy"), load("mtc")
    # the whole point only holds if both arms saw the SAME obstacle layout
    assert legacy["world"] == mtc["world"], (legacy["world"], mtc["world"])
    assert legacy["world"], "world hash missing"
    # neither arm is allowed to have succeeded - this is not a capability win
    assert legacy["status"] != "PASS" and mtc["status"] != "PASS"
    # legacy cannot place the first object at all
    assert legacy["trace"] == ["PICK_A(attempt=1):OK", "PLACE_A:FAIL"], legacy["trace"]
    assert legacy["error_code"] == "ERR_SKILL_FAILED"
    # MTC places and verifies the first object, then dies on the second pick
    assert mtc["trace"][:3] == ["PICK_A(attempt=1):OK", "PLACE_A:OK",
                                "VERIFY_A(attempt=1):OK"], mtc["trace"]
    assert any("PICK_B" in s and "FAIL" in s for s in mtc["trace"]), mtc["trace"]
    # so the phases reached differ, and the difference is exactly the place/verify
    # pair that legacy never gets to
    legacy_ok = [s for s in legacy["trace"] if s.endswith(":OK")]
    mtc_ok = [s for s in mtc["trace"] if s.endswith(":OK")]
    assert len(mtc_ok) > len(legacy_ok)
    print(json.dumps({
        "verdict": "C13_MTC_REACHES_A_PLACE_PHASE_LEGACY_CANNOT",
        "same_world": legacy["world"],
        "legacy": {"status": legacy["status"], "error": legacy["error_code"],
                   "phases_ok": legacy_ok},
        "mtc": {"status": mtc["status"], "error": mtc["error_code"],
                "phases_ok": mtc_ok},
        "neither_completed": True,
        "scene_limitation": "ceiling sized for box A also obstructs box B",
        "n_per_arm": 1,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
