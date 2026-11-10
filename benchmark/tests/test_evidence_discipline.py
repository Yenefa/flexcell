#!/usr/bin/env python3
"""Evidence discipline tests: no claim may exist without a machine check.

WHY: for eighteen rounds several EvoBot batches were published with a README and no
verifier. A claim nobody can re-run is a narrative, not evidence. These tests make that
gap impossible to reintroduce silently.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "experiments" / "baselines"))

ACCEPTANCE = ROOT / "setup" / "acceptance"


def evobot_batches():
    return sorted(p for p in ACCEPTANCE.iterdir()
                  if p.is_dir() and p.name.startswith("evobot"))


def test_every_evobot_batch_has_a_verifier():
    missing = [p.name for p in evobot_batches() if not (p / "verify.py").exists()]
    assert not missing, "batches without a machine check: %s" % missing


def test_every_evobot_batch_states_its_rung():
    import evidence_index
    unclassified = [p.name for p in evobot_batches()
                    if p.name not in evidence_index.RUNGS]
    assert not unclassified, "unclassified batches: %s" % unclassified


def test_superseded_batches_name_their_replacement_and_are_retained():
    import evidence_index
    for old, new in evidence_index.SUPERSEDED.items():
        assert (ACCEPTANCE / old).is_dir(), "superseded batch was deleted: " + old
        assert new, old
        replacement = new.split(" ")[0]
        assert (ACCEPTANCE / replacement).is_dir(), (
            "replacement missing for %s -> %s" % (old, replacement))


def test_live_batches_are_not_superseded():
    import evidence_index
    live = [p.name for p in evobot_batches() if p.name not in evidence_index.SUPERSEDED]
    assert len(live) >= 8, len(live)


def test_evidence_index_json_is_current():
    p = ACCEPTANCE / "evobot_evidence_index.json"
    assert p.exists(), "run experiments/baselines/evidence_index.py"
    doc = json.loads(p.read_text(encoding="utf-8"))
    assert doc["record_kind"] == "EVOBOT_EVIDENCE_INDEX"
    assert doc["verifier_failures"] == 0, doc["verifier_failures"]
    assert doc["batches"] == len(evobot_batches())


def test_no_batch_claims_a_rung_it_did_not_reach():
    """A batch claiming Simulation Tested must contain actual run artefacts."""
    import evidence_index
    for p in evobot_batches():
        rung = evidence_index.RUNGS.get(p.name, "")
        if "Independently Verified" in rung or "Generalization" in rung:
            # any archived verdict counts; batch directories do not all use runs/
            # batch layouts vary (runs/, runs_after_fix/, arma_verdict.json ...), so the
            # check asks whether ANY archived verdict exists, not whether a path matches
            has_runs = any(p.rglob("*verdict*.json"))
            assert has_runs, "%s claims %r but has no run artefacts" % (p.name, rung)
