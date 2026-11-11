#!/usr/bin/env python3
"""Generate a fifth held-out set from a NEW template that constrains ORDER.

WHY: every earlier held-out instance varied the world but not the STRUCTURE of the
requirement. T12 asks for a repeated route and T13 for a measured branch; a planner could
satisfy both without ever reasoning about when things must happen. T14 makes sequence part of
the goal and is graded by the existing "order" clause, so the evaluator is untouched.
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "benchmark" / "generators"))
import unseen_tasks as U


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    if list(out.glob("*.json")):
        raise SystemExit("refusing to overwrite existing specs")
    seeds = [9300, 9301, 9302, 9303, 9304, 9305, 9306, 9307,
             9400, 9401, 9402, 9403, 9404, 9405, 9406, 9407]
    for seed in seeds:
        spec = U.generate("T14_ordered_pair", seed, "held_out")
        spec.pop("_branch_note", None)
        (out / (spec["task_id"] + ".json")).write_text(
            json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    ids = sorted(p.stem for p in out.glob("*.json"))
    print("staged %d T14 specs on fresh seeds 9300/9400" % len(ids))
    for prev in ("recovery_public16", "recovery_public32", "recovery_public48",
                 "recovery_public64"):
        d = WT / "benchmark" / "held_out" / prev
        if d.is_dir():
            assert not ({p.stem for p in d.glob("*.json")} & set(ids)), prev
    print("no overlap with any earlier set")
    # the order constraint must actually be present and non-trivial
    for p in sorted(out.glob("*.json")):
        sp = json.loads(p.read_text(encoding="utf-8"))
        o = sp["expected_goal"].get("order") or []
        assert len(o) == 2 and o[0] != o[1], p.stem
        assert sp["constraints"]["order"] == o
    print("every spec carries a two-element order constraint")
    return 0


if __name__ == "__main__":
    sys.exit(main())
