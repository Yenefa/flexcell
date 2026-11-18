#!/usr/bin/env python3
"""Step 5 at the LIVE boundary: an applied entry must be recorded with its run id.

Before this, recovery_driver wrote experience_binding.json but never touched the usage
ledger, so "which task used this entry, what changed, what happened" was unanswerable for
the only path that runs a robot.
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "runtime" / "recovery"))
sys.path.insert(0, str(ROOT))
import recovery_driver as rd  # noqa: E402
import review_ledger as chain  # noqa: E402

CHAIN_DIR = ROOT / "setup" / "acceptance" / "evobot_continual_chain_20261118"
ASSETS = CHAIN_DIR / "skill_assets.jsonl"
ENTRIES = CHAIN_DIR / "records_v2.jsonl"


def _result(**kw):
    return "RESULT " + json.dumps(kw)


def _e2_identity(entries_path):
    rows = [json.loads(l) for l in open(entries_path, encoding="utf-8") if l.strip()]
    entry = [r for r in rows if (r.get("version") or {}).get("label") == "E2"][-1]
    return entry["entry_id"], entry["chain_sha256"]


def _reviewed(tmp_path):
    rows = [json.loads(l) for l in open(ENTRIES, encoding="utf-8") if l.strip()]
    eid, sha = _e2_identity(ENTRIES)
    led = tmp_path / "ledger.jsonl"
    chain.append(str(led), {"entry_id": eid, "verdict": "ACCEPT",
                            "reviewed_by": "gate-auditor",
                            "entry_chain_sha256": sha})
    return eid, led


def _failure(tmp_path, poses):
    (tmp_path / "task.out").write_text(
        _result(outcome=1, error_code=61,
                detail="state drift or occupied destination before b-1",
                completed_stage_ids=[]), encoding="utf-8")
    stages = [{"object_name": n, "place_pose": p} for n, p in poses]
    (tmp_path / "plan.json").write_text(json.dumps({
        "stages": stages, "clearance_m": 0.05,
        "position_tolerance_m": 0.02}), encoding="utf-8")


def test_an_applied_live_entry_writes_three_ledger_rows(tmp_path):
    eid, led = _reviewed(tmp_path)
    _failure(tmp_path, [("a", [0.20, 0.0, 0.0175]),
                        ("b", [0.256, 0.0, 0.0175])])
    usage = tmp_path / "usage.jsonl"
    rc = rd.main(["--run", str(tmp_path),
                  "--experience-asset", str(ASSETS),
                  "--experience-entries", str(ENTRIES),
                  "--experience-review-ledger", str(led),
                  "--experience-observation", str(tmp_path / "plan.json"),
                  "--experience-usage-ledger", str(usage),
                  "--experience-entry-id", eid])
    assert rc == 0
    rows = [json.loads(l) for l in open(usage, encoding="utf-8") if l.strip()]
    assert [r["event"] for r in rows] == ["RETRIEVED", "APPLIED", "OUTCOME"]
    assert all(r["run_id"] == str(tmp_path) for r in rows)
    assert all(r["entry_id"] == eid for r in rows)
    assert rows[-1]["outcome"] in ("IMPROVED", "UNCHANGED")


def test_a_default_path_writes_no_false_application(tmp_path):
    """With no reviewed entry, defaults are used: that is NOT an application."""
    _failure(tmp_path, [("a", [0.12, -0.15, 0.0175]),
                        ("b", [0.12, -0.15, 0.0175])])
    usage = tmp_path / "usage.jsonl"
    rd.main(["--run", str(tmp_path), "--experience-usage-ledger", str(usage),
             "--experience-entry-id", "would-be-id"])
    assert not usage.exists()


def test_an_inapplicable_plan_writes_no_application(tmp_path):
    """A plan already meeting the contract gets defaults, so no APPLIED row."""
    eid, led = _reviewed(tmp_path)
    _failure(tmp_path, [("a", [0.20, 0.0, 0.0175]),
                        ("b", [0.29, 0.0, 0.0175])])
    usage = tmp_path / "usage.jsonl"
    rd.main(["--run", str(tmp_path),
             "--experience-asset", str(ASSETS),
             "--experience-entries", str(ENTRIES),
             "--experience-review-ledger", str(led),
             "--experience-observation", str(tmp_path / "plan.json"),
             "--experience-usage-ledger", str(usage),
             "--experience-entry-id", eid])
    assert not usage.exists()
