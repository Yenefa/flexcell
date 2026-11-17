"""A regression must testify once, under its own name.

MEASURED 2026-11-17 (review): usable records were counted by length. Deleting a
real regression from the valid case and duplicating another PASS record still
produced ACCEPT, because two anonymous PASS lines satisfied min_regressions=2.
Duplicate identities are now refused, and a record with no name cannot testify.
"""
import copy
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for path in (str(HERE), str(HERE.parents[1]), str(HERE.parents[2])):
    if path not in sys.path:
        sys.path.insert(0, path)

from test_contract import contract_of, candidate_of, verdict_for  # noqa: E402


def _candidate():
    return copy.deepcopy(candidate_of("p1_valid_repair"))


def _regressions(candidate):
    return candidate["regressions"]


def test_the_valid_case_still_passes():
    assert verdict_for(_candidate()).status == "ACCEPT"


def test_duplicating_a_pass_does_not_replace_the_missing_regression():
    candidate = _candidate()
    records = _regressions(candidate)
    # keep the contract's two regressions honest, then make the second a copy
    records[1] = copy.deepcopy(records[0])
    verdict = verdict_for(candidate)
    assert verdict.status != "ACCEPT", verdict.to_dict()
    codes = [reason.get("code") for reason in verdict.to_dict().get("reasons", [])]
    assert "REGRESSION_DUPLICATE" in codes, codes


def test_an_unnamed_regression_cannot_testify():
    candidate = _candidate()
    for record in _regressions(candidate):
        record.pop("name", None)
    verdict = verdict_for(candidate)
    assert verdict.status != "ACCEPT", verdict.to_dict()
    codes = [reason.get("code") for reason in verdict.to_dict().get("reasons", [])]
    assert "REGRESSION_UNNAMED" in codes, codes


def test_two_distinct_names_are_still_fine():
    candidate = _candidate()
    records = _regressions(candidate)
    records[0]["name"] = "regression_one"
    records[1]["name"] = "regression_two"
    assert verdict_for(candidate).status == "ACCEPT"
