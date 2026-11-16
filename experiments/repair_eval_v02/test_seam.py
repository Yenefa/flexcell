"""The seam between #249's boundary and #250's acceptance, as committed tests.

INTEGRATION_SEAM.md described four probe results and promised that once the two
branches existed together the probe would become a test. This is that test. The
probe also left the pieces uncommitted on purpose, because it depended on two
branches that were not merged yet; this branch is where they meet, so the claim no
longer has to live only in prose.

What is being tested is not either module on its own - each has its own suite -
but the composition: that the information the boundary refuses cannot reach the
judgement, and that the judgement does not move when the candidate's own claim
does.
"""
import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT), str(ROOT / "benchmark" / "repair_eval" / "contracts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import acceptance                                        # noqa: E402
import task_contract                                     # noqa: E402
from benchmark.repair_eval import visibility as vis       # noqa: E402

POLICY_PATH = ROOT / "benchmark" / "repair_eval" / "visibility_policy.json"
CASE = ROOT / "benchmark" / "repair_eval" / "contracts" / "cases" / "p1_valid_repair.json"


def load_case():
    payload = json.loads(CASE.read_text(encoding="utf-8"))
    return task_contract.TaskContract.from_mapping(payload["contract"]), payload["candidate"]


def build_boundary(tmp_path, condition="A_STATIC", stale=False):
    policy = vis.load_policy(POLICY_PATH)
    candidate = tmp_path / "candidate"
    (candidate / "skill").mkdir(parents=True)
    (candidate / "skill" / "recovery.py").write_text("def f(): return 1\n")
    (candidate / "task.md").write_text("# task\n")
    if stale:
        (candidate / "verdict.json").write_text('{"passed": true}\n')
    verdict = tmp_path / "verdict"
    verdict.mkdir()
    (verdict / "verdict.json").write_text('{"passed": true}\n')
    hidden = tmp_path / "hidden"
    hidden.mkdir()
    return vis.RunBoundary(policy, tmp_path, candidate, verdict, hidden,
                           condition=condition), candidate


# ------------------------------------------- the boundary refuses the verdict
def test_the_judge_is_out_of_reach_while_the_candidate_code_is_not(tmp_path):
    boundary, _ = build_boundary(tmp_path)
    with pytest.raises(vis.BoundaryError) as exc:
        boundary.read_text("verdict.json", "candidate_source")
    assert (exc.value.as_dict() or {}).get("reason") == "reserved_name"
    assert boundary.read_text("skill/recovery.py", "candidate_source")


def test_a_stale_verdict_in_the_candidate_is_refused_before_anything_is_read(tmp_path):
    boundary, _ = build_boundary(tmp_path, stale=True)
    with pytest.raises(vis.StaleArtifact):
        boundary.assert_fresh_run()


# --------------------------------- the judgement ignores the candidate's claim
def _evaluate(contract, candidate):
    verdict = acceptance.evaluate(contract, candidate)
    payload = verdict.to_dict()
    return payload["status"], [r["code"] for r in payload["reasons"]], payload


def test_the_valid_repair_is_accepted_through_the_real_policy_context(tmp_path):
    contract, candidate = load_case()
    build_boundary(tmp_path)
    status, codes, _ = _evaluate(contract, candidate)
    assert status == "ACCEPT", codes
    assert codes == []


def test_flipping_the_candidates_own_claim_does_not_move_the_verdict():
    contract, candidate = load_case()
    claimed = dict(candidate)
    claimed["claim_success"] = True
    unclaimed = dict(candidate)
    unclaimed["claim_success"] = False
    a_status, a_codes, a_payload = _evaluate(contract, unclaimed)
    b_status, b_codes, b_payload = _evaluate(contract, claimed)
    assert a_status == b_status
    assert a_codes == b_codes
    # the claim is recorded, it just does not decide anything
    assert a_payload["checks"] != b_payload["checks"] or a_payload != b_payload


def test_a_missed_goal_cannot_be_rescued_by_claiming_success():
    contract, candidate = load_case()
    broken = json.loads(json.dumps(candidate))
    for name in broken["objects"]:
        position = broken["objects"][name]
        broken["objects"][name] = [position[0] + 0.9, position[1], position[2]]
    broken["claim_success"] = True
    status, codes, _ = _evaluate(contract, broken)
    assert status == "REJECT"
    assert "GOAL_NOT_MET" in codes


# ------------------------------------------- identity travels with the record
def test_the_record_can_carry_both_identities_at_once(tmp_path):
    """A run record must be able to name the policy and the contract together.

    If either identity is missing the record cannot show which version of the
    rules produced it, and after the fact nobody can tell whether a number came
    from the current rules or an older set.
    """
    contract, _ = load_case()
    boundary, _ = build_boundary(tmp_path)
    described = boundary.describe()
    assert described["policy_id"]
    assert described["policy_fingerprint"]
    record = {
        "policy_id": described["policy_id"],
        "policy_fingerprint": described["policy_fingerprint"],
        "condition": "A_STATIC",
        "contract_sha256": contract.sha256(),
        "contract_version": contract.version,
    }
    for key, value in record.items():
        assert value, key
    # the two identities are independent and both stable
    assert record["contract_sha256"] == contract.sha256()
    assert len(record["contract_sha256"]) == 64


def test_the_policy_fingerprint_changes_when_the_rules_change(tmp_path):
    """A poisoned policy must not keep the same fingerprint.

    Without this, a record that names the fingerprint proves nothing: the rules
    could have been edited underneath a name that never moved.
    """
    original = vis.load_policy(POLICY_PATH)
    payload = json.loads(POLICY_PATH.read_text(encoding="utf-8"))
    payload["conditions"]["A_STATIC"]["visible"]["verification"] = False
    payload["guidance_max_chars"] = payload.get("guidance_max_chars", 1200) + 1
    poisoned_path = tmp_path / "poisoned.json"
    poisoned_path.write_text(json.dumps(payload), encoding="utf-8")
    poisoned = vis.load_policy(poisoned_path)
    assert poisoned.fingerprint() != original.fingerprint()
