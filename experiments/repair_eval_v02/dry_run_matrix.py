
"""Drive the 24-slot v0.2 matrix through the real adapter, with a scripted agent.

WHY THIS EXISTS
    The matrix cannot be run with a model on this machine: the credential gate
    path is absent, the env file is absent and neither registry hive carries the
    key. Rather than claim a matrix that never ran, this drives the *same* 24
    slots through the *same* adapter with a ScriptedAgent - the mechanism the
    repository already uses to validate measurement without spending money.

WHAT IT PROVES, AND WHAT IT DOES NOT
    Proves: the slot table, the condition routing, the freshness gate, the
    visibility boundary, the contract evaluation and the ledger all compose, and
    a full matrix produces a complete, auditable record with zero slots missing.
    Does not prove: anything about model capability. Every record is marked
    DRY_RUN and must never enter a denominator.

    The reason this is worth doing before the credential exists is the one the
    repository already learned twice: a pipeline that has never been executed
    end to end is not a pipeline, it is a plan. If the first end-to-end run
    happens with the real model, every bug in the harness silently becomes a
    capability result.
"""
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "benchmark" / "repair_eval" / "contracts"))

from benchmark.repair_eval import visibility as vis      # noqa: E402
import acceptance                                        # noqa: E402
import task_contract                                     # noqa: E402

CONDITIONS = ("A_STATIC", "B_REAL_FEEDBACK", "C_MISMATCHED_FEEDBACK", "D_GUIDED")
FAMILIES = ("F1_OBJECT_REGISTRATION", "F2_GOAL_MAPPING")
REPS = (1, 2, 3)

DEFECTS = {
    "F1_OBJECT_REGISTRATION": {
        "broken": "def registered_objects(scene):\n    return []\n",
        "fixed": "def registered_objects(scene):\n    return sorted(scene)\n",
        "test": "from skill.registry import registered_objects\n\n\ndef test_registry():\n    assert registered_objects(['a', 'b']) == ['a', 'b']\n",
    },
    "F2_GOAL_MAPPING": {
        "broken": "def to_world(goal, frame):\n    return goal\n",
        "fixed": "def to_world(goal, frame):\n    return [goal[0] + frame[0], goal[1] + frame[1], goal[2]]\n",
        "test": "from skill.mapping import to_world\n\n\ndef test_mapping():\n    assert to_world([0, 0, 0], [1, 2, 0]) == [1, 2, 0]\n",
    },
}


def contract_for(family):
    """A frozen contract per family. The goal is the ruler, not the candidate's."""
    return {
        "schema": "flexcell.repair_eval.task_contract/1",
        "version": 1,
        "task_id": "REPAIR-" + family,
        "immutable": {
            "user_goal": "repair the %s defect without changing the task" % family,
            "objects": [{"name": "target", "position": [0.22, 0.0, 0.0175], "tolerance": 0.02}],
            "zones": [{"name": "zone", "position": [0.14, 0.0, 0.0175], "radius": 0.06}],
            "thresholds": {"max_position_error_m": 0.02, "min_regressions": 1},
        },
        "editable_fields": ["skill/"],
        "protected_paths": [{"path": "task.md", "sha256": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"}],
        "evidence_required": ["termination_log"],
        "run_id_pattern": "^RUN-[0-9]{4}$",
    }


def build_candidate(root, family):
    (root / "skill").mkdir(parents=True, exist_ok=True)
    (root / "task.md").write_text("")
    (root / "gate").mkdir(exist_ok=True)
    (root / "gate" / "acceptance.py").write_text("print('gate')\n")
    name = "registry.py" if family.startswith("F1") else "mapping.py"
    (root / "skill" / name).write_text(DEFECTS[family]["broken"])
    (root / "skill" / "test_fix.py").write_text(DEFECTS[family]["test"])
    return root


def run_slot(family, condition, rep, workdir, policy, mismatched_dir):
    """One slot. The agent's information is whatever the condition allows."""
    slot_id = "%s-%s-r%d" % (family.split("_")[0], condition[0], rep)
    run_id = "RUN-%04d" % (rep * 10 + CONDITIONS.index(condition))
    candidate = build_candidate(workdir / "candidate", family)
    verdict_dir = workdir / "verdict"; verdict_dir.mkdir()
    hidden = workdir / "hidden"; hidden.mkdir()

    record = dict(slot_id=slot_id, family=family, condition=condition, repetition=rep,
                  run_id=run_id, status="NOT_RUN", qualification="DRY_RUN")

    # 1. freshness first: a new run may not inherit a previous run's artifacts
    try:
        boundary = vis.RunBoundary(policy, workdir, candidate, verdict_dir, hidden,
                                   condition=condition, mismatch_dir=mismatched_dir)
        boundary.assert_fresh_run()
    except vis.BoundaryError as exc:
        record.update(status="INVALID", reason=(exc.as_dict() or {}).get("reason"))
        return record

    facade = vis.ToolFacade(boundary)
    desc = boundary.describe()
    record["policy_id"] = desc["policy_id"]
    record["policy_fingerprint"] = desc["policy_fingerprint"]

    # 2. what this condition may see
    seen = {}
    for label, rel, cat in (("task", "task.md", "static_input"),
                            ("gate", "gate/acceptance.py", "static_input"),
                            ("source", "skill/" + ("registry.py" if family.startswith("F1") else "mapping.py"),
                             "candidate_source")):
        try:
            facade.read_file(rel)
            seen[label] = "visible"
        except vis.BoundaryError as exc:
            seen[label] = (exc.as_dict() or {}).get("reason")
    record["visibility"] = seen

    try:
        feedback = boundary.read_feedback()
        record["feedback"] = "present" if feedback else "empty"
    except vis.BoundaryError as exc:
        record["feedback"] = (exc.as_dict() or {}).get("reason")

    # 3. the scripted agent applies the known fix (this is the fixture, not a model)
    name = "registry.py" if family.startswith("F1") else "mapping.py"
    facade.write_file("skill/" + name, DEFECTS[family]["fixed"])

    # 4. execute the regression the contract requires, in the candidate itself
    test = subprocess.run([sys.executable, "-m", "pytest", "-q", "skill/test_fix.py"],
                          cwd=candidate, capture_output=True, text=True)
    record["regression_exit"] = test.returncode

    # 5. independent acceptance against the frozen contract
    contract = task_contract.TaskContract.from_mapping(contract_for(family))
    state = {
        "candidate_schema": acceptance.CANDIDATE_SCHEMA,
        "task_id": contract.task_id,
        "run_id": run_id,
        "exit_code": test.returncode,
        "claim_success": True,
        "objects": {"target": [0.22, 0.0, 0.0175]},
        "regressions": [{"name": "skill_test", "status": "PASS" if test.returncode == 0 else "FAIL"}],
        "protected_hashes": {"task.md": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
        "changed_files": ["skill/" + name],
        "evidence": [{"name": "termination_log", "path": "evidence/termination.log", "sha256": "a" * 64}],
    }
    verdict = acceptance.evaluate(contract, state).to_dict()
    record["verdict"] = verdict["status"]
    record["codes"] = [r["code"] for r in verdict["reasons"]]
    record["contract_sha256"] = verdict["contract_sha256"]
    record["status"] = "DRY_RUN_COMPLETE"
    return record


def main():
    policy_path = ROOT / "benchmark" / "repair_eval" / "visibility_policy.json"
    policy = vis.load_policy(policy_path)
    rows = []
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        donor = tmp / "donor"; (donor / "telemetry").mkdir(parents=True)
        (donor / "telemetry" / "execution.log").write_text("donor feedback\n")
        (donor / "verdict.json").write_text('{"passed": true}\n')
        for family in FAMILIES:
            for condition in CONDITIONS:
                for rep in REPEATS:
                    workdir = tmp / ("%s-%s-r%d" % (family, condition, rep))
                    workdir.mkdir(parents=True)
                    rows.append(run_slot(family, condition, rep, workdir, policy, donor))

    summary = dict(
        slots=len(rows),
        expected=len(FAMILIES) * len(CONDITIONS) * len(REPEATS),
        by_status={},
        by_condition={},
        visibility_consistent=all(
            row.get("visibility", {}).get("gate") == "sealed_material" for row in rows),
        qualification="DRY_RUN_SCRIPTED_AGENT_NOT_A_MODEL_RESULT",
    )
    for row in rows:
        summary["by_status"][row["status"]] = summary["by_status"].get(row["status"], 0) + 1
        summary["by_condition"].setdefault(row["condition"], []).append(row["verdict"])
    print(json.dumps(dict(summary=summary, rows=rows), indent=2, ensure_ascii=False))
    return 0


REPEATS = REPS

if __name__ == "__main__":
    raise SystemExit(main())
