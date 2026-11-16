"""The acceptance audit must not silently acquire an UNMET."""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]


def run_audit():
    result = subprocess.run([sys.executable, str(HERE / "audit_acceptance.py")],
                            cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr[-400:]
    return json.loads((HERE / "evidence" / "acceptance_audit.json").read_text(encoding="utf-8"))


def test_no_criterion_is_silently_unmet():
    payload = run_audit()
    unmet = [r for r in payload["rows"] if r["status"] == "UNMET"]
    assert not unmet, "criteria regressed to UNMET: %s" % [
        (r["issue"], r["criterion"], r["evidence"]) for r in unmet]


def test_every_manual_item_says_why_it_cannot_be_checked():
    payload = run_audit()
    for row in payload["rows"]:
        if row["status"] == "MANUAL":
            assert row["evidence"].strip(), row["criterion"]


def test_the_audit_covers_every_issue_it_claims_to():
    payload = run_audit()
    covered = {row["issue"] for row in payload["rows"]}
    for issue in ("249", "250", "251", "252", "253", "254"):
        assert issue in covered, issue


def test_a_status_that_is_not_a_word_is_caught():
    """The audit found three of its own bugs by refusing a non-status.

    Two checks returned a bool where a status word was expected, and one raised
    because PolicyError has no as_dict. If the runner had stringified whatever it
    got, all three would have printed as something plausible.
    """
    sys.path.insert(0, str(HERE))
    import audit_acceptance as A
    row = A.check("x", "999", lambda: (True, "bool status"))
    assert row["status"] == A.UNMET
    assert "as a status" in row["evidence"]
