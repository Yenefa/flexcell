#!/usr/bin/env python3
"""Generate a THIRD 16-instance held-out set on fresh seeds (7500-7507, 7600-7607).

WHY: every previous batch measured false success either not at all or by retrofitting the
self-assessment afterwards. This set exists to run the FULL honesty chain natively - the
assessor runs during the batch, its claim is passed into the observation with
--agent-claim, and the verdict therefore carries a claim that was collected at run time
rather than reconstructed later.
"""
import json
import sys
from pathlib import Path

WT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(WT / "benchmark" / "generators"))
import unseen_tasks as U

T13_SEEDS = [7500, 7501, 7502, 7503, 7504, 7505, 7506, 7507]
T12_SEEDS = [7600, 7601, 7602, 7603, 7604, 7605, 7606, 7607]


def main():
    out = Path(sys.argv[1])
    out.mkdir(parents=True, exist_ok=True)
    for template, seeds in (("T13_geometric_conditional", T13_SEEDS),
                             ("T12_triple_revisit", T12_SEEDS)):
        for seed in seeds:
            spec = U.generate(template, seed, "held_out")
            spec.pop("_branch_note", None)
            (out / (spec["task_id"] + ".json")).write_text(
                json.dumps(spec, indent=2) + "\n", encoding="utf-8")
    print("staged", len(list(out.glob("*.json"))), "specs on fresh seeds 7500/7600")
    return 0


if __name__ == "__main__":
    sys.exit(main())
