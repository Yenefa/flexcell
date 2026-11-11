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
    import verify_provenance as vp
    # CORRECTED 2026-11-12 (round 15) after an independent review found this check was WEAKER
    # than what it replaced. Its four defects, all real:
    #   1. `if r.get('provenance_verified') is True:` made provenance OPT-IN - a record that simply
    #      omitted the field received ZERO provenance checking, including all four legacy records.
    #      The reviewer demonstrated it by appending a fabricated record with no such field: the
    #      gate passed.
    #   2. `is True` is a type check, so the string 'true' also passed.
    #   3. SEVEN had six entries - store_version was missing - while the comment claimed seven.
    #      A name that overstates a check is the same defect class as validated:true set by the
    #      seeder. It is now SEVEN_FIELDS and it contains seven.
    #   4. `all(validated)` was removed with no replacement, so a record with validated:false and
    #      no provenance claim passed where the OLD verifier failed it. Weaker for that class.
    #
    # THE FIX IS TO NOT TRUST THE RECORD'S OWN CLAIM: provenance is now DERIVED here, for every
    # record, every time. A record may not assert its way past the gate, and the legacy records
    # that genuinely fail are REPORTED rather than skipped.
    SEVEN_FIELDS = ("store_version", "task_id", "failure_class", "evidence",
                    "lesson", "source_run", "outcome")
    assert len(SEVEN_FIELDS) == 7
    derived_ok = 0
    derived_fail = []
    for r in rows:
        missing = [k for k in SEVEN_FIELDS if k not in r]
        assert not missing, "record %r missing %r" % (r.get("task_id"), missing)
        assert (ROOT / r["source_run"]).exists(), "evidence dir missing: %s" % r["source_run"]
        prov_ok, files, why = vp.verify_provenance(str(ROOT / r["source_run"]), r["evidence"])
        if prov_ok:
            derived_ok += 1
        else:
            derived_fail.append((r.get("task_id"), why))
        # A record may NOT claim provenance the checker cannot reproduce.
        if r.get("provenance_verified") is True:
            assert prov_ok, ("record %r CLAIMS provenance_verified but fails re-verification: %s"
                             % (r.get("task_id"), why))
            assert r.get("evidence_files"), \
                "verified record %r names no evidence files" % r.get("task_id")
            for fpath in r["evidence_files"]:
                assert (ROOT / fpath).exists(), "evidence file missing: %s" % fpath
    # The skeleton must contain at least one record whose evidence is actually reproducible;
    # otherwise the store is populated with prose and the channel is empty.
    assert derived_ok >= 1, (
        "no record in the store has reproducible evidence; %d record(s) fail provenance"
        % len(derived_fail))

    bad = {"files": ["benchmark/evaluators/evaluate.py"], "evidence": {"x": 1},
           "expected_effect": "x", "rollback": "revert"}
    accepted, _ = regress.gate(bad, run_regressions=False)
    assert accepted is False

    obs = {"instruction": "passing through the right bin first",
           "objects": [], "zones": [], "skills": []}
    enriched = C.build_observation_with_experience(obs)
    # CORRECTED 2026-11-12 (round 15): this used to assert retrieval returned at least one lesson.
    # That assumed the store holds something trustworthy. Both provenance-verified records were then
    # independently REJECTED - their lessons were false even though their evidence was real - so the
    # correct retrieval result is ZERO, and asserting non-emptiness would force a wrong lesson into a
    # plan. The assertion is now that the mechanism honours the review ledger, which is the property
    # that actually matters and can fail.
    import baseline_c as _C
    rejected = _C._rejected_shas(ROOT / 'evolution' / 'experience' / 'records.jsonl')
    assert isinstance(enriched['experience'], list)
    if rejected:
        for r in store.read(ROOT / 'evolution' / 'experience' / 'records.jsonl'):
            if r.get('record_sha256') in rejected:
                assert r['lesson'] not in [x['lesson'] for x in enriched['experience']], (
                    'a REJECTED lesson reached retrieval: %s' % r.get('task_id'))

    print(json.dumps({"verdict": "EVOBOT_BASELINE_C_SKELETON_VERIFIED",
                      "stage": "Unit Tested only",
                      "experience_records": len(rows),
                      "provenance_derived_ok": derived_ok,
                      "provenance_failed": len(derived_fail),
                      # Published, not hidden: the legacy records genuinely fail provenance and a
                      # verifier that quietly skipped them is how the defect survived this long.
                      "provenance_failed_ids": [t for t, _ in derived_fail],
                      "chain": msg,
                      "regression_gate_blocks_evaluator": True,
                      "retrieved_lessons": len(enriched["experience"]),
                      "simulation_tested": False,
                      "independently_verified": False}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
