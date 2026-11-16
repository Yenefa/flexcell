#!/usr/bin/env python3
"""Load and score the case files in cases/.

WHY THE CASES ARE DATA AND NOT SEVEN TEST FUNCTIONS
    A defect class is a claim about the world, not about Python: "a run that
    claims success but ends 4 cm from the target must not be accepted". Keeping
    that claim in a reviewable JSON file means a domain reader can check it
    without reading the evaluator, and adding a class is adding a file rather
    than editing a test.

WHY false ACCEPT AND false REJECT ARE COUNTED SEPARATELY
    They are different failures with different costs:

        false accept  a failed repair is published as a fix
        false reject  a working repair is thrown away

    One number cannot express both, and a corpus that only reports accuracy
    hides which one it is making. The summary keeps them apart, and a status
    that is merely wrong in the third way (REJECT where UNKNOWN was expected)
    is reported as a status mismatch rather than being folded into either.

Everything here is stdlib-only.
"""

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import acceptance                                        # noqa: E402
import task_contract                                     # noqa: E402

CASE_SCHEMA = "flexcell.repair_eval.case/1"
CASES_DIRNAME = "cases"
REQUIRED_CASE_KEYS = ("case_id", "contract", "candidate", "expect")


class CaseError(ValueError):
    """A case file that cannot be trusted to test anything."""

    def __init__(self, path, problems):
        self.path = str(path)
        self.problems = list(problems)
        super().__init__("invalid case %s: %s"
                         % (self.path, "; ".join(self.problems)))


def case_paths(directory=None):
    """Every case file, in a stable order (the file names carry the class id)."""
    root = Path(directory) if directory else HERE / CASES_DIRNAME
    return sorted(Path(root).glob("*.json"))


def load(path):
    """Read, validate and return one case.

    Validation happens before the case is used to test anything, because a case
    whose contract is itself invalid would "prove" the evaluator rejects things
    for the wrong reason.
    """
    path = Path(path)
    problems = []
    try:
        case = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise CaseError(path, ["not readable as JSON: %s" % (error,)]) from error
    if not isinstance(case, dict):
        raise CaseError(path, ["case must be an object"])

    for key in REQUIRED_CASE_KEYS:
        if key not in case:
            problems.append("%s: missing" % (key,))
    if case.get("case_schema") != CASE_SCHEMA:
        problems.append("case_schema: expected %r got %r"
                        % (CASE_SCHEMA, case.get("case_schema")))
    if not isinstance(case.get("case_id"), str) or not case.get("case_id", "").strip():
        problems.append("case_id: must be a non-empty string")
    if not isinstance(case.get("candidate"), dict):
        problems.append("candidate: must be an object")

    expect = case.get("expect")
    if not isinstance(expect, dict):
        problems.append("expect: must be an object")
        expect = {}
    status = expect.get("status")
    if status not in acceptance.STATUSES:
        problems.append("expect.status: %r is not one of %s"
                        % (status, acceptance.STATUSES))
    codes = expect.get("codes")
    if not isinstance(codes, list) or not all(isinstance(c, str) for c in codes):
        problems.append("expect.codes: must be a list of reason codes")
        codes = []
    for code in codes:
        if code not in acceptance.REASONS:
            problems.append("expect.codes: %r is not a known reason code" % (code,))
    if status == acceptance.ACCEPT and codes:
        problems.append("expect: an ACCEPT case cannot expect reason codes %r"
                        % (codes,))
    if status != acceptance.ACCEPT and not codes:
        problems.append("expect: a non-ACCEPT case must name the reason code(s) "
                        "that justify it, otherwise a rejection for any reason "
                        "would pass")

    contract = case.get("contract")
    problems += ["contract." + problem
                 for problem in task_contract.validate(contract)]
    if problems:
        raise CaseError(path, problems)
    return case


def run(case, contract=None):
    """Judge one loaded case and report what happened versus what was expected."""
    if contract is None:
        contract = task_contract.TaskContract.from_mapping(case["contract"])
    verdict = acceptance.evaluate(contract, case["candidate"])
    expect = case["expect"]
    expected_status = expect["status"]
    expected_codes = sorted(set(expect.get("codes") or []))
    actual_codes = verdict.codes
    codes_exact = bool(expect.get("codes_exact", True))
    codes_ok = (actual_codes == expected_codes if codes_exact
                else set(expected_codes).issubset(actual_codes))
    accepted = verdict.status == acceptance.ACCEPT
    expected_accept = expected_status == acceptance.ACCEPT
    return {
        "case_id": case["case_id"],
        "title": case.get("title", ""),
        "defect_class": case.get("defect_class", ""),
        "expected_status": expected_status,
        "actual_status": verdict.status,
        "status_ok": verdict.status == expected_status,
        "expected_codes": expected_codes,
        "actual_codes": actual_codes,
        "codes_ok": codes_ok,
        "false_accept": bool(accepted and not expected_accept),
        "false_reject": bool(expected_accept and not accepted),
        "failed_checks": verdict.failed_checks(),
        "verdict": verdict,
    }


def run_all(paths=None):
    return [run(load(path)) for path in (paths or case_paths())]


def summary(results):
    """The three numbers that must be zero, zero and the corpus size."""
    return {
        "false_accept": sum(1 for r in results if r["false_accept"]),
        "false_reject": sum(1 for r in results if r["false_reject"]),
        "cases": len(results),
    }


def mismatches(results):
    """Everything that was wrong, whether or not it is an accept/reject error."""
    out = []
    for result in results:
        if result["status_ok"] and result["codes_ok"]:
            continue
        out.append({
            "case_id": result["case_id"],
            "expected_status": result["expected_status"],
            "actual_status": result["actual_status"],
            "expected_codes": result["expected_codes"],
            "actual_codes": result["actual_codes"],
        })
    return out


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if "--summary" not in argv:
        sys.stderr.write("usage: casefile.py --summary\n")
        return 2
    results = run_all()
    payload = summary(results)
    sys.stdout.write(json.dumps(payload) + "\n")
    wrong = mismatches(results)
    for item in wrong:
        sys.stderr.write("case %s: expected %s %s, got %s %s\n"
                         % (item["case_id"], item["expected_status"],
                            item["expected_codes"], item["actual_status"],
                            item["actual_codes"]))
    ok = (payload["false_accept"] == 0 and payload["false_reject"] == 0
          and not wrong)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
