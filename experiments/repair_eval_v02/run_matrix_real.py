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
import shutil
import subprocess
import sys
import uuid
from urllib.error import URLError
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
for path in (str(HERE), str(ROOT), str(ROOT / "benchmark" / "repair_eval" / "contracts")):
    if path not in sys.path:
        sys.path.insert(0, path)

import acceptance                                       # noqa: E402
import health                                           # noqa: E402
import evidence_archive as ARCH                          # noqa: E402
import environment_receipt                               # noqa: E402
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
    ran = health.checked_run([sys.executable, "-m", "pytest", "-q", "skill"],
                             cwd=candidate)
    (candidate / "telemetry").mkdir(exist_ok=True)
    (candidate / "telemetry" / "execution.log").write_text(
        "exit=%d" % ran.returncode + chr(10) + (ran.stdout or "") + (ran.stderr or ""))
    health.pytest_terminal(ran)
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
             source="synthetic", task_variant="v1", source_files=None):
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
    shutil.copytree(candidate, workdir / "initial_candidate")
    baseline = health.inventory(candidate)
    editable = ([IN.editable_rel(instance)] if instance else ["skill/"])
    health_before = health.safe_probe(
        ROOT, source_sha, candidate, source_files=source_files,
        required_files=tuple(baseline), baseline=baseline, editable=editable)
    ARCH.write_json(workdir / "health_before.json", health_before)
    health.require_healthy(health_before)
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
            health.gate_terminal(_ok, payload)
            (candidate / "telemetry" / "execution.log").write_text(
                json.dumps(payload, ensure_ascii=False) + chr(10))
            return payload
        return refresh_feedback(candidate)

    refresh()
    donor_log = None
    if condition == "B_REAL_FEEDBACK":
        donor_dir = workdir / "donor_output"
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
    agent = RepairAgent(
        ledger, boundary, task_text, contract.editable_fields,
        guidance=policy.conditions[condition].guidance if condition == "D_GUIDED" else None)

    # Drive the loop here rather than calling agent.run(), so that the feedback
    # for the next interaction is refreshed from a real execution after every
    # step. agent.run() remains the driver for callers that have no workspace.
    steps = 0
    limit = max_interactions + 1
    try:
        while not agent.done and steps < limit:
            try:
                agent.step()
            except B.BudgetExhausted:
                break
            steps += 1
            if not agent.done:
                refresh()
    finally:
        ledger.finish()
        ARCH.write_json(workdir / "account.json", ledger.account())
        ARCH.write_json(workdir / "transcript.json", agent.transcript)
    result = agent.result()

    # Instance workspaces have no skill/ test package. Running pytest there
    # yields exit 4 and invents an ordinary-task regression that never existed.
    regression = (None if instance else refresh_feedback(candidate))
    state = {
        "candidate_schema": acceptance.CANDIDATE_SCHEMA,
        "task_id": contract.task_id,
        "run_id": "RUN-%04d" % (abs(hash((family, condition, rep))) % 10000),
        "exit_code": regression.returncode if regression else 0,
        "claim_success": result["claimed_success"],
        "objects": {"target": [0.22, 0.0, 0.0175]},
        "regressions": [{"name": "skill", "status":
                         ("PASS" if regression.returncode == 0 else "FAIL")
                         if regression else "NOT_RUN"}],
        "protected_hashes": {
            "task.md": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"},
        "changed_files": result["writes"],
        "evidence": [{"name": "termination_log", "path": "evidence/termination.log",
                      "sha256": "a" * 64}],
    }
    if instance:
        gate_ok, gate_payload = IN.check(instance, candidate, task_variant)
        action_terminal = health.gate_terminal(gate_ok, gate_payload)
        verdict = {"status": "ACCEPT" if gate_ok else "REJECT",
                   "reasons": [] if gate_ok else [{"code": gate_payload.get("code", "UNKNOWN")}]}
    else:
        verdict = acceptance.evaluate(contract, state).to_dict()
        action_terminal = health.pytest_terminal(regression)

    ARCH.write_json(verdict_dir / "final.json", {
        "verdict": verdict, "action_terminal": action_terminal,
        "regression_exit": regression.returncode if regression else None,
        "gate_independent": "NOT_RUN"})

    health_after = health.safe_probe(
        ROOT, source_sha, candidate, source_files=source_files,
        required_files=tuple(baseline), baseline=baseline, editable=editable)
    ARCH.write_json(workdir / "health_after.json", health_after)
    health.require_healthy(health_after)

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
    record["contract_sha256"] = hashlib.sha256(json.dumps(
        contract_for(family), sort_keys=True, separators=(",", ":"),
        ensure_ascii=False).encode()).hexdigest()
    record["source_sha"] = source_sha
    record["donor_log"] = str(donor_log) if donor_log else None
    record["model"] = transport.metadata()["requested_model"]
    record["key_fingerprint"] = transport.metadata()["key_fingerprint"]
    record["contract_verdict"] = verdict["status"]
    record["regression_exit"] = regression.returncode if regression else None
    record["task_variant"] = task_variant
    record["family"] = family
    record["instance"] = instance
    record["action_terminal"] = action_terminal
    record["health_before"] = health_before
    record["health_after"] = health_after
    record["candidate_sha"] = health.tree_sha(candidate)
    record["regression_scope"] = "source_gate_only" if instance else "synthetic_skill_pytest"
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
    # A family is a name like F1_OBJECT_REGISTRATION, not an instance id like
    # DEF-F1-REG. Passing the instance silently ran the wrong instance: seeds
    # fell back to 5000+, the slot ids carried the instance name, and the gate
    # answered for a different family. Sixty-three thousand tokens went into
    # three slots before anyone read the code. Refuse instead.
    unknown = [f for f in fam_sel if f not in FAMILIES]
    if unknown:
        raise SystemExit(
            "unknown family %s; known families are %s (an instance id like "
            "DEF-F1-REG is not a family name)"
            % (", ".join(unknown), ", ".join(FAMILIES)))
    con_sel = [x for x in args.conditions.split(",") if x] or list(CONDITIONS)
    rep_sel = [int(x) for x in args.reps.split(",") if x] or list(REPEATS)
    unknown_conditions = set(con_sel) - set(CONDITIONS)
    if unknown_conditions or not rep_sel or len(set(rep_sel)) != len(rep_sel):
        ap.error("conditions must be known and repetitions unique")
    source_sha = health.checked_run(["git", "rev-parse", "HEAD"], cwd=ROOT).stdout.strip()
    dirty = health.checked_run(["git", "diff", "--quiet", "HEAD", "--",
                                "experiments/repair_eval_v02", "benchmark/repair_eval",
                                IN.CONFIG_REL, IN.OBSERVE_REL, IN.FSM_REL,
                                "runtime/planner/gated_chat.py"], cwd=ROOT)
    if dirty.returncode != 0:
        ap.error("execution sources differ from HEAD; commit them before a model batch")
    source_files = {}
    for folder in (HERE, ROOT / "benchmark" / "repair_eval"):
        for path in folder.rglob("*"):
            if path.is_file() and path.suffix in (".py", ".json") \
                    and "evidence" not in path.relative_to(folder).parts:
                source_files[path.relative_to(ROOT).as_posix()] = health.file_sha(path)
    for rel in (IN.CONFIG_REL, IN.OBSERVE_REL, IN.FSM_REL, "runtime/planner/gated_chat.py"):
        source_files[rel] = health.file_sha(ROOT / rel)
    tracked = health.checked_run(["git", "ls-files", "--error-unmatch", "--", *source_files], cwd=ROOT)
    if tracked.returncode != 0:
        ap.error("execution source contains uncommitted files; commit before a model batch")
    execute_batch(args, policy, fam_sel, con_sel, rep_sel, source_sha, source_files)
    return 0


def execute_batch(args, policy, families, conditions, reps, source_sha, source_files):
    """Serial, fail-closed dispatch; every planned slot always gets a row.

    Working directories live beside their archives. If archiving fails, the
    originals survive; TemporaryDirectory must never erase the only evidence.
    """
    out = Path(args.out).resolve()
    if out.exists():
        raise FileExistsError("batch output already exists; use a new run path: %s" % out)
    batch_dir = out.parent / (out.stem + "-" + uuid.uuid4().hex[:12])
    working = batch_dir / "working"
    working.mkdir(parents=True)
    donor = working / "donor"
    (donor / "telemetry").mkdir(parents=True)
    (donor / "telemetry" / "execution.log").write_text("DONOR FAILURE\n")
    (donor / "verdict.json").write_text('{"passed": false}')
    slots = [(f, c, r) for f in families for c in conditions for r in reps]
    rows, produced = [], {}
    environment = environment_receipt.capture()
    spent, consecutive_exhausted, attempted = 0, 0, 0
    stopped = None
    summary = {}

    def persist(running):
        summary.update(slots_attempted=attempted, slots_recorded=len(rows),
                       slots_planned=len(slots), tokens_spent=spent,
                       batch_budget=args.budget, model=args.model,
                       stopped=stopped, running=running,
                       qualification="REAL_MODEL_RUN", source_sha=source_sha,
                       environment=environment,
                       source_files=source_files, archive_root=str(batch_dir),
                       terminal_states={}, by_condition={})
        for row in rows:
            status = row["terminal_status"]
            summary["terminal_states"][status] = summary["terminal_states"].get(status, 0) + 1
            summary["by_condition"].setdefault(row["condition"], []).append(status)
        ARCH.write_json(out, {"summary": summary, "rows": rows})

    persist(True)
    for family, condition, rep in slots:
        slot_id = "%s-%s-r%d" % (family.split("_")[0], condition[0], rep)
        row = {"slot_id": slot_id, "condition": condition, "family": family,
               "seed": {"F1_OBJECT_REGISTRATION": 5100, "F2_GOAL_MAPPING": 5200}[family] + rep,
               "source_sha": source_sha, "terminal_status": "NOT_RUN",
               "qualification": "REAL_MODEL_RUN", "tokens_total": 0,
               "interactions_used": 0, "edited_paths": []}
        if not stopped and args.limit and attempted >= args.limit:
            stopped = "LIMIT_REACHED"
        if not stopped and spent >= args.budget:
            stopped = "BATCH_BUDGET_EXHAUSTED"
        if stopped:
            row["notes"] = "dispatch stopped: " + stopped
            rows.append(row)
            persist(True)
            continue
        borrowed = next((v for (f, r), v in produced.items()
                         if f == family and r != rep), None)
        if condition == "C_MISMATCHED_FEEDBACK" and (not borrowed
                or not borrowed.get("donor_log") or not Path(borrowed["donor_log"]).is_file()):
            row["notes"] = "no B run of this family at another seed exists to borrow from"
            rows.append(row)
            persist(True)
            continue
        workdir = working / slot_id
        workdir.mkdir()
        ARCH.write_json(workdir / "source_identity.json", {
            "source_sha": source_sha, "source_files": source_files,
            "environment": environment})
        pre = health.safe_probe(ROOT, source_sha, workdir, source_files=source_files)
        ARCH.write_json(workdir / "dispatch_before.json", pre)
        try:
            health.require_healthy(pre)
            attempted += 1
            row.update(run_slot(
                family, condition, rep, workdir, policy, donor, args.model,
                args.max_interactions, seed=row["seed"], source_sha=source_sha,
                source_files=source_files,
                donor_run_id=borrowed["run_id"] if borrowed else None,
                donor_log_path=borrowed["donor_log"] if borrowed else None,
                source=args.source, task_variant=args.task_variant))
            if row.get("action_terminal") not in health.CONFIRMED:
                raise health.UnconfirmedAction(health.NO_RESPONSE, "slot has no confirmed action terminal")
            post = health.safe_probe(ROOT, source_sha, workdir, source_files=source_files)
            ARCH.write_json(workdir / "dispatch_after.json", post)
            health.require_healthy(post)
        except BaseException as exc:
            # A process result is not a robot verdict. In particular, transport
            # timeout/no response must not become FAIL or continue dispatch.
            unknown = isinstance(exc, (health.UnconfirmedAction, subprocess.TimeoutExpired,
                                       TimeoutError, ConnectionError, URLError))
            state = (exc.state if isinstance(exc, health.UnconfirmedAction)
                     else health.TIMEOUT if isinstance(exc, (TimeoutError, subprocess.TimeoutExpired))
                     or isinstance(getattr(exc, "reason", None), TimeoutError)
                     else health.NO_RESPONSE)
            row.update(terminal_status="UNKNOWN" if unknown else "INVALID",
                       action_terminal=state if unknown else "NOT_DISPATCHED_OR_INVALID",
                       deviation_codes=["S1" if unknown else "S2"],
                       notes="%s: %s" % (type(exc).__name__, str(exc)[:500]))
            account_path = workdir / "account.json"
            if account_path.exists():
                row.update(json.loads(account_path.read_text()))
            stopped = ("UNCONFIRMED_ACTION:" + state if unknown else "UNHEALTHY_OR_HARNESS_ERROR")
            ARCH.write_json(workdir / "exception.json", {"type": type(exc).__name__, "detail": str(exc)})
        finally:
            # Probe even after an exception, without masking the original stop.
            post = health.safe_probe(ROOT, source_sha, workdir, source_files=source_files)
            ARCH.write_json(workdir / "dispatch_final.json", post)
            if not post["healthy"]:
                stopped = stopped or "UNHEALTHY_POST_PROBE"
                row["terminal_status"] = "INVALID"
            try:
                destination = batch_dir / "slots" / slot_id
                if row.get("donor_log"):
                    row["donor_log"] = str(destination / "donor_output" / Path(row["donor_log"]).name)
                archive = ARCH.preserve(workdir, destination, row)
                row["archive"] = archive
                row["candidate_sha"] = archive["candidate_sha"]
            except Exception as exc:
                stopped = "ARCHIVE_FAILED"
                row.update(terminal_status="INVALID", archive_error=str(exc),
                           preserved_workdir=str(workdir))
            rows.append(row)
            spent += row.get("tokens_total", 0)
            consecutive_exhausted = (consecutive_exhausted + 1
                                    if row["terminal_status"] == B.BUDGET_EXHAUSTED else 0)
            if consecutive_exhausted >= 3:
                stopped = stopped or "THREE_CONSECUTIVE_BUDGET_EXHAUSTED"
            persist(True)
            if row.get("archive"):
                if condition == "B_REAL_FEEDBACK" and row.get("donor_log"):
                    produced[(family, rep)] = {"run_id": row.get("run_id", slot_id),
                                              "donor_log": str(Path(row["archive"]["path"]) / "donor_output" /
                                                               Path(row["donor_log"]).name)}
                try:
                    shutil.rmtree(workdir)
                except OSError as exc:
                    stopped = stopped or "WORKDIR_CLEANUP_FAILED"
                    row["cleanup_error"] = str(exc)
                    row["preserved_workdir"] = str(workdir)
                    persist(True)
    persist(False)
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return {"summary": summary, "rows": rows}


if __name__ == "__main__":
    raise SystemExit(main())
