"""Run one real slot end to end. Smoke test before any batch.

Cost control: this caps the slot at --max-interactions (default 2), not the
protocol's 6, so the first real call cannot run away. The batch runner uses 6.
"""
import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT), str(ROOT / "benchmark" / "repair_eval" / "contracts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import budget as B                                      # noqa: E402
import run_record as REC                                # noqa: E402
import task_contract                                    # noqa: E402
import acceptance                                       # noqa: E402
from agent import RepairAgent                           # noqa: E402
from benchmark.repair_eval import visibility as vis      # noqa: E402
from llm_transport import GatedTransport                # noqa: E402
from dry_run_matrix import DEFECTS, build_candidate, contract_for  # noqa: E402

FAMILY = "F1_OBJECT_REGISTRATION"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--condition", default="B_REAL_FEEDBACK")
    ap.add_argument("--max-interactions", type=int, default=2)
    args = ap.parse_args(argv)

    policy = vis.load_policy(ROOT / "benchmark" / "repair_eval" / "visibility_policy.json")
    contract = task_contract.TaskContract.from_mapping(contract_for(FAMILY))

    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        candidate = build_candidate(tmp / "candidate", FAMILY)
        verdict_dir = tmp / "verdict"; verdict_dir.mkdir()
        hidden = tmp / "hidden"; hidden.mkdir()
        donor = tmp / "donor"; (donor / "telemetry").mkdir(parents=True)
        (donor / "telemetry" / "execution.log").write_text("DONOR: registry returned []" + chr(10))
        (donor / "verdict.json").write_text('{"passed": false}')

        boundary = vis.RunBoundary(policy, tmp, candidate, verdict_dir, hidden,
                                   condition=args.condition, mismatch_dir=donor)
        boundary.assert_fresh_run()
        (candidate / "telemetry").mkdir(exist_ok=True)
        (candidate / "telemetry" / "execution.log").write_text(
            "REAL FAILURE: registered_objects(['a','b']) returned []" + chr(10) + "stage=s2" + chr(10))

        transport = GatedTransport()
        ledger = B.Ledger(transport, max_interactions=args.max_interactions)

        task = ("The skill module skill/registry.py must register every object it is "
                "given. Right now registered_objects(scene) returns an empty list, so the "
                "robot cannot see the objects it is asked to move. Fix skill/registry.py.")
        agent = RepairAgent(ledger, boundary, task, contract.editable_fields)
        result = agent.run()

        regression = subprocess.run([sys.executable, "-m", "pytest", "-q", "skill"],
                                    cwd=candidate, capture_output=True, text=True)
        state = {
            "candidate_schema": acceptance.CANDIDATE_SCHEMA,
            "task_id": contract.task_id,
            "run_id": "RUN-9001",
            "exit_code": regression.returncode,
            "claim_success": result["claimed_success"],
            "objects": {"target": [0.22, 0.0, 0.0175]},
            "regressions": [{"name": "skill", "status":
                             "PASS" if regression.returncode == 0 else "FAIL"}],
            "protected_hashes": {
                "task.md": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
            "changed_files": result["writes"],
            "evidence": [{"name": "termination_log", "path": "evidence/termination.log",
                          "sha256": "a" * 64}],
        }
        verdict = acceptance.evaluate(contract, state).to_dict()

        record = REC.build_record(
            slot_id="F1-B-smoke", condition=args.condition,
            condition_access=policy.conditions[args.condition], policy=policy,
            account=result["account"], terminal_status=result["terminal_state"],
            claim_success=result["claimed_success"],
            feedback_text="REAL FAILURE: registered_objects returned []",
            gate_target="PASS" if verdict["status"] == "ACCEPT" else "FAIL",
            gate_contract="PASS" if verdict["status"] == "ACCEPT" else "FAIL",
            gate_contract_codes=[r["code"] for r in verdict["reasons"]],
            gate_independent="NOT_RUN",
            edited_paths=result["writes"],
            first_edit_after_execution=True,
            evidence_path="smoke",
        )
        record["model"] = transport.metadata()["requested_model"]
        record["key_fingerprint"] = transport.metadata()["key_fingerprint"]

        print(json.dumps({
            "terminal_state": result["terminal_state"],
            "claimed_success": result["claimed_success"],
            "interactions": record["interactions_used"],
            "tokens_total": record["tokens_total"],
            "tokens_source": record["tokens_source"],
            "writes": result["writes"],
            "contract": verdict["status"],
            "codes": [r["code"] for r in verdict["reasons"]],
            "regression_exit": regression.returncode,
            "model": record["model"],
            "key_fingerprint": record["key_fingerprint"],
        }, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
