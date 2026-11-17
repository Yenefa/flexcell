"""The acceptance audit must cover every criterion and never acquire an UNMET."""
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]

# the six issues carry 46 checkboxes between them; this number is the whole point
EXPECTED_CRITERIA = 46


def run_audit(tmp_path=None):
    """The audit writes its JSON only when asked, so runs do not dirty the tree."""
    import os
    import tempfile
    target = Path(tmp_path or tempfile.mkdtemp()) / "acceptance_audit.json"
    env = dict(os.environ, AUDIT_OUT=str(target))
    result = subprocess.run([sys.executable, str(HERE / "audit_acceptance.py")],
                            cwd=ROOT, capture_output=True, text=True, env=env)
    assert result.returncode == 0, result.stderr[-400:]
    return json.loads(target.read_text(encoding="utf-8"))


def test_the_audit_covers_every_criterion_the_issues_list():
    """The first version audited 24 rows and called itself an acceptance audit.

    The issues carry 46 checkboxes, so 22 criteria had no row at all and the
    audit still looked complete. That is the failure this case exists to stop.
    """
    payload = run_audit()
    assert payload["criteria"] == EXPECTED_CRITERIA
    assert len(payload["rows"]) == EXPECTED_CRITERIA


def test_no_criterion_is_silently_unmet():
    payload = run_audit()
    unmet = [r for r in payload["rows"] if r["status"] == "UNMET"]
    assert not unmet, [(r["id"], r["evidence"]) for r in unmet]


def test_every_row_has_a_unique_criterion_id():
    payload = run_audit()
    ids = [r["id"] for r in payload["rows"]]
    assert len(ids) == len(set(ids))
    # the ids must name the issue they came from
    for row in payload["rows"]:
        assert row["id"].split(".")[0] == str(row["issue"]), row["id"]


def test_every_manual_row_says_why_it_cannot_be_checked():
    payload = run_audit()
    for row in payload["rows"]:
        if row["status"] == "MANUAL":
            assert row["evidence"].strip(), row["id"]
            assert len(row["evidence"]) > 8, row["id"]


DOC_LEVEL_CHECK_IDS = ("251.1", "251.6", "251.8", "254.2", "254.5", "254.7")


def test_document_presence_is_graded_partial_not_met():
    """Finding a word in a document is not evidence the thing works.

    Six checks can only look for the topic in prose. They must not be graded MET,
    or the ledger claims verification where there is only a sentence.
    """
    sys.path.insert(0, str(HERE))
    import audit_acceptance as A
    rows = {r["id"]: r for r in
            (A.run_one(cid, issue, text) for cid, issue, text in A.CRITERIA)}
    for cid in DOC_LEVEL_CHECK_IDS:
        row = rows[cid]
        assert row["status"] != "MET", (
            "%s is documentation-only but graded MET: %s" % (cid, row["evidence"]))


def test_the_documented_fingerprint_is_compared_with_the_live_one(tmp_path):
    """A doc can print a fingerprint that no longer matches the policy."""
    sys.path.insert(0, str(HERE))
    import audit_acceptance as A
    status, evidence = A.k249_7()
    assert status == A.MET
    assert "matches the live" in evidence


def test_partial_is_allowed_and_unmet_is_not():
    payload = run_audit()
    statuses = {r["status"] for r in payload["rows"]}
    assert statuses <= {"MET", "PARTIAL", "MANUAL", "UNMET"}
    assert "UNMET" not in statuses


def test_a_criterion_with_no_check_and_no_reason_is_unmet():
    """Missing coverage has to fail loudly rather than vanish."""
    sys.path.insert(0, str(HERE))
    import audit_acceptance as A
    row = A.run_one("999.9", 999, "a criterion nobody covered")
    assert row["status"] == A.UNMET
    assert "no check and no stated reason" in row["evidence"]


def test_a_status_that_is_not_a_word_is_caught():
    sys.path.insert(0, str(HERE))
    import audit_acceptance as A
    A.COVERED["999.8"] = lambda: (True, "bool status")
    try:
        row = A.run_one("999.8", 999, "x")
    finally:
        A.COVERED.pop("999.8", None)
    assert row["status"] == A.UNMET
    assert "as a status" in row["evidence"]


def test_running_the_audit_does_not_write_into_the_repository():
    """It once did, and a dirty evidence file refused a merge.

    The audit is a check. Its output is a byproduct, so it goes to a temp path
    unless the caller asks for a file.
    """
    import os
    evidence = HERE / "evidence" / "acceptance_audit.json"
    if evidence.exists():
        evidence.unlink()
    env = {k: v for k, v in os.environ.items() if k != "AUDIT_OUT"}
    result = subprocess.run([sys.executable, str(HERE / "audit_acceptance.py")],
                            cwd=ROOT, capture_output=True, text=True, env=env)
    assert result.returncode == 0
    assert not evidence.exists(), "the audit wrote into the repository again"
