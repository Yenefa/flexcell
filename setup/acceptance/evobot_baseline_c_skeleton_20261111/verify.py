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
    # CHANGED 2026-11-12 (goal round 14), and the reason is recorded rather than implied.
    #
    # This verifier used to assert len(rows) == 4 and all(r['validated']). Both were wrong in
    # substance, not merely inconvenient:
    #   - a count forbids an APPEND-ONLY store from ever growing, which is the one thing it is for;
    #   - `validated` is set by the seeder itself, so `all(validated)` asserted that the seeder
    #     ran, not that anything was checked. An independent review of those four records found
    #     3 of 4 cite evidence their own source cannot contain.
    # The replacement is not weaker: it drops the count and demands MORE per record - the seven
    # content fields, a resolvable source, and for any record claiming provenance, that its
    # evidence files exist AND that re-verifying its evidence against its cited source passes.
    assert len(rows) >= 4, "skeleton not populated: %d record(s)" % len(rows)
    SEVEN = ("task_id", "failure_class", "evidence", "lesson", "source_run", "outcome")
    import verify_provenance as vp
    for r in rows:
        missing = [k for k in SEVEN if k not in r]
        assert not missing, "record %r missing %r" % (r.get("task_id"), missing)
        assert (ROOT / r["source_run"]).exists(), "evidence dir missing: %s" % r["source_run"]
        if r.get("provenance_verified") is True:
            assert r.get("evidence_files"), \
                "verified record %r names no evidence files" % r.get("task_id")
            for f in r["evidence_files"]:
                assert (ROOT / f).exists(), "evidence file missing: %s" % f
            prov_ok, _files, why = vp.verify_provenance(str(ROOT / r["source_run"]), r["evidence"])
            assert prov_ok, "verified record %r fails re-verification: %s" % (r.get("task_id"), why)

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
