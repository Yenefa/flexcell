#!/usr/bin/env python3
"""Acceptance tests for the task contract and its negative corpus.

WHAT THESE TESTS ARE FOR
    Not "does evaluate() run". A function that returns REJECT for everything
    would pass that. These tests pin the two properties the paper needs:

    1. The ruler is the contract. No self-report, no candidate-supplied goal
       and no candidate-supplied threshold can move a verdict.
    2. Every gate is load-bearing. Each gate is removed or violated one at a
       time from a valid repair, and each removal must be caught by name.

WHY EACH NEGATIVE ASSERTS A NAMED CODE
    Asserting only "not ACCEPT" would let a case pass for the wrong reason - a
    candidate that fails schema validation also returns REJECT. Each case
    therefore asserts the exact reason-code set, so N1..N6 cannot collapse into
    one another.

WHY FALSE ACCEPT AND FALSE REJECT ARE COUNTED SEPARATELY
    They cost different things: a false accept publishes a broken repair as a
    fix, a false reject throws away a working one. The summary keeps them apart
    and a third outcome (REJECT where UNKNOWN was expected) is reported as a
    status mismatch rather than being folded into either.

Run:
    python3 -m pytest benchmark/repair_eval/contracts -q
    python3 benchmark/repair_eval/contracts/test_contract.py --summary
"""

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

if __package__:
    from . import acceptance, casefile, task_contract
else:
    import acceptance
    import casefile
    import task_contract

CASES = casefile.case_paths()
CASE_IDS = [path.stem for path in CASES]


# --------------------------------------------------------------------- helpers
def load_case(name="p1_valid_repair"):
    """Load one case by file stem, e.g. 'p1_valid_repair'."""
    return casefile.load(HERE / "cases" / (name + ".json"))


def contract_of(name="p1_valid_repair"):
    return task_contract.TaskContract.from_mapping(load_case(name)["contract"])


def candidate_of(name="p1_valid_repair"):
    """Always a copy: a test that mutates the shared fixture would poison the rest."""
    return copy.deepcopy(load_case(name)["candidate"])


def verdict_for(candidate, name="p1_valid_repair"):
    return acceptance.evaluate(contract_of(name), candidate)


def check_named(verdict, name):
    for check in verdict.checks:
        if check["check"] == name:
            return check
    raise AssertionError("no check named %r in %r"
                         % (name, [c["check"] for c in verdict.checks]))


# --------------------------------------------------------- contract validation
def _mutations():
    """(id, mutate, expected fragment) for every way a contract can be wrong."""
    def unknown_top_level(mapping):
        mapping["notes"] = "free text"

    def wrong_schema(mapping):
        mapping["schema"] = "flexcell.repair_eval.task_contract/0"

    def missing_task_id(mapping):
        del mapping["task_id"]

    def version_zero(mapping):
        mapping["version"] = 0

    def unknown_immutable_key(mapping):
        mapping["immutable"]["robot"] = "ur5e"

    def missing_threshold(mapping):
        del mapping["immutable"]["thresholds"]["min_regressions"]

    def zero_tolerance(mapping):
        mapping["immutable"]["objects"][0]["tolerance"] = 0

    def object_zone_unknown(mapping):
        mapping["immutable"]["objects"][0]["zone"] = "zone_9"

    def duplicate_object(mapping):
        mapping["immutable"]["objects"].append(
            copy.deepcopy(mapping["immutable"]["objects"][0]))

    def editable_inside_protected(mapping):
        mapping["editable_fields"].append("config/task_goal.yaml:user_goal")

    def run_id_pattern_matches_empty(mapping):
        mapping["run_id_pattern"] = ".*"

    def run_id_pattern_invalid(mapping):
        mapping["run_id_pattern"] = "HO-[0-9a"

    def protected_digest_too_short(mapping):
        mapping["protected_paths"][0]["sha256"] = "abc"

    def thresholds_unknown_key(mapping):
        mapping["immutable"]["thresholds"]["max_lift_m"] = 0.1

    def evidence_empty(mapping):
        mapping["evidence_required"] = []

    def editable_empty(mapping):
        mapping["editable_fields"] = []

    return [
        ("unknown_top_level_field", unknown_top_level, "contract.notes: unknown field"),
        ("wrong_schema", wrong_schema, "schema: expected"),
        ("missing_task_id", missing_task_id, "task_id: missing"),
        ("version_zero", version_zero, "version: must be an integer >= 1"),
        ("unknown_immutable_key", unknown_immutable_key,
         "immutable.robot: unknown field"),
        ("missing_threshold", missing_threshold,
         "immutable.thresholds.min_regressions: missing"),
        ("zero_tolerance", zero_tolerance,
         "immutable.objects[0].tolerance: must be a finite number > 0"),
        ("object_zone_unknown", object_zone_unknown,
         "immutable.objects[0].zone: 'zone_9' is not a declared zone"),
        ("duplicate_object", duplicate_object,
         "immutable.objects[2].name: duplicate object name"),
        ("editable_inside_protected", editable_inside_protected,
         "is editable but also protected"),
        ("run_id_pattern_matches_empty", run_id_pattern_matches_empty,
         "matches the empty string"),
        ("run_id_pattern_invalid", run_id_pattern_invalid,
         "not a valid regular expression"),
        ("protected_digest_too_short", protected_digest_too_short,
         "must be a 64-character lowercase sha256 hex digest"),
        ("thresholds_unknown_key", thresholds_unknown_key,
         "immutable.thresholds.max_lift_m: unknown field"),
        ("evidence_empty", evidence_empty, "evidence_required: must be a non-empty list"),
        ("editable_empty", editable_empty, "editable_fields: must be a non-empty list"),
    ]


MUTATIONS = _mutations()
MUTATION_IDS = [item[0] for item in MUTATIONS]


def test_the_case_contract_is_valid():
    assert task_contract.validate(load_case()["contract"]) == []


@pytest.mark.parametrize("name,mutate,fragment", MUTATIONS, ids=MUTATION_IDS)
def test_validate_rejects(name, mutate, fragment):
    mapping = load_case()["contract"]
    mutate(mapping)
    problems = task_contract.validate(mapping)
    assert problems, "a mutated contract was accepted: %s" % (name,)
    assert any(fragment in problem for problem in problems), (
        "%s was rejected for the wrong reason: %r" % (name, problems))


@pytest.mark.parametrize("name,mutate,fragment", MUTATIONS, ids=MUTATION_IDS)
def test_from_mapping_refuses_to_build(name, mutate, fragment):
    mapping = load_case()["contract"]
    mutate(mapping)
    with pytest.raises(task_contract.ContractError) as caught:
        task_contract.TaskContract.from_mapping(mapping)
    assert any(fragment in problem for problem in caught.value.problems)


def test_contract_error_carries_every_problem():
    mapping = load_case()["contract"]
    mapping["version"] = 0
    mapping["notes"] = "free text"
    with pytest.raises(task_contract.ContractError) as caught:
        task_contract.TaskContract.from_mapping(mapping)
    assert len(caught.value.problems) >= 2, caught.value.problems


def test_canonical_json_is_insertion_order_independent():
    mapping = load_case()["contract"]
    reordered = {key: mapping[key] for key in reversed(list(mapping))}
    assert (task_contract.TaskContract.from_mapping(reordered).sha256()
            == task_contract.TaskContract.from_mapping(mapping).sha256())


def test_sha256_is_a_stable_64_character_digest():
    digest = contract_of().sha256()
    assert len(digest) == 64
    assert int(digest, 16) >= 0
    assert digest == contract_of().sha256()


def test_accessors_do_not_leak_internal_state():
    contract = contract_of()
    before = contract.sha256()
    objects = contract.objects
    objects[0]["tolerance"] = 99.0
    thresholds = contract.thresholds
    thresholds["max_position_error_m"] = 99.0
    assert contract.sha256() == before
    assert contract.thresholds["max_position_error_m"] == 0.02


# ------------------------------------------------------- editable/protected line
@pytest.mark.parametrize("path,editable,code", [
    ("config/controller.yaml:kp", True, task_contract.EDITABLE_FIELD),
    ("config/controller.yaml:kv", True, task_contract.EDITABLE_FIELD),
    # A member-scoped authorisation covers that member only: retuning kp does
    # not authorise rewriting the file or a neighbouring gain.
    ("config/controller.yaml:kd", False, task_contract.UNDECLARED_PATH),
    ("config/controller.yaml", False, task_contract.UNDECLARED_PATH),
    ("scripts/grasp_timing.py:approach_dwell_s", True, task_contract.EDITABLE_FIELD),
    ("config/task_goal.yaml", False, task_contract.PROTECTED_PATH),
    ("config/acceptance_policy.yaml", False, task_contract.PROTECTED_PATH),
    ("src/flexcell/flexcell_skills/pick_server.py", False,
     task_contract.UNDECLARED_PATH),
])
def test_edit_boundary(path, editable, code):
    assert contract_of().classify_path(path) == (editable, code)


@pytest.mark.parametrize("run_id,expected", [
    ("HO-38ce6531a597", True),
    ("HO-000000000000", True),
    ("run-20261116-001", False),
    ("HO-38CE6531A597", False),
    ("", False),
    (None, False),
])
def test_run_id_pattern(run_id, expected):
    assert contract_of().matches_run_id(run_id) is expected


def test_effective_tolerance_takes_the_stricter_number():
    contract = contract_of()
    strict_tolerance = {"name": "block_a", "position": [0.0, 0.0, 0.0],
                        "tolerance": 0.001}
    loose_tolerance = {"name": "block_a", "position": [0.0, 0.0, 0.0],
                       "tolerance": 0.5}
    assert contract.effective_tolerance(strict_tolerance) == 0.001
    assert contract.effective_tolerance(loose_tolerance) == 0.02


# ------------------------------------------------------------------ case corpus
def test_the_corpus_has_the_seven_declared_cases():
    ids = [casefile.load(path)["case_id"] for path in CASES]
    assert ids == ["N1", "N2", "N3", "N4", "N5", "N6", "P1"], ids


def test_every_case_is_judged_against_the_same_frozen_contract():
    digests = {casefile.load(path)["case_id"]:
               task_contract.TaskContract.from_mapping(
                   casefile.load(path)["contract"]).sha256()
               for path in CASES}
    assert len(set(digests.values())) == 1, digests


@pytest.mark.parametrize("case_path", CASES, ids=CASE_IDS)
def test_case_verdict_matches_its_expectation(case_path):
    case = casefile.load(case_path)
    result = casefile.run(case)
    expect = case["expect"]

    assert result["actual_status"] == expect["status"], {
        "case": result["case_id"],
        "expected": expect["status"],
        "actual": result["actual_status"],
        "reasons": result["verdict"].reasons,
        "failed_checks": result["failed_checks"],
    }
    assert result["actual_codes"] == sorted(expect["codes"]), (
        "case %s was decided for the wrong reason" % (result["case_id"],))

    severities = {acceptance.REASONS[code][0] for code in result["actual_codes"]}
    if expect["status"] == acceptance.ACCEPT:
        assert result["verdict"].reasons == [], result["verdict"].reasons
        assert not result["false_accept"]
    elif expect["status"] == acceptance.REJECT:
        # A rejection must be a measured violation, never an unmeasurable gate.
        assert severities == {acceptance.REJECT}, result["actual_codes"]
    else:
        assert severities == {acceptance.UNKNOWN}, result["actual_codes"]
        assert result["verdict"].accepted is False


@pytest.mark.parametrize("case_path", CASES, ids=CASE_IDS)
def test_each_case_is_deterministic(case_path):
    case = casefile.load(case_path)
    first = casefile.run(case)["verdict"].to_dict()
    second = casefile.run(case)["verdict"].to_dict()
    assert first == second
    # The verdict must be transportable as JSON: a NaN would silently become
    # null in a report and take the reason with it.
    json.dumps(first, allow_nan=False)


def test_case_order_does_not_matter():
    forward = [(r["case_id"], r["actual_status"], r["actual_codes"])
               for r in casefile.run_all(CASES)]
    backward = [(r["case_id"], r["actual_status"], r["actual_codes"])
                for r in casefile.run_all(list(reversed(CASES)))]
    assert forward == list(reversed(backward))


def test_summary_reports_no_false_accept_and_no_false_reject():
    results = casefile.run_all()
    payload = casefile.summary(results)
    assert payload == {"false_accept": 0, "false_reject": 0, "cases": 7}, payload
    assert casefile.mismatches(results) == []


# ---------------------------------------------------------------- claim handling
@pytest.mark.parametrize("case_path", CASES, ids=CASE_IDS)
def test_claim_cannot_move_the_verdict(case_path):
    case = casefile.load(case_path)
    contract = task_contract.TaskContract.from_mapping(case["contract"])
    baseline_candidate = copy.deepcopy(case["candidate"])
    baseline_candidate.pop("claim_success", None)
    baseline = acceptance.evaluate(contract, baseline_candidate)

    for claim in (True, False, "true", 1, None):
        candidate = copy.deepcopy(baseline_candidate)
        candidate["claim_success"] = claim
        verdict = acceptance.evaluate(contract, candidate)
        assert verdict.status == baseline.status, (claim, case["case_id"])
        assert verdict.codes == baseline.codes, (claim, case["case_id"])
        assert verdict.failed_checks() == baseline.failed_checks()


def test_missing_claim_is_recorded_as_absent_not_false():
    candidate = candidate_of()
    candidate.pop("claim_success")
    claim = check_named(verdict_for(candidate), "claim")["evidence"]
    assert claim["claim_present"] is False
    assert claim["claim_success"] is None
    assert claim["used_for_decision"] is False


def test_false_success_and_false_failure_are_kept_apart():
    honest_failure = candidate_of("n1_claim_success_goal_not_met")
    failed = check_named(verdict_for(honest_failure,
                                     "n1_claim_success_goal_not_met"), "claim")
    assert failed["evidence"]["false_success"] is True
    assert failed["evidence"]["false_failure"] is False

    unclaimed_fix = candidate_of()
    fixed = check_named(verdict_for(unclaimed_fix), "claim")
    assert fixed["evidence"]["false_success"] is False
    assert fixed["evidence"]["false_failure"] is True


# ------------------------------------------------------------ gate load-bearing
def _gates():
    """One degradation per gate, applied to the valid repair."""
    def goal_not_met(candidate):
        candidate["objects"]["block_a"] = [0.16, -0.15, 0.0175]

    def goal_unmeasured(candidate):
        candidate["objects"].pop("block_a")

    def regression_failed(candidate):
        candidate["regressions"][0]["status"] = "FAIL"

    def regression_short(candidate):
        candidate["regressions"] = candidate["regressions"][:1]

    def regression_unusable(candidate):
        candidate["regressions"][1]["status"] = "SKIPPED"

    def protected_modified(candidate):
        candidate["protected_hashes"]["config/task_goal.yaml"] = "0" * 64

    def protected_unverifiable(candidate):
        candidate["protected_hashes"].pop("config/task_goal.yaml")

    def evidence_missing(candidate):
        candidate["evidence"] = [entry for entry in candidate["evidence"]
                                 if entry["name"] != "run_manifest"]

    def evidence_malformed(candidate):
        candidate["evidence"][0]["sha256"] = "not-a-digest"

    def run_id_mismatch(candidate):
        candidate["run_id"] = "run-20261116-001"

    def nonzero_exit(candidate):
        candidate["exit_code"] = 3

    def exit_missing(candidate):
        candidate["exit_code"] = None

    def unauthorized_edit(candidate):
        candidate["changed_files"] = ["config/controller.yaml:kd"]

    def changed_files_unreported(candidate):
        candidate.pop("changed_files")

    def task_mismatch(candidate):
        candidate["task_id"] = "repair-other-999"

    return [
        ("goal_not_met", goal_not_met, "GOAL_NOT_MET"),
        ("goal_unmeasured", goal_unmeasured, "GOAL_UNMEASURED"),
        ("regression_failed", regression_failed, "REGRESSION_FAILED"),
        ("regression_short", regression_short, "REGRESSION_MISSING"),
        ("regression_unusable", regression_unusable, "REGRESSION_MISSING"),
        ("protected_modified", protected_modified, "PROTECTED_MODIFIED"),
        ("protected_unverifiable", protected_unverifiable, "PROTECTED_UNVERIFIABLE"),
        ("evidence_missing", evidence_missing, "EVIDENCE_MISSING"),
        ("evidence_malformed", evidence_malformed, "EVIDENCE_MISSING"),
        ("run_id_mismatch", run_id_mismatch, "RUN_ID_MISMATCH"),
        ("nonzero_exit", nonzero_exit, "NONZERO_EXIT"),
        ("exit_missing", exit_missing, "EXIT_CODE_MISSING"),
        ("unauthorized_edit", unauthorized_edit, "UNAUTHORIZED_EDIT"),
        ("changed_files_unreported", changed_files_unreported,
         "CHANGED_FILES_UNREPORTED"),
        ("task_mismatch", task_mismatch, "TASK_MISMATCH"),
    ]


GATES = _gates()
GATE_IDS = [item[0] for item in GATES]


@pytest.mark.parametrize("name,degrade,code", GATES, ids=GATE_IDS)
def test_every_gate_is_load_bearing(name, degrade, code):
    candidate = candidate_of()
    degrade(candidate)
    verdict = verdict_for(candidate)
    assert verdict.status != acceptance.ACCEPT, (
        "the valid repair was still accepted after %s" % (name,))
    assert code in verdict.codes, (name, verdict.codes)
    severity = acceptance.REASONS[code][0]
    assert verdict.status == severity, (name, severity, verdict.status)


def test_an_acceptance_needs_every_gate_to_have_passed():
    verdict = verdict_for(candidate_of())
    assert verdict.status == acceptance.ACCEPT
    assert verdict.reasons == []
    assert verdict.failed_checks() == []
    # Every check is positive, so nothing was skipped on the way to a pass.
    assert all(check["ok"] for check in verdict.checks)


# -------------------------------------------------------------------- tampering
def test_tampered_threshold_cannot_widen_acceptance():
    name = "n1_claim_success_goal_not_met"
    candidate = candidate_of(name)
    candidate["reported_thresholds"] = {"max_position_error_m": 0.5}
    verdict = verdict_for(candidate, name)

    assert verdict.status == acceptance.REJECT
    assert verdict.codes == ["GOAL_NOT_MET", "TAMPERED_IMMUTABLE"]
    tolerance = check_named(verdict, "goal:block_a")["evidence"]
    # 0.5 was supplied; 0.02 was used. The contract's number is the only one
    # that can decide, and the record says so.
    assert tolerance["tolerance_m"] == 0.02
    assert tolerance["tolerance_source"] == "contract"


def test_tampered_goal_cannot_move_the_target():
    candidate = candidate_of()
    candidate["reported_goal"] = {"block_a": [0.30, 0.30, 0.0],
                                  "block_b": [0.30, 0.30, 0.0]}
    verdict = verdict_for(candidate)

    assert verdict.status == acceptance.REJECT
    assert verdict.codes == ["TAMPERED_IMMUTABLE"]
    evidence = check_named(verdict, "goal:block_a")["evidence"]
    assert evidence["required_position"] == [0.12, -0.15, 0.0175]
    assert evidence["distance_m"] == pytest.approx(0.001921, abs=1e-6)


def test_tampered_echo_is_recorded_with_the_paths_it_used():
    candidate = candidate_of()
    candidate["immutable"] = {"user_goal": "whatever I like"}
    verdict = verdict_for(candidate)
    assert verdict.status == acceptance.REJECT
    tampering = check_named(verdict, "immutable_not_restated")["evidence"]
    assert tampering["tampered_paths"] == ["$.immutable", "$.immutable.user_goal"]
    assert tampering["contract_sha256"] == contract_of().sha256()


# ------------------------------------------------------- unknown is never a pass
def test_unknown_evidence_is_never_reported_as_a_pass():
    candidate = candidate_of()
    candidate["evidence"] = []
    verdict = verdict_for(candidate)
    assert verdict.status == acceptance.UNKNOWN
    assert verdict.accepted is False
    assert acceptance.UNKNOWN in {acceptance.REASONS[c][0] for c in verdict.codes}


def test_malformed_candidate_is_unknown_not_rejected():
    verdict = verdict_for(["not", "a", "mapping"])
    assert verdict.status == acceptance.UNKNOWN
    assert verdict.codes == ["CANDIDATE_MALFORMED"]


def test_verdict_carries_the_digest_of_the_contract_that_produced_it():
    for case_path in CASES:
        case = casefile.load(case_path)
        contract = task_contract.TaskContract.from_mapping(case["contract"])
        verdict = acceptance.evaluate(contract, case["candidate"])
        assert verdict.contract_sha256 == contract.sha256()
        assert verdict.task_id == contract.task_id
        assert verdict.contract_version == contract.version


def test_evaluate_rejects_a_contract_that_is_not_a_task_contract():
    with pytest.raises(TypeError):
        acceptance.evaluate(load_case()["contract"], candidate_of())


def test_a_measured_violation_outranks_a_missing_gate():
    # REJECT wins over UNKNOWN: missing evidence cannot make a violated
    # tolerance true, and reporting UNKNOWN here would let a broken repair hide
    # behind an incomplete bundle.
    candidate = candidate_of()
    candidate["objects"]["block_a"] = [0.16, -0.15, 0.0175]
    candidate["evidence"] = []
    verdict = verdict_for(candidate)
    assert verdict.status == acceptance.REJECT
    assert verdict.codes == ["EVIDENCE_MISSING", "GOAL_NOT_MET"]


def test_editing_the_goal_changes_the_frozen_digest():
    # The digest is the freeze marker: if a threshold could be edited without
    # changing it, a run could be re-graded against a widened ruler.
    mapping = load_case()["contract"]
    baseline = task_contract.TaskContract.from_mapping(mapping).sha256()
    mapping["immutable"]["thresholds"]["max_position_error_m"] = 0.5
    widened = task_contract.TaskContract.from_mapping(mapping)
    assert widened.sha256() != baseline


# ------------------------------------------------- object names are data, not schema
# These two defects were found by running the whole 24-slot matrix, not by the
# corpus: both produce a false REJECT, which turns no test red and instead drives
# the reported success rate to zero while looking like the repairs all failed.
COLLIDING_OBJECT_NAMES = ("target", "goal", "version", "zones", "tolerance",
                          "editable_fields", "protected_paths")


def _contract_with_object_named(name):
    mapping = load_case()["contract"]
    for obj in mapping["immutable"]["objects"]:
        if obj["name"] == "block_a":
            obj["name"] = name
    return task_contract.TaskContract.from_mapping(mapping)


@pytest.mark.parametrize("name", COLLIDING_OBJECT_NAMES)
def test_an_object_named_like_a_schema_field_is_not_tampering(name):
    # "target" is the most natural object name there is. Scanning object keys as
    # schema fields made every run of such a task REJECT with TAMPERED_IMMUTABLE:
    # the evaluator accusing the repair of cheating when the bug was its own.
    contract = _contract_with_object_named(name)
    candidate = candidate_of()
    candidate["objects"] = {name: [0.12, -0.15, 0.0175],
                            "block_b": [0.25, 0.05, 0.0175]}
    verdict = acceptance.evaluate(contract, candidate)
    assert verdict.status == acceptance.ACCEPT, verdict.reasons
    assert verdict.reasons == []


def test_a_schema_field_key_is_still_tampering_at_the_top_level():
    # The fix narrows the scan; it must not blunt it. A top-level "zones" is a
    # restated schema field no matter what lives inside "objects".
    candidate = candidate_of()
    candidate["zones"] = [{"name": "z", "position": [0.0, 0.0, 0.0], "radius": 9.0}]
    candidate["objects"]["target"] = [0.12, -0.15, 0.0175]
    verdict = verdict_for(candidate)
    assert verdict.status == acceptance.REJECT
    assert verdict.codes == ["TAMPERED_IMMUTABLE"]
    hits = check_named(verdict, "immutable_not_restated")["evidence"]["tampered_paths"]
    assert hits == ["$.zones"], hits


def test_the_container_key_is_still_checked_but_its_contents_are_not():
    # The distinction the fix draws: a top-level "thresholds" is a restated
    # schema field; a "tolerance" inside "objects" is an object's name. Both
    # halves matter - skipping the whole scan would hide real tampering.
    candidate = candidate_of()
    candidate["objects"]["tolerance"] = [0.12, -0.15, 0.0175]   # object name
    verdict = verdict_for(candidate)
    assert verdict.codes == [], verdict.reasons

    candidate = candidate_of()
    candidate["thresholds"] = {"max_position_error_m": 0.5}     # schema field
    verdict = verdict_for(candidate)
    assert verdict.codes == ["TAMPERED_IMMUTABLE"]
    hits = check_named(verdict, "immutable_not_restated")["evidence"]["tampered_paths"]
    assert hits == ["$.thresholds"], hits


# ------------------------------------------------------- directory authorisations
@pytest.mark.parametrize("field", ["skill/", "skill", "skill/registry.py"])
def test_directory_and_file_authorisations_agree(field):
    # "skill/" used to authorise nothing: split_path kept the trailing slash while
    # _normalise stripped it, so the root became "skill//" and startswith() never
    # matched. The contract validated, so the author could not see the mistake
    # until the whole matrix came back UNAUTHORIZED_EDIT.
    mapping = load_case()["contract"]
    mapping["editable_fields"] = [field]
    contract = task_contract.TaskContract.from_mapping(mapping)
    assert contract.classify_path("skill/registry.py") == (
        True, task_contract.EDITABLE_FIELD)


def test_a_directory_authorisation_covers_the_directory_but_a_file_does_not():
    mapping = load_case()["contract"]
    mapping["editable_fields"] = ["skill"]
    directory = task_contract.TaskContract.from_mapping(mapping)
    assert directory.is_editable("skill/nested/deep.py") is True
    assert directory.is_editable("skill_other/x.py") is False

    mapping = load_case()["contract"]
    mapping["editable_fields"] = ["skill/registry.py"]
    single = task_contract.TaskContract.from_mapping(mapping)
    assert single.is_editable("skill/registry.py") is True
    assert single.is_editable("skill/other.py") is False


def test_split_path_normalises_the_file_part():
    assert task_contract.split_path("skill/") == ("skill", None)
    assert task_contract.split_path("skill/registry.py") == ("skill/registry.py", None)
    assert task_contract.split_path("config/controller.yaml:kp") == (
        "config/controller.yaml", "kp")
    assert task_contract.split_path(" skill/ ") == ("skill", None)


def test_an_editable_field_that_cannot_match_itself_is_refused():
    # Self-consistency is checkable at contract-build time. Discovering it after
    # the run is how a configuration mistake becomes "every repair failed".
    for bad in (":kp", "/"):
        mapping = load_case()["contract"]
        mapping["editable_fields"] = [bad]
        assert task_contract.validate(mapping), bad
    for good in ("skill/", "skill", "skill/registry.py",
                 "config/controller.yaml:kp"):
        mapping = load_case()["contract"]
        mapping["editable_fields"] = [good]
        assert task_contract.validate(mapping) == [], good


# --------------------------------------------------- candidate report format
def test_every_case_declares_the_candidate_schema():
    # A case that lost its format tag would be judged UNKNOWN and would stop
    # testing the defect class it was written for.
    for case_path in CASES:
        candidate = casefile.load(case_path)["candidate"]
        assert candidate.get("candidate_schema") == acceptance.CANDIDATE_SCHEMA, (
            case_path.name)


def test_a_report_from_another_harness_is_unknown():
    candidate = candidate_of()
    candidate["candidate_schema"] = "some-other-harness/7"
    verdict = verdict_for(candidate)
    assert verdict.status == acceptance.UNKNOWN
    assert verdict.codes == ["CANDIDATE_MALFORMED"]
    assert verdict.accepted is False


def test_a_report_without_a_schema_is_unknown():
    candidate = candidate_of()
    candidate.pop("candidate_schema")
    verdict = verdict_for(candidate)
    assert verdict.status == acceptance.UNKNOWN
    assert verdict.codes == ["CANDIDATE_MALFORMED"]


def test_an_unknown_schema_stops_before_reading_the_rest():
    # The formats we do not know may use "objects" for something else, so nothing
    # in such a report may decide anything - not even to reject it.
    candidate = candidate_of()
    candidate["candidate_schema"] = "some-other-harness/7"
    candidate["objects"]["block_a"] = [0.30, 0.30, 0.0]    # looks like a goal miss
    candidate["exit_code"] = 1                             # looks like a failure
    verdict = verdict_for(candidate)
    assert verdict.status == acceptance.UNKNOWN
    assert verdict.codes == ["CANDIDATE_MALFORMED"]
    assert verdict.failed_checks() == ["candidate_schema"]


def test_a_wrong_schema_can_never_be_accepted():
    # Negative control: deleting the format gate makes this fail, on every case.
    for case_path in CASES:
        case = casefile.load(case_path)
        contract = task_contract.TaskContract.from_mapping(case["contract"])
        candidate = copy.deepcopy(case["candidate"])
        candidate["candidate_schema"] = "some-other-harness/7"
        verdict = acceptance.evaluate(contract, candidate)
        assert verdict.status != acceptance.ACCEPT, case["case_id"]


def test_an_equal_contract_identity_echo_is_recorded_not_punished():
    # The collector may stamp the report with the contract it believes it ran
    # under. That is provenance: a match must be visible and must change nothing.
    contract = contract_of()
    candidate = candidate_of()
    candidate["contract_version"] = contract.version
    candidate["contract_sha256"] = contract.sha256()
    verdict = verdict_for(candidate)
    assert verdict.status == acceptance.ACCEPT
    assert verdict.reasons == []
    echo = check_named(verdict, "contract_identity_echo")
    assert echo["ok"] is True
    assert echo["informational"] is True
    assert echo["evidence"]["declared"] == {
        "contract_version": contract.version,
        "contract_sha256": contract.sha256()}


def test_a_mismatched_contract_identity_is_a_task_mismatch():
    # Reusing TAMPERED_IMMUTABLE here would merge "the report names another
    # rulebook" with "the candidate edited the ruler", and the six defect classes
    # would stop being separable by code. True is included because it compares
    # equal to 1 as an int and must still be refused.
    for key, value in (("contract_version", 2),
                       ("contract_sha256", "0" * 64),
                       ("contract_version", True)):
        candidate = candidate_of()
        candidate[key] = value
        verdict = verdict_for(candidate)
        assert verdict.status == acceptance.REJECT, (key, value)
        assert verdict.codes == ["TASK_MISMATCH"], (key, value)


def test_an_absent_contract_identity_changes_nothing():
    # The seven corpus cases declare neither field, which must stay normal.
    for case_path in CASES:
        case = casefile.load(case_path)
        contract = task_contract.TaskContract.from_mapping(case["contract"])
        verdict = acceptance.evaluate(contract, case["candidate"])
        names = [entry["check"] for entry in verdict.checks]
        assert "contract_identity_echo" not in names, case["case_id"]
    assert verdict_for(candidate_of()).status == acceptance.ACCEPT


# ------------------------------------------------------- importability contract
REPO_ROOT = HERE.parents[2]


def run_from_repository_root(argv):
    return subprocess.run(argv, cwd=str(REPO_ROOT), capture_output=True,
                          text=True, timeout=180)


def test_the_package_imports_from_the_repository_root():
    # A flat "import task_contract" made this fail: a module imported by package
    # path cannot see its siblings. #252 consumes this as a library, so the
    # package form is the one that has to work.
    proc = run_from_repository_root(
        [sys.executable, "-c",
         "import benchmark.repair_eval.contracts.acceptance"])
    assert proc.returncode == 0, proc.stderr


def test_the_package_entry_point_prints_the_summary():
    proc = run_from_repository_root(
        [sys.executable, "-m", "benchmark.repair_eval.contracts.test_contract",
         "--summary"])
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout.strip()) == {
        "false_accept": 0, "false_reject": 0, "cases": 7}


def test_package_level_objects_share_one_class():
    # Package import must not create a second TaskContract: two copies would make
    # evaluate() raise TypeError on the caller's own contract, which is exactly
    # the silent wiring failure this follow-up closes.
    script = (
        "from benchmark.repair_eval.contracts import acceptance, casefile, "
        "task_contract\n"
        "case = casefile.load("
        "'benchmark/repair_eval/contracts/cases/p1_valid_repair.json')\n"
        "contract = task_contract.TaskContract.from_mapping(case['contract'])\n"
        "verdict = acceptance.evaluate(contract, case['candidate'])\n"
        "print(verdict.status)\n"
    )
    proc = run_from_repository_root([sys.executable, "-c", script])
    assert proc.returncode == 0, proc.stderr
    assert proc.stdout.strip() == "ACCEPT"


# -------------------------------------------------------------------------- cli
@pytest.mark.parametrize("script", [
    str(HERE / "casefile.py"),
    str(HERE / "test_contract.py"),
], ids=["casefile", "test_contract"])
def test_summary_command_prints_the_three_numbers(script):
    proc = subprocess.run([sys.executable, script, "--summary"],
                          cwd=str(HERE), capture_output=True, text=True, timeout=120)
    assert proc.returncode == 0, proc.stderr
    assert json.loads(proc.stdout.strip()) == {
        "false_accept": 0, "false_reject": 0, "cases": 7}


def main(argv=None):
    """Print the corpus summary. Used by the one-command check in the docs."""
    return casefile.main(argv)


if __name__ == "__main__":
    sys.exit(main())
