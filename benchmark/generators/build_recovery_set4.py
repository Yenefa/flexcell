#!/usr/bin/env python3
"""Generate a FOURTH held-out set on seeds never used for any earlier batch.

WHY A NEW SET IS NEEDED FOR A GENERALIZATION CLAIM: the 7500/7600 set was already planned
over in the retracted pair48 batch. The agent never learned from it, so it is still held
out, but it is not untouched. A generalization claim should rest on instances that no run
in this project has ever touched.
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "benchmark" / "generators"))
import unseen_tasks as U

T13_SEEDS = [8100, 8101, 8102, 8103, 8104, 8105, 8106, 8107]
T12_SEEDS = [8200, 8201, 8202, 8203, 8204, 8205, 8206, 8207]


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    if list(out.glob("*.json")):
        raise SystemExit("refusing to overwrite existing specs in %s" % out)
    for template, seeds in (("T13_geometric_conditional", T13_SEEDS),
                             ("T12_triple_revisit", T12_SEEDS)):
        for seed in seeds:
            spec = U.generate(template, seed, "held_out")
            spec.pop("_branch_note", None)
            (out / (spec["task_id"] + ".json")).write_text(
                json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    ids = sorted(p.stem for p in out.glob("*.json"))
    print("staged %d specs on untouched seeds 8100/8200" % len(ids))
    # guard: no overlap with any earlier set
    for prev in ("recovery_public16", "recovery_public32", "recovery_public48"):
        d = WT / "benchmark" / "held_out" / prev
        if not d.is_dir():
            continue
        old = {p.stem for p in d.glob("*.json")}
        overlap = old & set(ids)
        assert not overlap, ("overlaps %s: %s" % (prev, sorted(overlap)[:3]))
    print("no overlap with public16/32/48")
    return 0


if __name__ == "__main__":
    sys.exit(main())
