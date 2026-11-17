#!/usr/bin/env python3
"""Fixture-driven checks for scripts/run_log_audit.py (issue #231).

No robot, no simulator, no pytest: every case builds a SYNTHETIC run directory in a
temporary tree and runs the real audit script as a subprocess, so the assertions are
on the same exit codes and MISSING lines an operator would see.

Three fixture families are required by the issue - a run that ended normally, a run
that failed during execution, and a run that failed at startup - and each is checked
twice: once COMPLETE (the phase-aware inventory must accept it, which is the negative
test that stops the auditor demanding logs a startup failure cannot have) and once
with items removed (exact missing set and exit 1).

Three more fixtures copy the fields the writers actually persist - the RESULT
fsm_trace, the FSM/demo log steps and the episode policy_output.action - and carry
the two retention regressions from the PR #244 review: a skill jsonl emptied in
place, and a run whose executed skills appear only in those real fields.

Run directly:  python scripts/test_run_log_audit.py
"""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "scripts" / "run_log_audit.py"
CONFIG = ROOT / "config" / "run_log_required.json"


def sha256_file(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_json(path, doc):
    return write(path, json.dumps(doc, sort_keys=True) + "\n")


def write_jsonl(path, rows):
    return write(path, "".join(json.dumps(row, sort_keys=True) + "\n"
                               for row in rows))


def episode_record(run_id):
    """Shape copied from flexcell_skills/contracts/episode.py: versioned, with steps."""
    return {"EpisodeSchemaVersion": 1,
            "scenario_id": "push_v1",
            "run_id": run_id,
            "policy": {"name": "rule", "version": "0"},
            "steps": [{"seq": 1,
                       "policy_input": {"goal": {"goal_id": "t08"}},
                       "policy_output": {"action": "PUSH", "target": "red"},
                       "executor_result": {"outcome": 0}}],
            "final_state": {"outcome": 0}}


NORMAL_RESULT = {"outcome": 0, "error_code": 0,
                 "detail": "two pushes verified",
                 "completed_stage_ids": ["OBSERVE_A", "MOVE_A", "PUSH_A",
                                         "VERIFY_A"]}
FAILED_RESULT = {"outcome": 1, "error_code": 25,
                 "detail": ("PUSH_A: FAIL gripper did not open "
                            "(position=-0.011 requested=0.02 stalled=True)"),
                 "completed_stage_ids": ["OBSERVE_A", "MOVE_A"]}


# Shapes copied from the writers (task_fsm_server.py finish()/log_record and
# contracts/episode.py), not invented for the test:
#   * RunPickPlace.Result and RunDemo.Result carry fsm_trace, a list of the states
#     the FSM visited; RunComposite.Result carries completed_stage_ids of the
#     caller's own stage ids and no fsm_trace at all;
#   * task_fsm.jsonl / demo_runs.jsonl repeat fsm_trace and add steps, each naming
#     a skill ('pick') and its stage label ('PICK_A(attempt=1)');
#   * an episode step keeps the same action under steps[].policy_output.action.
SINGLE_FSM_TRACE = ["OBSERVE_A", "PICK_A(attempt=1):OK", "PLACE_A:OK",
                    "VERIFY_A(attempt=1):OK"]
DEMO_FSM_TRACE = SINGLE_FSM_TRACE + ["OBSERVE_B", "PICK_B(attempt=1):OK",
                                     "PLACE_B:OK", "VERIFY_B(attempt=1):OK"]
SINGLE_RESULT_FSM = {"outcome": 0, "error_code": 0,
                     "detail": "task done: all assignments verified",
                     "fsm_trace": SINGLE_FSM_TRACE}
DEMO_RESULT_FSM = {"outcome": 0, "error_code": 0,
                   "scenario_id": "week1_demo_v1",
                   "run_id": "week1_demo_v1-0a1b2c3d",
                   "detail": "task done: all assignments verified",
                   "fsm_trace": DEMO_FSM_TRACE,
                   "object_a_at_zone": True, "object_b_at_zone": True}
COMPOSITE_RESULT_FSM = {"outcome": 0, "error_code": 0,
                        "run_id": "composite-0123456789abcdef",
                        "completed_stage_ids": ["one", "two"],
                        "component_run_ids": ["pick_place_v1-0badc0de",
                                              "pick_place_v1-0badc0df"],
                        "detail": "all native stages and fresh joint conditions"}


def fsm_steps(entries):
    """Steps as task_fsm_server.py appends them: state label plus skill name."""
    return [{"state": state, "skill": skill, "ok": True, "error_code": 0,
             "attempt": 1}
            for state, skill in entries]


def episode_record_from_actions(run_id, actions, scenario="pick_place_v1"):
    """Episode steps as contracts/episode.py writes them: the action lives under
    policy_output, so a reader that only looks at the step's own keys sees none."""
    return {"EpisodeSchemaVersion": 1,
            "scenario_id": scenario,
            "run_id": run_id,
            "policy": {"name": "rule", "version": "0"},
            "steps": [{"seq": index + 1,
                       "policy_input": {"goal": {"goal_id": "t08"}},
                       "policy_output": {"action": action, "target": "red"},
                       "executor_result": {"outcome": 0}}
                      for index, action in enumerate(actions)],
            "final_state": {"outcome": 0}}


class Fixture:
    """Writes synthetic run directories under one temporary root."""

    def __init__(self, base):
        self.base = Path(base)
        self.runs = self.base / "runs"
        self.runs.mkdir(parents=True, exist_ok=True)

    def _result(self, run, result):
        write(run / "task.out", "session start\nRESULT %s\n"
              % json.dumps(result, sort_keys=True))

    def normal(self, name="run_normal"):
        run = self.runs / name
        self._result(run, NORMAL_RESULT)
        write_json(run / "sim" / "episodes" / "push_v1_run.json",
                   episode_record(name))
        write_jsonl(run / "decisions.jsonl",
                    [{"seq": 1, "action": "OBSERVE", "dispatching": True},
                     {"seq": 2, "action": "PUSH", "dispatching": True}])
        write_jsonl(run / "task_fsm.jsonl",
                    [{"run_id": name, "outcome": 0,
                      "completed_stage_ids": NORMAL_RESULT["completed_stage_ids"]}])
        for log in ("observe.jsonl", "move_to_pose.jsonl", "push.jsonl",
                    "verify.jsonl"):
            write_jsonl(run / log, [{"event": "request", "log": log}])
        write_json(run / "verdict.json", {"passed": True, "run": name})
        return run

    def execution_failure(self, name="run_exec_failure"):
        run = self.runs / name
        self._result(run, FAILED_RESULT)
        write_json(run / "sim" / "episodes" / "push_v1_run.json",
                   episode_record(name))
        write_jsonl(run / "decisions.jsonl",
                    [{"seq": 1, "action": "PUSH", "dispatching": True}])
        write_jsonl(run / "demo_runs.jsonl",
                    [{"run_id": name, "outcome": 1,
                      "completed_stage_ids": ["OBSERVE_A", "MOVE_A"]}])
        for log in ("observe.jsonl", "move_to_pose.jsonl", "push.jsonl"):
            write_jsonl(run / log, [{"event": "request", "log": log}])
        write_json(run / "failure_evidence.json",
                   {"error_code": 25, "detail": "gripper did not open"})
        return run

    def startup_failure(self, name="run_startup_failure"):
        run = self.runs / name
        write(run / "launch.out",
              "ros2 launch trusted_sim.launch.py\n"
              "Traceback (most recent call last):\n"
              "  File launch.py, line 24, in on_start\n"
              "RuntimeError: Gazebo did not start\n")
        write(run / "crash_detail.txt",
              "unhandled exception: RuntimeError: Gazebo did not start\n")
        return run

    # -- real writer shapes (review #244 item 4) -------------------------
    def single_fsm_trace(self, name="run_single_fsm_trace"):
        """A single-object run recorded the way task_fsm_server.py writes it.

        The RESULT carries fsm_trace (what the server's finish() sets) and no
        completed_stage_ids; task_fsm.jsonl repeats that trace and adds steps; the
        episode keeps each action under policy_output.action.
        """
        run = self.runs / name
        self._result(run, SINGLE_RESULT_FSM)
        write_json(run / "sim" / "episodes" / "pick_place_v1_one.json",
                   episode_record_from_actions(name, ("OBSERVE", "PICK",
                                                      "PLACE", "VERIFY")))
        write_jsonl(run / "decisions.jsonl",
                    [{"seq": 1, "action": "PICK", "dispatching": True}])
        write_jsonl(run / "task_fsm.jsonl",
                    [{"run_id": "pick_place_v1-0badc0de",
                      "scenario_id": "pick_place_v1", "outcome": "0",
                      "error_code": 0,
                      "detail": SINGLE_RESULT_FSM["detail"],
                      "fsm_trace": list(SINGLE_FSM_TRACE),
                      "steps": fsm_steps([("OBSERVE_A", "observe"),
                                          ("PICK_A(attempt=1)", "pick"),
                                          ("PLACE_A", "place"),
                                          ("VERIFY_A(attempt=1)", "verify")])}])
        for log in ("observe.jsonl", "verify.jsonl"):
            write_jsonl(run / log, [{"event": "request", "log": log}])
        write_json(run / "verdict.json", {"passed": True, "run": name})
        return run

    def demo_fsm_trace(self, name="run_demo_fsm_trace"):
        """The week-1.5 demo: two legs, one shared demo_runs.jsonl record."""
        run = self.runs / name
        self._result(run, DEMO_RESULT_FSM)
        for leg in ("a", "b"):
            write_json(run / "sim" / "episodes" / ("week1_demo_v1_%s.json" % leg),
                       episode_record_from_actions(
                           name, ("OBSERVE", "PICK", "PLACE", "VERIFY"),
                           scenario="week1_demo_v1"))
        write_jsonl(run / "decisions.jsonl",
                    [{"seq": 1, "action": "PICK", "dispatching": True}])
        write_jsonl(run / "demo_runs.jsonl",
                    [{"run_id": DEMO_RESULT_FSM["run_id"],
                      "scenario_id": "week1_demo_v1", "outcome": "0",
                      "error_code": 0,
                      "detail": DEMO_RESULT_FSM["detail"],
                      "fsm_trace": list(DEMO_FSM_TRACE),
                      "steps": fsm_steps([("OBSERVE_A", "observe"),
                                          ("PICK_A(attempt=1)", "pick"),
                                          ("PLACE_A", "place"),
                                          ("VERIFY_A(attempt=1)", "verify"),
                                          ("OBSERVE_B", "observe"),
                                          ("PICK_B(attempt=1)", "pick"),
                                          ("PLACE_B", "place"),
                                          ("VERIFY_B(attempt=1)", "verify")])}])
        for log in ("observe.jsonl", "verify.jsonl"):
            write_jsonl(run / log, [{"event": "request", "log": log}])
        write_json(run / "verdict.json", {"passed": True, "run": name})
        return run

    def composite_fsm_trace(self, name="run_composite_fsm_trace"):
        """A composite run: the RESULT has no fsm_trace and its completed stage ids
        are the caller's own ('one', 'two'), so executed skills show up only in the
        nested native records - task_fsm.jsonl steps and per-stage episodes."""
        run = self.runs / name
        self._result(run, COMPOSITE_RESULT_FSM)
        records = []
        for index, leg in enumerate(("one", "two")):
            component_run = "pick_place_v1-0badc0d%s" % (
                "e" if index == 0 else "f")
            write_json(run / "sim" / "episodes"
                       / ("pick_place_v1_%s.json" % leg),
                       episode_record_from_actions(
                           component_run,
                           ("OBSERVE", "PICK", "PLACE", "VERIFY")))
            records.append(
                {"run_id": component_run,
                 "parent_run_id": COMPOSITE_RESULT_FSM["run_id"],
                 "stage_id": leg,
                 "execution_kind": "IN_PROCESS_COMPONENT",
                 "scenario_id": "pick_place_v1", "outcome": "0",
                 "error_code": 0,
                 "fsm_trace": list(SINGLE_FSM_TRACE),
                 "steps": fsm_steps([("OBSERVE_A", "observe"),
                                     ("PICK_A(attempt=1)", "pick"),
                                     ("PLACE_A", "place"),
                                     ("VERIFY_A(attempt=1)", "verify")])})
        write_jsonl(run / "task_fsm.jsonl", records)
        write_jsonl(run / "decisions.jsonl",
                    [{"seq": 1, "action": "PICK", "dispatching": True}])
        for log in ("observe.jsonl", "verify.jsonl"):
            write_jsonl(run / log, [{"event": "request", "log": log}])
        write_json(run / "verdict.json", {"passed": True, "run": name})
        return run


class AuditCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="run-log-audit-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.fx = Fixture(self.base)
        self.out_root = self.base / "out"

    # -- helpers ---------------------------------------------------------
    def audit(self, target, *extra, config=None):
        command = [sys.executable, str(AUDIT), str(target),
                   "--out-root", str(self.out_root)]
        if config is not None:
            command += ["--config", str(config)]
        command += list(extra)
        return subprocess.run(command, capture_output=True, text=True,
                              cwd=str(ROOT))

    def latest_report(self):
        dirs = sorted(p for p in self.out_root.iterdir() if p.is_dir())
        self.assertTrue(dirs, "audit wrote no output directory")
        report = json.loads((dirs[-1] / "audit.json").read_text(encoding="utf-8"))
        return dirs[-1], report

    def runs_by_id(self, report):
        return {run["run_id"]: run for run in report["runs"]}

    def missing_ids(self, run):
        return sorted(item["id"] for item in run["missing"])

    def missing_paths(self, run):
        return sorted(item["path"] for item in run["missing"])

    # -- complete fixtures, one per phase --------------------------------
    def test_complete_runs_pass_and_startup_demands_no_task_level_logs(self):
        self.fx.normal()
        self.fx.execution_failure()
        self.fx.startup_failure()
        proc = self.audit(self.fx.runs)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out_dir, report = self.latest_report()
        self.assertTrue(report["passed"])
        self.assertEqual(report["totals"]["runs"], 3)
        runs = self.runs_by_id(report)
        self.assertEqual(runs["run_normal"]["phase"], "success")
        self.assertEqual(runs["run_exec_failure"]["phase"], "failure")
        self.assertEqual(runs["run_startup_failure"]["phase"], "startup_failure")
        self.assertEqual(runs["run_normal"]["missing"], [])
        self.assertEqual(runs["run_exec_failure"]["missing"], [])
        self.assertEqual(runs["run_startup_failure"]["missing"], [])
        # phase-aware inventory: startup failure needs the launch record and crash
        # detail only, never an episode/decision/skill log it cannot have
        self.assertEqual(sorted(runs["run_startup_failure"]["required_ids"]),
                         ["crash_detail", "launch_record"])
        self.assertIn("failure_evidence",
                      runs["run_exec_failure"]["required_ids"])
        self.assertIn("verdict", runs["run_normal"]["required_ids"])
        self.assertNotIn("verdict", runs["run_exec_failure"]["required_ids"])
        self.assertIn("audit summary: 3 run(s), 3 passed",
                      proc.stdout)
        self.assertIn("0 bytes copied", proc.stdout)
        self.assertTrue((out_dir / "audit.json").is_file())

    # -- deficit variants: exact missing sets, exit 1 --------------------
    def test_normal_run_without_push_log_names_it_and_exits_1(self):
        run = self.fx.normal()
        (run / "push.jsonl").unlink()
        proc = self.audit(self.fx.runs)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        _out, report = self.latest_report()
        run_report = self.runs_by_id(report)["run_normal"]
        self.assertFalse(run_report["passed"])
        self.assertEqual(self.missing_ids(run_report), ["skill_logs"])
        self.assertEqual(self.missing_paths(run_report), ["push.jsonl"])
        line = [ln for ln in proc.stdout.splitlines()
                if ln.startswith("MISSING: run_normal/push.jsonl (")]
        self.assertEqual(len(line), 1, proc.stdout)
        # the reason names the stage that proves the skill ran
        self.assertIn("PUSH_A", line[0])
        self.assertIn("not retained", line[0])

    def test_failed_run_without_failure_evidence_or_detail_exits_1(self):
        run = self.fx.execution_failure()
        (run / "failure_evidence.json").unlink()
        write(run / "task.out", "session start\nRESULT %s\n"
              % json.dumps({"outcome": 1, "error_code": 25, "detail": "",
                            "completed_stage_ids": ["OBSERVE_A", "MOVE_A"]},
                           sort_keys=True))
        proc = self.audit(self.fx.runs)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        _out, report = self.latest_report()
        run_report = self.runs_by_id(report)["run_exec_failure"]
        self.assertEqual(self.missing_ids(run_report),
                         ["crash_detail", "failure_evidence"])
        self.assertEqual(
            self.missing_paths(run_report),
            ["crash_detail.txt|failure_evidence.json:detail|task.out:detail"
             "|launch.out:markers",
             "failure_evidence.json"])
        self.assertIn("MISSING: run_exec_failure/failure_evidence.json (",
                      proc.stdout)
        self.assertIn("MISSING: run_exec_failure/crash_detail", proc.stdout)

    def test_startup_failure_without_launch_record_exits_1(self):
        run = self.fx.startup_failure()
        (run / "launch.out").unlink()
        proc = self.audit(self.fx.runs)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        _out, report = self.latest_report()
        run_report = self.runs_by_id(report)["run_startup_failure"]
        # crash detail still comes from crash_detail.txt, so only the launch
        # record is missing - and nothing task-level is demanded
        self.assertEqual(self.missing_ids(run_report), ["launch_record"])
        self.assertEqual(self.missing_paths(run_report), ["launch.out"])
        for forbidden in ("sim/episodes", "decisions.jsonl", "skill_log_any"):
            self.assertNotIn(forbidden, proc.stdout)

    def test_startup_failure_without_any_detail_exits_1(self):
        # a launch capture that exists but is empty still identifies a run; it is
        # an unexplained startup failure, which must fail rather than be skipped
        run = self.fx.startup_failure()
        (run / "launch.out").write_text("", encoding="utf-8")
        (run / "crash_detail.txt").unlink()
        proc = self.audit(self.fx.runs)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        _out, report = self.latest_report()
        run_report = self.runs_by_id(report)["run_startup_failure"]
        self.assertEqual(self.missing_ids(run_report),
                         ["crash_detail", "launch_record"])

    # -- review #244 item 4: derive executed skills from the real shapes --
    def test_real_fsm_trace_and_steps_without_pick_place_logs_exit_1(self):
        """The regression the review reproduced: a run recorded with the fields the
        server actually writes, with pick.jsonl and place.jsonl missing, was
        audited as complete because only completed_stage_ids/stage_ids/stages were
        read. All three persisted shapes must now name the lost logs."""
        single = self.fx.single_fsm_trace()
        demo = self.fx.demo_fsm_trace()
        composite = self.fx.composite_fsm_trace()
        proc = self.audit(self.fx.runs)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        _out, report = self.latest_report()
        runs = self.runs_by_id(report)
        for run_id in ("run_single_fsm_trace", "run_demo_fsm_trace",
                       "run_composite_fsm_trace"):
            with self.subTest(run=run_id):
                run_report = runs[run_id]
                self.assertFalse(run_report["passed"])
                # one skill_logs entry per lost log file
                self.assertEqual(set(self.missing_ids(run_report)),
                                 {"skill_logs"})
                self.assertEqual(self.missing_paths(run_report),
                                 ["pick.jsonl", "place.jsonl"])
                self.assertIn("PICK_A", run_report["stage_ids"])
                self.assertIn("PLACE_A", run_report["stage_ids"])
        line = [ln for ln in proc.stdout.splitlines()
                if ln.startswith("MISSING: run_single_fsm_trace/pick.jsonl (")]
        self.assertEqual(len(line), 1, proc.stdout)
        self.assertIn("PICK", line[0])
        self.assertIn("absent", line[0])

        # the same runs pass once the two logs are retained, so the new derivation
        # demands nothing the writers never produced
        for already_there in (single, demo, composite):
            write_jsonl(already_there / "pick.jsonl",
                        [{"event": "request", "log": "pick.jsonl"}])
            write_jsonl(already_there / "place.jsonl",
                        [{"event": "request", "log": "place.jsonl"}])
        again = self.audit(self.fx.runs)
        self.assertEqual(again.returncode, 0, again.stdout + again.stderr)
        _out, report = self.latest_report()
        self.assertTrue(report["passed"])

    def test_episode_policy_output_action_is_stage_evidence(self):
        """An archive can keep the episode and lose the FSM record: the action is
        only visible under steps[].policy_output.action."""
        run = self.fx.normal("run_episode_only")
        # remove every other stage source: no fsm_trace, no completed ids, no stage
        # token in the detail, and an FSM log that names no stage
        write(run / "task.out", "session start\nRESULT %s\n" % json.dumps(
            {"outcome": 0, "error_code": 0, "detail": "task done"},
            sort_keys=True))
        write_jsonl(run / "task_fsm.jsonl",
                    [{"run_id": "pick_place_v1-0badc0de", "outcome": "0",
                      "error_code": 0}])
        write_json(run / "sim" / "episodes" / "pick_place_v1_run.json",
                   episode_record_from_actions(
                       "run_episode_only", ("OBSERVE", "PICK", "PLACE",
                                            "VERIFY")))
        # normal() never wrote pick/place: the episode actions are the only source
        for absent in ("pick.jsonl", "place.jsonl"):
            self.assertFalse((run / absent).exists(), absent)
        proc = self.audit(self.fx.runs)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        _out, report = self.latest_report()
        run_report = self.runs_by_id(report)["run_episode_only"]
        self.assertEqual(set(self.missing_ids(run_report)), {"skill_logs"})
        self.assertEqual(self.missing_paths(run_report),
                         ["pick.jsonl", "place.jsonl"])

    def test_recovery_observe_stage_still_demands_the_observe_log(self):
        """REOBSERVE_A is the label the FSM writes for a recovery observation; the
        skill that ran is still observe, so observe.jsonl is still owed even when
        the step list did not record it."""
        run = self.fx.single_fsm_trace("run_recovery_observe")
        (run / "observe.jsonl").unlink()
        trace = ["REOBSERVE_A", "PICK_A(attempt=2):OK", "PLACE_A:OK",
                 "VERIFY_A(attempt=1):OK"]
        write(run / "task.out", "session start\nRESULT %s\n" % json.dumps(
            {"outcome": 0, "error_code": 0, "detail": "task done",
             "fsm_trace": trace}, sort_keys=True))
        write_jsonl(run / "task_fsm.jsonl",
                    [{"run_id": "pick_place_v1-0badc0de", "outcome": "0",
                      "error_code": 0, "fsm_trace": trace,
                      "steps": fsm_steps([("PICK_A(attempt=2)", "pick"),
                                          ("PLACE_A", "place"),
                                          ("VERIFY_A(attempt=1)", "verify")])}])
        write_json(run / "sim" / "episodes" / "pick_place_v1_one.json",
                   episode_record_from_actions(
                       "run_recovery_observe", ("PICK", "PLACE", "VERIFY")))
        proc = self.audit(self.fx.runs)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        line = [ln for ln in proc.stdout.splitlines()
                if ln.startswith("MISSING: run_recovery_observe/observe.jsonl (")]
        self.assertEqual(len(line), 1, proc.stdout)
        self.assertIn("REOBSERVE_A", line[0])

    # -- review #244 item 3: a retained-but-empty log is not evidence -----
    def test_emptied_skill_log_is_reported_missing(self):
        """The regression the review reproduced: truncating an executed skill's
        jsonl to zero bytes left the audit at exit 0, because existence was the
        only question asked."""
        run = self.fx.normal()
        (run / "push.jsonl").write_text("", encoding="utf-8")
        proc = self.audit(self.fx.runs)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        _out, report = self.latest_report()
        run_report = self.runs_by_id(report)["run_normal"]
        self.assertFalse(run_report["passed"])
        self.assertEqual(self.missing_ids(run_report), ["skill_logs"])
        self.assertEqual(self.missing_paths(run_report), ["push.jsonl"])
        line = [ln for ln in proc.stdout.splitlines()
                if ln.startswith("MISSING: run_normal/push.jsonl (")]
        self.assertEqual(len(line), 1, proc.stdout)
        self.assertIn("PUSH_A", line[0])
        self.assertIn("empty", line[0])

    def test_skill_log_with_only_unparseable_lines_is_reported_missing(self):
        run = self.fx.normal()
        (run / "push.jsonl").write_text('not json at all\n{"event": "req',
                                        encoding="utf-8")
        proc = self.audit(self.fx.runs)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        line = [ln for ln in proc.stdout.splitlines()
                if ln.startswith("MISSING: run_normal/push.jsonl (")]
        self.assertEqual(len(line), 1, proc.stdout)
        self.assertIn("no valid JSONL record", line[0])

    def test_skill_log_tolerance_is_unchanged(self):
        """Tightening must not punish the crash tail the other jsonl items already
        tolerate, and a garbage line beside real records is still not a valid log."""
        run = self.fx.normal()
        (run / "push.jsonl").write_text('{"event": "request"}\n{"event": "res',
                                        encoding="utf-8")
        proc = self.audit(run)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        (run / "push.jsonl").write_text(
            '{"event": "request"}\nnot json\n{"event": "done"}\n',
            encoding="utf-8")
        proc = self.audit(run)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        line = [ln for ln in proc.stdout.splitlines()
                if ln.startswith("MISSING: run_normal/push.jsonl (")]
        self.assertEqual(len(line), 1, proc.stdout)
        self.assertIn("unparseable line(s) beside", line[0])

    # -- output directory policy ----------------------------------------
    def test_each_invocation_writes_a_new_output_directory(self):
        run = self.fx.normal()
        before = {path.name: sha256_file(path) for path in run.rglob("*")
                  if path.is_file()}
        first = self.audit(run)
        second = self.audit(run)
        self.assertEqual(first.returncode, 0, first.stdout)
        self.assertEqual(second.returncode, 0, second.stdout)
        dirs = sorted(p for p in self.out_root.iterdir() if p.is_dir())
        self.assertEqual(len(dirs), 2)
        self.assertNotEqual(dirs[0], dirs[1])
        for directory in dirs:
            self.assertTrue((directory / "audit.json").is_file())
        # read-only input: the audited run is byte-identical afterwards
        after = {path.name: sha256_file(path) for path in run.rglob("*")
                 if path.is_file()}
        self.assertEqual(before, after)

    def test_existing_output_directory_is_refused(self):
        run = self.fx.normal()
        taken = self.base / "already-there"
        taken.mkdir()
        proc = self.audit(run, "--out", str(taken))
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("refusing to write into an existing output directory",
                      proc.stderr)
        self.assertFalse((taken / "audit.json").exists())

    # -- pointers, not copies -------------------------------------------
    def test_raw_artifacts_are_pointers_with_sha256_not_copies(self):
        run = self.fx.execution_failure()
        expected = {path.relative_to(run).as_posix(): sha256_file(path)
                    for path in run.rglob("*") if path.is_file()}
        proc = self.audit(run)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out_dir, report = self.latest_report()
        artifacts = {item["path"]: item
                     for item in report["runs"][0]["artifacts"]}
        self.assertEqual(artifacts["task.out"]["sha256"],
                         expected["task.out"])
        self.assertEqual(artifacts["failure_evidence.json"]["sha256"],
                         expected["failure_evidence.json"])
        self.assertIn("sim/episodes/push_v1_run.json", artifacts)
        # exactly one output file, and no run artefact was copied into it
        self.assertEqual(sorted(p.name for p in out_dir.iterdir()),
                         ["audit.json"])
        for name in expected:
            self.assertFalse((out_dir / name).exists(), name)

    # -- jsonl and episode validation -----------------------------------
    def test_truncated_final_jsonl_line_is_tolerated_but_garbage_is_not(self):
        run = self.fx.normal()
        decisions = run / "decisions.jsonl"
        decisions.write_text(decisions.read_text(encoding="utf-8")
                             + '{"seq": 3, "acti',
                             encoding="utf-8")
        proc = self.audit(run)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        decisions.write_text('{"seq": 1}\nnot json\n{"seq": 2}\n',
                             encoding="utf-8")
        proc = self.audit(run)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("MISSING: run_normal/decisions.jsonl (", proc.stdout)

    def test_episode_record_shape_is_validated(self):
        run = self.fx.normal()
        write_json(run / "sim" / "episodes" / "push_v1_run.json",
                   {"not_an_episode": True})
        proc = self.audit(run)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        _out, report = self.latest_report()
        self.assertEqual(self.missing_ids(report["runs"][0]),
                         ["episode_records"])
        self.assertEqual(self.missing_paths(report["runs"][0]),
                         ["sim/episodes/push_v1_run.json"])

    # -- batch mode ------------------------------------------------------
    def test_batch_mode_reports_every_run_and_fails_if_any_is_incomplete(self):
        self.fx.normal("run_a")
        self.fx.execution_failure("run_b")
        self.fx.startup_failure("run_c")
        (self.fx.runs / "run_a" / "verdict.json").unlink()
        proc = self.audit(self.fx.runs)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        _out, report = self.latest_report()
        runs = self.runs_by_id(report)
        self.assertEqual(sorted(runs), ["run_a", "run_b", "run_c"])
        self.assertEqual(self.missing_ids(runs["run_a"]), ["verdict"])
        self.assertEqual(self.missing_ids(runs["run_b"]), [])
        self.assertEqual(self.missing_ids(runs["run_c"]), [])
        self.assertEqual(report["totals"]["failed"], 1)
        self.assertIn("MISSING: run_a/verdict.json (", proc.stdout)

    # -- usage and config errors are exit 2, never a pass ---------------
    def test_usage_and_config_errors_exit_2(self):
        missing = self.audit(self.base / "nope")
        self.assertEqual(missing.returncode, 2)
        self.assertIn("run directory not found", missing.stderr)

        empty = self.base / "empty"
        empty.mkdir()
        no_run = self.audit(empty)
        self.assertEqual(no_run.returncode, 2)
        self.assertIn("is not a run directory and contains none", no_run.stderr)

        broken = write_json(self.base / "broken.json", {"schema_version": 1})
        bad_config = self.audit(self.fx.normal(), config=broken)
        self.assertEqual(bad_config.returncode, 2)
        self.assertIn("is invalid", bad_config.stderr)

        unknown_kind = json.loads(CONFIG.read_text(encoding="utf-8"))
        unknown_kind["items"][0]["kind"] = "whatever"
        bad_kind = write_json(self.base / "bad-kind.json", unknown_kind)
        wrong = self.audit(self.fx.normal(), config=bad_kind)
        self.assertEqual(wrong.returncode, 2)
        self.assertIn("unknown kind", wrong.stderr)

        # a run directory with no RESULT is a failure, not a pass, and never
        # silently "no items to check"
        run = self.fx.execution_failure("run_no_result")
        (run / "task.out").write_text("session start, killed\n",
                                      encoding="utf-8")
        proc = self.audit(run)
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        self.assertIn("MISSING: run_no_result/task.out (", proc.stdout)

    # -- the inventory itself -------------------------------------------
    def test_inventory_declares_the_products_the_issue_names(self):
        cfg = json.loads(CONFIG.read_text(encoding="utf-8"))
        ids = [item["id"] for item in cfg["items"]]
        for wanted in ("task_result", "launch_record", "crash_detail",
                       "episode_records", "decision_log", "fsm_log",
                       "skill_logs", "failure_evidence"):
            self.assertIn(wanted, ids)
        # the push skill log the T08 probe lost must be reachable from a stage name
        self.assertEqual(cfg["stage_skill_logs"]["PUSH"], "push.jsonl")
        for item in cfg["items"]:
            self.assertTrue(item["reason"].strip(), item["id"])
            self.assertTrue(item["phases"], item["id"])
        for phase in ("success", "failure", "startup_failure"):
            self.assertIn(phase, cfg["phases"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
