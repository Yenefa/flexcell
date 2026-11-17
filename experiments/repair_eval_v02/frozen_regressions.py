"""The seven #250 oracle cases, executed and retained for each frozen artifact.

These are evaluator-contract regressions. In particular, the synthetic
push_replay field in N3/P1 is not a new physical pushing experiment.
"""
from pathlib import Path

from benchmark.repair_eval.contracts import casefile
import health

CASE_FILES = (
    "n1_claim_success_goal_not_met.json", "n2_tampered_goal_or_threshold.json",
    "n3_goal_met_regression_failed.json", "n4_protected_file_modified.json",
    "n5_evidence_missing_run_id_mismatch.json", "n6_pass_text_nonzero_exit.json",
    "p1_valid_repair.json",
)
CASES = Path(casefile.__file__).parent / "cases"


def run(candidate, expected_sha, cases_dir=CASES):
    results = []
    for name in CASE_FILES:
        case_id = name.split("_")[0].upper()
        result = {"case_id": case_id, "evaluated_sha": expected_sha,
                  "scope": "fixed_evaluator_contract_case", "status": "FAIL"}
        try:
            if health.tree_sha(candidate) != expected_sha:
                raise ValueError("frozen candidate changed before regression")
            path = Path(cases_dir) / name
            result["case_sha256"] = health.file_sha(path)
            observed = casefile.run(casefile.load(path))
            if observed["case_id"] != case_id:
                raise ValueError("case identity changed")
            result.update({k: v for k, v in observed.items() if k != "verdict"})
            if health.tree_sha(candidate) != expected_sha:
                raise ValueError("frozen candidate changed during regression")
            result["status"] = "PASS" if observed["status_ok"] and observed["codes_ok"] else "FAIL"
        except Exception as exc:
            result["error"] = "%s: %s" % (type(exc).__name__, exc)
        results.append(result)
    return results
