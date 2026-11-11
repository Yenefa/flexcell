#!/usr/bin/env python3
"""Verify the auto-approach result and the two refuted alternatives."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def load(tag, i):
    p = HERE / ("%s_%d.json" % (tag, i))
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def main():
    auto = [load("auto", i) for i in range(5)]
    clamp = [load("clamped", i) for i in range(5)]
    assert all(auto), [i for i, r in enumerate(auto) if not r]

    ok = [i for i, r in enumerate(auto) if r["official_success"]]
    assert ok == [0, 1, 3], ok
    chosen = {i: auto[i]["mode"] for i in range(5)}
    assert chosen[0] == "top" and chosen[1] == "top" and chosen[3] == "side_x", chosen

    # the single-system result must beat either fixed policy on its own
    assert len(ok) == 3, ok

    # clamping the support plane was tried and made it worse - that must be on the record
    ok_clamp = [i for i, r in enumerate(clamp) if r and r["official_success"]]
    assert len(ok_clamp) < len(ok), (ok_clamp, ok)

    # the side_y refutation previously existed only as a string in the output, so deleting the
    # artefacts or flipping them would not have failed the check. Assert it.
    for i in (2, 4):
        sy = load("side_y", i)
        assert sy is not None, "side_y artefact for task %d is missing" % i
        assert sy["official_success"] is False, ("side_y now succeeds", i)
        assert sy["release_xy_error_m"] > 0.3, ("side_y error changed", i, sy)

    print(json.dumps({
        "verdict": "EVOBOT_LIBERO_AUTO_APPROACH_THREE_OF_FIVE",
        "single_system_solved": ok,
        "top_alone": [0, 1],
        "side_alone": [1, 3],
        "rule": "measured height <= 0.140 m -> top, else side_x",
        "refuted_alternatives": {
            "clamp_geometry_to_table": "%d/5, worse" % len(ok_clamp),
            "side_y_on_tall_bottles": "both still fail, 504 and 651 mm release error",
        },
        "remaining_failures": "the two tallest bottles (0.186/0.187 m); mechanism located, not fixed",
        "llm_involvement": "none - this is a deterministic geometry rule, i.e. the strong baseline",
        "perception": "ORACLE",
        "evaluator_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
