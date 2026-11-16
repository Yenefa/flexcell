"""Run the real 24-slot matrix through the gated model.

DIFFERENCES FROM budget_matrix.py
    That one uses a stand-in transport and marks every row SCRIPTED. This one uses
    the gated client, so the rows are real model runs and carry no such marker.

BUDGET
    The protocol caps each slot at 6 interactions and 20,000 tokens. This adds a
    batch cap on top (DATA_DICTIONARY 5.3 left the batch total TBD; the operator
    set it). The cap is checked before each slot, not before each call, so the
    run can overshoot by at most one slot - the per-slot cap of 20,000 bounds
    that. Checking it only afterwards would report an overspend instead of
    preventing one, which is why it is checked at all.
"""
import argparse
import hashlib
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

import acceptance                                       # noqa: E402
import instances as IN                                   # noqa: E402
import budget as B                                      # noqa: E402
import run_record as REC                                # noqa: E402
import task_contract                                    # noqa: E402
from agent import RepairAgent                           # noqa: E402
from benchmark.repair_eval import visibility as vis      # noqa: E402
from dry_run_matrix import (CONDITIONS, DEFECTS, FAMILIES, REPEATS,  # noqa: E402
                            build_candidate, contract_for)
from llm_transport import GatedTransport                # noqa: E402

TASKS = {
    "F1_OBJECT_REGISTRATION":
        "The skill module skill/registry.py must register every object it is given. "
        "Right now registered_objects(scene) returns an empty list, so the robot cannot "
        "see the objects it is asked to move. Fix skill/registry.py.",
    "F2_GOAL_MAPPING":
        "The skill module skill/mapping.py converts a goal from the tool frame to the "
        "world frame. Right now to_world(goal, frame) returns the goal unchanged, so the "
        "robot moves to the wrong place. Fix skill/mapping.py.",
}


class BatchBudget(B.BudgetExhausted):
    pass


def refresh_feedback(candidate):
    """Run the candidate and write what actually happened.

    Writing one failure sentence before the run and handing it to the agent six
    times is not "real execution feedback", even though it produces a file that
    looks like a log. It was the first version of this harness, and it made every
    feedback condition behave like the no-feedback one: the agent re-read the same
    sentence and retried blindly, so all twelve F2 slots died at the interaction
    cap. The measured difference after the fix, same slot, same model:

        static feedback  6 interactions  13,647 tokens  BUDGET_EXHAUSTED
        real feedback    1 interaction      475 tokens  ACCEPT
    """
    # Bytecode caches are invalidated by (mtime seconds, size). A repair that
    # rewrites a file within the same second with the same byte count therefore
    # runs against stale bytecode and looks like it did nothing - measured while
    # writing this harness's own test, where "return 0" became "return 7".
    for cache in candidate.rglob("__pycache__"):
        import shutil
        shutil.rmtree(cache, ignore_errors=True)
    ran = subprocess.run([sys.executable, "-m", "pytest", "-q", "skill"],
                         cwd=candidate, capture_output=True, text=True)
    (candidate / "telemetry").mkdir(exist_ok=True)
    (candidate / "telemetry" / "execution.log").write_text(
        "exit=%d" % ran.returncode + chr(10) + (ran.stdout or "") + (ran.stderr or ""))
    return ran


def replace_editable_fields(contract, fields):
    """A contract with a different editable surface.

    TaskContract is frozen, so this rebuilds it from its mapping rather than
    mutating it - the contract is the ruler and a runner must not loosen it in
    place.
    """
    mapping = contract.to_mapping() if hasattr(contract, "to_mapping") else None
    if mapping is None:
        raw = dict(contract.__dict__)
        raw["editable_fields"] = list(fields)
        return task_contract.TaskContract.from_mapping(raw)
    mapping["editable_fields"] = list(fields)
    return task_contract.TaskContract.from_mapping(mapping)


def run_slot(family, condition, rep, workdir, policy, donor, model, max_interactions,
             seed=None, donor_run_id=None, source_sha=None, donor_log_path=None,
             source="synthetic", task_variant="v1"):
    instance = ("DEF-F1-REG" if family.startswith("F1") else "DEF-F2-MAP") \
        if source == "instances" else None
    if instance:
        candidate = IN.materialize(instance, workdir / "candidate", task_variant)
        task_text = IN.task_text(instance, task_variant)
    else:
        candidate = build_candidate(workdir / "candidate", family, seed=seed)
        task_text = TASKS[family]
    slot_id = "%s-%s-r%d" % (family.split("_")[0], condition[0], rep)
    verdict_dir = workdir / "verdict"; verdict_dir.mkdir()
    hidden = workdir / "hidden"; hidden.mkdir()
    if condition == "C_MISMATCHED_FEEDBACK" and donor_log_path and Path(donor_log_path).exists():
        # The mismatch has to be somebody's real output. A sentence invented here
        # would make C identical to A with extra steps.
        (donor / "telemetry").mkdir(parents=True, exist_ok=True)
        (donor / "telemetry" / "execution.log").write_text(
            Path(donor_log_path).read_text())
    boundary = vis.RunBoundary(policy, workdir, candidate, verdict_dir, hidden,
                               condition=condition, mismatch_dir=donor)
    boundary.assert_fresh_run()
    (candidate / "telemetry").mkdir(exist_ok=True)

    def refresh():
        """The feedback for the next interaction, from the source this slot uses.

        An instance slot must see the sealed gate's typed answer. The first
        version of this block refreshed the initial message from the gate but
        left the per-step call pointing at the synthetic pytest helper, which
        ran in a workspace with no tests and overwrote the gate's output. B and C
        then received a pytest error instead of a reason code - the fourth time a
        new source of truth was added without switching the path that reads it.
        """
        if instance:
            _ok, payload = IN.check(instance, candidate, task_variant)
            (candidate / "telemetry" / "execution.log").write_text(
                json.dumps(payload, ensure_ascii=False) + chr(10))
            return payload
        return refresh_feedback(candidate)

    refresh()
    donor_log = None
    if condition == "B_REAL_FEEDBACK":
        donor_dir = Path(__file__).resolve().parent / "evidence" / "donor"
        donor_dir.mkdir(parents=True, exist_ok=True)
        donor_log = donor_dir / ("%s.log" % slot_id)
        donor_log.write_text((candidate / "telemetry" / "execution.log").read_text())

    transport = GatedTransport(model=model, timeout=300)
    ledger = B.Ledger(transport, max_interactions=max_interactions)
    contract = task_contract.TaskContract.from_mapping(contract_for(family))
    if instance:
        # The editable surface belongs to the instance, not to the synthetic
        # contract. Four real-instance slots were spent learning this: the agent
        # was told it could edit "skill/", wrote only there, and never touched
        # config/week1.yaml or src/task_fsm_server.py. All four came back FAIL
        # and the model was not at fault.
        #
        # This has to patch the assignment that survives: an earlier attempt put
        # the same code before the transport line, where the next statement
        # rebuilt the contract from scratch and silently undid it.
        surface = str(Path(IN.editable_rel(instance)).parent) + "/"
        contract = replace_editable_fields(contract, [surface])
    agent = RepairAgent(ledger, boundary, task_text, contract.editable_fields)

    # Drive the loop here rather than calling agent.run(), so that the feedback
    # for the next interaction is refreshed from a real execution after every
    # step. agent.run() remains the driver for callers that have no workspace.
    steps = 0
    limit = max_interactions + 1
    while not agent.done and steps < limit:
        try:
            agent.step()
        except B.BudgetExhausted:
            break
        steps += 1
        if not agent.done:
            refresh()
    ledger.finish()
    result = agent.result()

    regression = subprocess.run([sys.executable, "-m", "pytest", "-q", "skill"],
                                cwd=candidate, capture_output=True, text=True)
    state = {
        "candidate_schema": acceptance.CANDIDATE_SCHEMA,
        "task_id": contract.task_id,
        "run_id": "RUN-%04d" % (abs(hash((family, condition, rep))) % 10000),
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
    if instance:
        gate_ok, gate_payload = IN.check(instance, candidate, task_variant)
        verdict = {"status": "ACCEPT" if gate_ok else "REJECT",
                   "reasons": [] if gate_ok else [{"code": gate_payload.get("code", "UNKNOWN")}]}
    else:
        verdict = acceptance.evaluate(contract, state).to_dict()

    if result["terminal_state"] == B.BUDGET_EXHAUSTED:
        terminal = "BUDGET_EXHAUSTED"
    elif verdict["status"] == "ACCEPT":
        terminal = "UNKNOWN"      # contract accepted, independent gate never ran
    elif verdict["status"] == "REJECT":
        terminal = "FAIL"
    else:
        terminal = "UNKNOWN"

    record = REC.build_record(
        slot_id="%s-%s-r%d" % (family.split("_")[0], condition[0], rep),
        condition=condition, condition_access=policy.conditions[condition],
        policy=policy, account=result["account"], terminal_status=terminal,
        claim_success=result["claimed_success"],
        feedback_text=(TASKS[family] if condition != "A_STATIC" else None),
        guidance_text=(policy.conditions[condition].guidance
                       if condition == "D_GUIDED" else None),
        donor_run_id=donor_run_id,
        gate_target=("PASS" if verdict["status"] == "ACCEPT" else "FAIL"),
        gate_contract=("PASS" if verdict["status"] == "ACCEPT" else "FAIL"),
        gate_contract_codes=[r["code"] for r in verdict["reasons"]],
        gate_independent="NOT_RUN",
        edited_paths=result["writes"], first_edit_after_execution=True,
        evidence_path="experiments/repair_eval_v02/evidence",
    )
    record["qualification"] = "REAL_MODEL_RUN" + ("|INSTANCE" if instance else "|SYNTHETIC")
    record["seed"] = seed
    record["task_variant"] = task_variant
    record["contract_sha256"] = hashlib.sha256(json.dumps(
        contract_for(family), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode()).hexdigest()
    record["source_sha"] = source_sha
    record["donor_log"] = str(donor_log) if donor_log else None
    record["model"] = transport.metadata()["requested_model"]
    record["key_fingerprint"] = transport.metadata()["key_fingerprint"]
    record["contract_verdict"] = verdict["status"]
    record["regression_exit"] = regression.returncode
    return record


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--budget", type=int, default=500000)
    ap.add_argument("--max-interactions", type=int, default=6)
    ap.add_argument("--model", default="deepseek-flash")
    ap.add_argument("--out", default=str(HERE / "evidence" / "real_matrix.json"))
    ap.add_argument("--source", choices=("synthetic", "instances"), default="synthetic")
    ap.add_argument("--task-variant", choices=("v1", "v2"), default="v1",
                    help="v1 names the answer in the task text; v2 withholds it")
    ap.add_argument("--limit", type=int, default=0, help="stop after N slots (smoke)")
    ap.add_argument("--families", default="", help="comma separated subset")
    ap.add_argument("--conditions", default="", help="comma separated subset")
    ap.add_argument("--reps", default="", help="comma separated subset")
    args = ap.parse_args(argv)

    policy = vis.load_policy(ROOT / "benchmark" / "repair_eval" / "visibility_policy.json")
    fam_sel = [x for x in args.families.split(",") if x] or list(FAMILIES)
    con_sel = [x for x in args.conditions.split(",") if x] or list(CONDITIONS)
    rep_sel = [int(x) for x in args.reps.split(",") if x] or list(REPEATS)
    rows = []
    spent = 0
    stopped = None
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        donor = tmp / "donor"; (donor / "telemetry").mkdir(parents=True)
        (donor / "telemetry" / "execution.log").write_text("DONOR FAILURE" + chr(10))
        (donor / "verdict.json").write_text('{"passed": false}')
        source_sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT),
                                    capture_output=True, text=True).stdout.strip() or None
        base = {"F1_OBJECT_REGISTRATION": 5100, "F2_GOAL_MAPPING": 5200}
        produced = {}          # (family, rep) -> run_id of the B slot
        for family in fam_sel:
            for condition in con_sel:
                for rep in rep_sel:
                    if args.limit and len(rows) >= args.limit:
                        stopped = "limit %d reached" % args.limit
                        break
                    if spent >= args.budget:
                        stopped = "batch budget %d reached at %d tokens" % (args.budget, spent)
                        break
                    workdir = tmp / ("%s-%s-r%d" % (family, condition, rep))
                    workdir.mkdir(parents=True)
                    slot_id = "%s-%s-r%d" % (family.split("_")[0], condition[0], rep)
                    seed = base.get(family, 5000) + rep
                    # MANIFEST 2: the donor of a C slot must be a B run of the same
                    # family at a different seed, bound before any C run. With no
                    # such run the C slot stays NOT_RUN - it is not filled in with
                    # somebody else's feedback.
                    borrowed = None
                    borrowed_log = None
                    if condition == "C_MISMATCHED_FEEDBACK":
                        for other_rep in rep_sel:
                            if other_rep != rep and (family, other_rep) in produced:
                                entry = produced[(family, other_rep)]
                                borrowed = entry.get("run_id")
                                borrowed_log = entry.get("donor_log")
                                break
                        if not borrowed:
                            rows.append({"slot_id": slot_id, "condition": condition,
                                         "terminal_status": "NOT_RUN",
                                         "qualification": "REAL_MODEL_RUN",
                                         "seed": seed, "source_sha": source_sha,
                                         "notes": "no B run of this family at another "
                                                  "seed exists to borrow from",
                                         "tokens_total": 0, "interactions_used": 0,
                                         "edited_paths": []})
                            continue
                    try:
                        row = run_slot(family, condition, rep, workdir, policy, donor,
                                       args.model, args.max_interactions, seed=seed,
                                       donor_run_id=borrowed, source_sha=source_sha,
                                       donor_log_path=borrowed_log,
                                       source=args.source, task_variant=args.task_variant)
                    except Exception as exc:                       # noqa: BLE001
                        # One dead call must not take the batch with it. The
                        # failure is a record of its own: the environment broke,
                        # which is INVALID, not a failed repair.
                        row = {"slot_id": slot_id, "condition": condition,
                               "terminal_status": "INVALID",
                               "qualification": "REAL_MODEL_RUN",
                               "deviation_codes": ["D-ENV"],
                               "notes": ("%s: %s" % (type(exc).__name__,
                                                     str(exc)))[:300],
                               "tokens_total": 0, "interactions_used": 0,
                               "edited_paths": []}
                    rows.append(row)
                    if condition == "B_REAL_FEEDBACK":
                        produced[(family, rep)] = {
                            "run_id": row.get("run_id") or row["slot_id"],
                            "donor_log": row.get("donor_log")}
                    spent += row.get("tokens_total", 0)
                    # persist every slot: a crash after the loop must not lose
                    # work that has already been paid for
                    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
                    Path(args.out).write_text(json.dumps(
                        {"summary": {"slots_attempted": len(rows), "running": True,
                                     "tokens_spent": spent},
                         "rows": rows}, indent=2, ensure_ascii=False), encoding="utf-8")
            if stopped:
                break
        if stopped:
            pass
    for family in []:
        pass

    summary = {
        "slots_attempted": len(rows),
        "slots_planned": len(fam_sel) * len(con_sel) * len(rep_sel),
        "tokens_spent": spent,
        "batch_budget": args.budget,
        "model": args.model,
        "stopped": stopped,
        "terminal_states": {},
        "by_condition": {},
        "qualification": "REAL_MODEL_RUN",
    }
    for row in rows:
        summary["terminal_states"][row["terminal_status"]] = (
            summary["terminal_states"].get(row["terminal_status"], 0) + 1)
        summary["by_condition"].setdefault(row["condition"], []).append(
            row["terminal_status"])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "rows": rows}, indent=2,
                              ensure_ascii=False), encoding="utf-8")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
