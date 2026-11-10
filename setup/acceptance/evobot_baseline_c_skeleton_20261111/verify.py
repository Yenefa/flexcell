#!/usr/bin/env python3
"""Verify the Baseline C skeleton: store, guards, retrieval, regression decision."""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
for p in ("evolution/experience", "evolution/diagnosis",
          "evolution/validation", "experiments/baselines"):
    sys.path.insert(0, str(ROOT / p))

import store
import regress
import baseline_c as C


def main():
    sp = ROOT / "evolution" / "experience" / "records.jsonl"
    ok, msg = store.verify_chain(sp)
    assert ok, msg
    rows = store.read(sp)
    assert len(rows) == 4, len(rows)
    assert all(r["validated"] for r in rows)
    assert all((ROOT / r["source_run"]).exists() for r in rows), "evidence dir missing"

    bad = {"files": ["benchmark/evaluators/evaluate.py"], "evidence": {"x": 1},
           "expected_effect": "x", "rollback": "revert"}
    accepted, _ = regress.gate(bad, run_regressions=False)
    assert accepted is False

    obs = {"instruction": "passing through the right bin first",
           "objects": [], "zones": [], "skills": []}
    enriched = C.build_observation_with_experience(obs)
    assert enriched["experience"], "retrieval returned nothing"

    print(json.dumps({"verdict": "EVOBOT_BASELINE_C_SKELETON_VERIFIED",
                      "stage": "Unit Tested only",
                      "experience_records": len(rows),
                      "chain": msg,
                      "regression_gate_blocks_evaluator": True,
                      "retrieved_lessons": len(enriched["experience"]),
                      "simulation_tested": False,
                      "independently_verified": False}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
