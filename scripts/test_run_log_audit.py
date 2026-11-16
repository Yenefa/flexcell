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
            # the failure-phase candidate list has a layered twin now, so the
            # "checked everywhere" string names task.stdout:detail as well
            ["crash_detail.txt|failure_evidence.json:detail|task.out:detail"
             "|task.stdout:detail|launch.out:markers",
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
