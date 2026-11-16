#!/usr/bin/env python3
"""Aggregation-layer checks for scripts/offline_audit (issue #246).

Every case drives the real CLI in a subprocess with a temporary run directory.
The three existing sub-tools are replaced by small deterministic stubs so these
tests check ONLY the new aggregation contract: status, reason codes, issue
propagation, output safety and exit codes. One case at the end invokes the real
run_log_audit.py end to end.
"""
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_json(path, doc):
    return write(path, json.dumps(doc, sort_keys=True) + "\n")


def stub(path, report_name, summary, exit_code):
    """A child process that behaves like one of the three existing tools."""
    script = """
import json, pathlib, sys
out = pathlib.Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
(out / %r).write_text(json.dumps(%r), encoding='utf-8')
sys.exit(%d)
""" % (report_name, summary, exit_code)
    return write(path, script)


PROFILE = {
    "schema_version": 1,
    "requires": {
        "retention": [],
        "progress": ["attempts.jsonl"],
        "timeline": [["observations.jsonl"], ["phases.jsonl"]],
    },
}
OK_RETENTION = {"schema_version": 1, "status": "COMPLETE", "runs": [],
                "totals": {"runs": 0, "missing_items": 0}}
OK_PROGRESS = {"status": "MEASURED", "code": "OK", "reason_codes": [],
               "inputs_unchanged": True}
OK_TIMELINE = {"status": "ALIGNED", "code": "OK", "reason_codes": [],
               "inputs_unchanged": True}


class OfflineAuditCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="offline-audit-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.run = self.base / "run-0001"
        self.run.mkdir()
        self.profile = write_json(self.base / "profile.json", PROFILE)
        self.out = self.base / "out"
        self.stubs = self.base / "stubs"
        self.stubs.mkdir()

    def with_inputs(self):
        for name in ("attempts.jsonl", "observations.jsonl", "phases.jsonl"):
            write(self.run / name, "")

    def use_stubs(self, retention=(OK_RETENTION, 0), progress=(OK_PROGRESS, 0),
                  timeline=(OK_TIMELINE, 0)):
        specs = {
            "retention": ("audit.json",) + retention,
            "progress": ("summary.json",) + progress,
            "timeline": ("summary.json",) + timeline,
        }
        paths = {}
        for name, (report, summary, code) in specs.items():
            paths[name] = stub(self.stubs / (name + ".py"), report, summary, code)
        driver = """
import sys
sys.path.insert(0, %r)
from scripts.offline_audit import cli
paths = %r
for name, path in paths.items():
    cli.SUBTOOLS[name] = lambda run, out, p=path: [sys.executable, str(p), str(out)]
sys.exit(cli.main(%r))
""" % (str(ROOT), {k: str(v) for k, v in paths.items()},
       ["--run", str(self.run), "--out", str(self.out),
        "--profile", str(self.profile)])
        return write(self.base / "driver.py", driver)

    def invoke(self, driver=None, args=None):
        command = [sys.executable, str(driver)] if driver else [
            sys.executable, "-m", "scripts.offline_audit",
            "--run", str(self.run), "--out", str(self.out),
            "--profile", str(self.profile)]
        if args:
            command += args
        return subprocess.run(command, cwd=str(ROOT), capture_output=True,
                              text=True, timeout=120)

    def report(self):
        return json.loads((self.out / "report.json").read_text(encoding="utf-8"))

    # -- contract ---------------------------------------------------------
    def test_report_contract_and_subtool_reports_are_kept(self):
        self.with_inputs()
        proc = self.invoke(self.use_stubs())
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        report = self.report()
        self.assertEqual(report["schema_version"], "offline-run-audit/1")
        self.assertIs(report["diagnostic_only"], True)
        self.assertEqual(report["robot_task_outcome"], "NOT_EVALUATED")
        self.assertEqual([c["name"] for c in report["checks"]],
                         ["retention", "progress", "timeline"])
        self.assertTrue(all(c["status"] == "COMPLETE" for c in report["checks"]))
        self.assertEqual([c["sub_report"] for c in report["checks"]],
                         ["retention/audit.json", "progress/summary.json",
                          "timeline/summary.json"])
        self.assertEqual(report["issues"], [])
        self.assertEqual(report["derived_inputs"], [])
        self.assertEqual(report["source"]["run_id"], "run-0001")
        self.assertEqual(sorted(i["path"] for i in report["source"]["inputs"]),
                         ["attempts.jsonl", "observations.jsonl", "phases.jsonl"])
        for name in ("retention", "progress", "timeline"):
            self.assertTrue((self.out / name).is_dir())

    def test_unknown_with_zero_exit_is_not_reported_as_complete(self):
        self.with_inputs()
        unknown = dict(OK_PROGRESS, status="UNKNOWN", code="ENDPOINTS_MISSING",
                       reason_codes=["ENDPOINTS_MISSING"])
        proc = self.invoke(self.use_stubs(progress=(unknown, 0)))
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = self.report()
        progress = report["checks"][1]
        self.assertEqual(progress["exit_code"], 0)
        self.assertEqual(progress["status"], "UNKNOWN")
        self.assertIn("ENDPOINTS_MISSING", progress["reason_codes"])
        self.assertTrue(any(i["code"] == "NOT_FULLY_DETERMINED"
                            for i in report["issues"]))
        self.assertEqual(report["robot_task_outcome"], "NOT_EVALUATED")

    def test_missing_input_is_disclosed_and_not_filled(self):
        write(self.run / "observations.jsonl", "")
        write(self.run / "phases.jsonl", "")
        proc = self.invoke(self.use_stubs())
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = self.report()
        progress = report["checks"][1]
        self.assertIs(progress["executed"], False)
        self.assertEqual(progress["status"], "NOT_APPLICABLE")
        self.assertIsNone(progress["sub_report"])
        self.assertTrue(any(i["code"] == "INPUT_ABSENT" for i in report["issues"]))

    def test_subtool_error_propagates_and_products_survive(self):
        self.with_inputs()
        failing = dict(OK_TIMELINE, status="ERROR")
        proc = self.invoke(self.use_stubs(timeline=(failing, 2)))
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        report = self.report()
        self.assertEqual(report["checks"][2]["exit_code"], 2)
        self.assertTrue(any(i["code"] == "SUBTOOL_EXIT" for i in report["issues"]))
        self.assertTrue((self.out / "timeline" / "summary.json").is_file())
        self.assertTrue((self.out / "retention" / "audit.json").is_file())

    def test_output_safety(self):
        self.with_inputs()
        driver = self.use_stubs()
        # an existing output directory is refused
        self.out.mkdir()
        write(self.out / "keep.txt", "do not touch")
        proc = self.invoke(driver)
        self.assertEqual(proc.returncode, 2)
        self.assertIn("already exists", proc.stderr)
        self.assertEqual((self.out / "keep.txt").read_text(encoding="utf-8"),
                         "do not touch")
        # an output inside the run is refused
        self.out = self.run / "nested-out"
        proc = self.invoke(driver)
        self.assertEqual(proc.returncode, 2)
        self.assertFalse(self.out.exists())

    def test_real_retention_tool_runs_end_to_end(self):
        run = self.run
        write(run / "task.out", "RESULT %s\n" % json.dumps(
            {"outcome": 0, "error_code": 0, "detail": "ok",
             "completed_stage_ids": ["OBSERVE_A", "PUSH_A", "VERIFY_A"]}))
        write_json(run / "sim" / "episodes" / "e.json",
                   {"EpisodeSchemaVersion": 1, "steps": [{"seq": 1}],
                    "final_state": {"outcome": 0}})
        for name, rows in (("decisions.jsonl", [{"seq": 1}]),
                           ("task_fsm.jsonl", [{"outcome": 0}]),
                           ("observe.jsonl", [{"event": "request"}]),
                           ("move_to_pose.jsonl", [{"event": "request"}]),
                           ("push.jsonl", [{"event": "request"}]),
                           ("verify.jsonl", [{"event": "request"}])):
            write(run / name, "".join(json.dumps(r) + "\n" for r in rows))
        write_json(run / "verdict.json", {"passed": True})
        driver = self.use_stubs()
        proc = self.invoke(driver)
        # progress/timeline have no inputs in this fixture -> aggregate exit 1,
        # but the REAL retention tool must have produced a COMPLETE check.
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = self.report()
        retention = report["checks"][0]
        self.assertEqual(retention["status"], "COMPLETE")
        self.assertEqual(retention["exit_code"], 0)
        self.assertEqual(retention["sub_report"], "retention/audit.json")
        self.assertTrue((self.out / "retention" / "audit.json").is_file())


if __name__ == "__main__":
    unittest.main()
