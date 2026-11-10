#!/usr/bin/env python3
"""C13: does MTC show a planning capability the legacy dispatch path lacks?

THIS RECORD CONTAINS A REVERSAL, and the verifier enforces both halves so neither
can be quoted alone:

  plate 0.30 m (too wide, obstructed box B):
      legacy stops at PLACE_A;  MTC reaches PLACE_A + VERIFY_A
  plate 0.12 m (covers box A only, fair):
      legacy PASSES the whole task;  MTC fails at PLACE_B

The first result was an artefact of my own scene bug. The fair scene reverses it.
So the answer to the mechanism question here is NEGATIVE for MTC: on the one
properly sized constrained scene, the legacy stack completes and MTC does not.
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


def main():
    fair_l, fair_m = load("legacy"), load("mtc")
    wide_l, wide_m = load("plate030-legacy"), load("plate030-mtc")
    # each pair really ran the same world
    assert fair_l["world"] == fair_m["world"], (fair_l["world"], fair_m["world"])
    assert wide_l["world"] == wide_m["world"], (wide_l["world"], wide_m["world"])
    # the two plate sizes are genuinely different worlds
    assert fair_l["world"] != wide_l["world"], "plate change did not change the world"

    # --- wide plate: the artefact ---
    assert wide_l["trace"] == ["PICK_A(attempt=1):OK", "PLACE_A:FAIL"], wide_l["trace"]
    assert wide_m["trace"][:3] == ["PICK_A(attempt=1):OK", "PLACE_A:OK",
                                   "VERIFY_A(attempt=1):OK"], wide_m["trace"]
    assert wide_l["status"] != "PASS" and wide_m["status"] != "PASS"

    # --- fair plate: the reversal ---
    assert fair_l["status"] == "PASS", fair_l["status"]
    assert len(fair_l["trace"]) == 6 and all(s.endswith(":OK") for s in fair_l["trace"]), \
        fair_l["trace"]
    assert fair_m["status"] != "PASS", fair_m["status"]
    assert fair_m["trace"][-1] == "PLACE_B:FAIL", fair_m["trace"]

    print(json.dumps({
        "verdict": "C13_NO_MTC_ADVANTAGE_REVERSES_THE_ARTEFACT",
        "wide_plate_0_30m": {
            "legacy": wide_l["status"], "mtc": wide_m["status"],
            "note": "plate obstructed box B; MTC looked further ahead only because "
                    "legacy died earlier on the same obstruction",
        },
        "fair_plate_0_12m": {
            "legacy": fair_l["status"], "mtc": fair_m["status"],
            "legacy_phases": fair_l["trace"], "mtc_phases": fair_m["trace"],
        },
        "mechanism_question": "MTC does NOT show a capability FSM lacks here",
        "n_per_arm": 1,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
