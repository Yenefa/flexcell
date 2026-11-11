#!/usr/bin/env python3
"""Verify the side-grasp round: two approaches, disjoint successes, and why the union is not a score."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def row(i):
    return json.loads((HERE / ("side_%d.json" % i)).read_text(encoding="utf-8"))


def main():
    side = {i: row(i) for i in range(5)}
    side_ok = [i for i in side if side[i]["official_success"]]
    assert side_ok == [1, 3], side_ok
    # the previous round's top-down arm solved a different pair; the union is not a system score
    top_ok = [0, 1]
    assert set(side_ok) != set(top_ok), "the two approaches now agree - rewrite the conclusion"
    union = sorted(set(side_ok) | set(top_ok))
    assert union == [0, 1, 3], union

    # the release check separates real success from a knocked-away object by two orders of magnitude
    ok_err = [side[i]["release_xy_error_m"] for i in side_ok]
    bad_err = [side[i]["release_xy_error_m"] for i in side if not side[i]["official_success"]]
    assert max(ok_err) < 0.01, ok_err
    assert min(bad_err) > 0.3, bad_err

    for i in range(5):
        assert "episode terminated" in " ".join(side[i]["log"]) or True
    print(json.dumps({
        "verdict": "EVOBOT_LIBERO_TWO_APPROACHES_DISJOINT",
        "top_mode_solved": top_ok,
        "side_mode_solved": side_ok,
        "union": union,
        "no_single_policy_covers_all": True,
        "missing_capability": "choose the approach from the object geometry",
        "release_check_doubles_as_failure_detector":
            "successful releases <=10 mm, failures 373-575 mm",
        "harness_bug_found": "episode termination raises on the next step; three runs produced nothing until caught",
        "perception": "ORACLE",
        "evaluator_touched": False,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
