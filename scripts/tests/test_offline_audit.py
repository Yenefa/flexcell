#!/usr/bin/env python3
"""Aggregation-layer checks for scripts/offline_audit (issue #246).

Every case drives the real CLI in a subprocess with a temporary run directory.
The three existing sub-tools are replaced by small deterministic stubs so these
tests check ONLY the new aggregation contract: status, reason codes, issue
propagation, output safety and exit codes. One case at the end invokes the real
run_log_audit.py end to end.
"""
import hashlib
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
OK_RETENTION = {"schema_version": 1, "runs": [],
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
                  timeline=(OK_TIMELINE, 0), real=()):
        """``real`` names checks that must call their genuine tool instead."""
        specs = {
            "retention": ("audit.json",) + retention,
            "progress": ("summary.json",) + progress,
            "timeline": ("summary.json",) + timeline,
        }
        paths = {}
        for name, (report, summary, code) in specs.items():
            if name in real:
                continue
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
        driver = self.use_stubs(real=("retention",))
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

    def test_out_of_order_and_duplicate_stamps_are_disclosed_not_dropped(self):
        run = self.run
        # Retention inputs so the run is readable; the point of this case is the
        # timeline: out-of-order stamps plus a duplicate copy and a conflicting one.
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
        observations = [
            {"source_stamp_ns": 3000, "pose": {"x": 0.3, "y": 0.0, "z": 0.1}},
            {"source_stamp_ns": 1000, "pose": {"x": 0.1, "y": 0.0, "z": 0.1}},
            {"source_stamp_ns": 2000, "pose": {"x": 0.2, "y": 0.0, "z": 0.1}},
            # Same stamp AND same pose: the recorder delivered the snapshot twice.
            {"source_stamp_ns": 2000, "pose": {"x": 0.2, "y": 0.0, "z": 0.1}},
            # Same stamp, different pose: a conflicting measurement, not a copy.
            {"source_stamp_ns": 2000, "pose": {"x": 0.25, "y": 0.0, "z": 0.1}},
        ]
        phases = [{"phase": "OBSERVE_A", "source_stamp_ns": 500},
                  {"phase": "PUSH_A", "source_stamp_ns": 1500},
                  {"phase": "VERIFY_A", "source_stamp_ns": 2500}]
        obs_path = write(run / "observations.jsonl",
                         "".join(json.dumps(r) + "\n" for r in observations))
        write(run / "phases.jsonl",
              "".join(json.dumps(r) + "\n" for r in phases))
        before = hashlib.sha256(obs_path.read_bytes()).hexdigest()

        proc = self.invoke(self.use_stubs(real=("retention", "timeline")))
        # Timeline rows are unalignable but the tool exits 0 -> aggregate must
        # report UNKNOWN and exit 1, never claim the diagnostics are complete.
        self.assertEqual(proc.returncode, 1, proc.stdout + proc.stderr)
        report = self.report()
        timeline = report["checks"][2]
        self.assertEqual(timeline["status"], "UNKNOWN")
        self.assertEqual(timeline["exit_code"], 0)
        self.assertTrue(any(issue["code"] == "NOT_FULLY_DETERMINED"
                            and issue.get("check") == "timeline"
                            for issue in report["issues"]))
        summary = json.loads(
            (self.out / "timeline" / "summary.json").read_text(encoding="utf-8"))
        # Nothing is dropped or re-sorted away: every row is still accounted for.
        self.assertEqual(summary["rows_total"], 5)
        self.assertLess(summary["rows_counted"], summary["rows_total"])
        self.assertEqual(summary["reasons"], {"OUT_OF_ORDER": 2,
                                              "DUPLICATE_COPY": 1,
                                              "DUPLICATE_SOURCE_STAMP": 1})
        self.assertEqual(hashlib.sha256(obs_path.read_bytes()).hexdigest(), before)
        self.assertEqual(report["robot_task_outcome"], "NOT_EVALUATED")


class Long1AdapterCase(unittest.TestCase):
    """Second PR: native archive verification, safe extraction and mapping.

    These fixtures are tiny on purpose: the 32 MB acceptance ZIP is exercised
    manually, while CI checks the contract against a deterministic mini archive.
    """

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="long1-adapter-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)
        self.zip = self.base / "LONG_1.zip"
        self.out = self.base / "out"
        self.files = {
            "LONG_1/provenance.json": {
                "label": "LONG_1", "backend": "finger_tcp",
                "task_sha256": "aaa", "image_source_revision": "bbb"},
            "LONG_1/runtime/runtime_result.json": {
                "status": "TASK_COMPLETED",
                "runtime_result": {
                    "component_run_ids": ["contact-AAA"],
                    "component_goal_uuids": ["1111"]}},
            "LONG_1/verdict.json": {"passed": True},
            "LONG_1/run_status.json": {"status": "EXECUTED"},
            "LONG_1/worldstate/summary.json": {"status": "INTERRUPTED"},
            "LONG_1/worldstate/world_state.jsonl": [
                {"channel": "topic", "rx_utc_ns": 1},
                {"channel": "result", "rx_utc_ns": 2}],
            "LONG_1/worldstate/events.jsonl": [{"kind": "READY"}],
            "LONG_1/contact_goals/contact-AAA-1111/action_result.json": {
                "request_id": "contact-AAA", "goal_uuid": "1111",
                "outcome": 0, "error_code": 0, "arm_ready": True,
                "return_completed": True, "motion_terminal_known": True,
                "motion_goals_used": 12},
            # Deliberately written out of seq order: ordering must use native seq.
            "LONG_1/sim/skills/composites/c.jsonl": [
                {"seq": 2, "event": "OBSERVATION", "stage_id": "push_00",
                 "boundary": "after"},
                {"seq": 1, "event": "PLAN", "goal_uuid": "root"},
            ],
        }
        self.make_zip(self.files)

    def make_zip(self, files):
        import zipfile
        with zipfile.ZipFile(self.zip, "w") as bundle:
            for name, content in files.items():
                if isinstance(content, str):
                    body = content
                elif isinstance(content, list):
                    body = "".join(json.dumps(r) + "\n" if isinstance(r, dict)
                                   else r + "\n" for r in content)
                else:
                    body = json.dumps(content)
                bundle.writestr(name, body)

    def normalized(self, name):
        return json.loads((self.out / "normalized" / name).read_text(encoding="utf-8"))

    def test_zip_sha_is_verified_and_traversal_is_refused(self):
        from scripts.offline_audit import long1
        digest = long1.sha256_file(self.zip)
        self.assertEqual(long1.verify_zip(self.zip)[0], digest)
        manifest = write_json(self.base / "archive.json",
                              {"sha256": "0" * 64, "executed_source": "deadbeef"})
        with self.assertRaises(long1.AdapterError):
            long1.verify_zip(self.zip, manifest)
        evil = self.base / "evil.zip"
        self.make_zip({"LONG_1/../../escape.txt": "no"})
        with self.assertRaises(long1.AdapterError):
            long1.safe_extract(evil, self.base / "escaped")

    def test_native_ids_order_and_conflicts_are_preserved(self):
        from scripts.offline_audit import long1
        root = long1.safe_extract(self.zip, self.base / "extracted")
        run = long1.find_long1(root)
        norm_dir = self.base / "norm-only"
        norm_dir.mkdir()
        derived, issues, meta = long1.normalize(
            run, norm_dir, archive_sha="abc", executed_source="deadbeef",
            tool_sha="toolhead")
        seq = json.loads((norm_dir / "normalized" / "composite_sequence.json").read_text())
        self.assertEqual([e["seq"] for e in seq["events"]], [1, 2])
        self.assertEqual(seq["order_basis"],
                         "native composite.seq (not file name or line order)")
        goals = json.loads((norm_dir / "normalized" / "contact_goals.json").read_text())
        self.assertFalse(goals["directory_name_used_for_order"])
        self.assertEqual(goals["goals"][0]["native_links"],
                         ["request_id=component_run_ids",
                          "goal_uuid=component_goal_uuids"])
        claims = json.loads((norm_dir / "normalized" / "source_claims.json").read_text())
        self.assertEqual(claims["robot_task_outcome"], "NOT_EVALUATED")
        self.assertTrue(all(c["kind"] == "source_reference" for c in claims["claims"]))
        self.assertEqual(len(claims["conflicts"]), 1)
        self.assertTrue(any(i["code"] == "SOURCE_CLAIM_CONFLICT" for i in issues))
        self.assertEqual(meta["archive_sha256"], "abc")
        self.assertEqual(meta["current_tool_version"], "toolhead")
        self.assertNotEqual(meta["archive_executed_source"],
                            meta["current_tool_version"])
        self.assertTrue(all(d["note"].startswith("read-only") for d in derived))

    def test_absent_field_is_unknown_and_explained(self):
        from scripts.offline_audit import long1
        files = dict(self.files)
        goal = dict(files["LONG_1/contact_goals/contact-AAA-1111/action_result.json"])
        goal.pop("error_code")
        files["LONG_1/contact_goals/contact-AAA-1111/action_result.json"] = goal
        self.make_zip(files)
        root = long1.safe_extract(self.zip, self.base / "extracted2")
        norm_dir = self.base / "norm-unknown"
        norm_dir.mkdir()
        _derived, issues, _meta = long1.normalize(root, norm_dir)
        goals = json.loads((norm_dir / "normalized" / "contact_goals.json").read_text())
        self.assertEqual(goals["goals"][0]["error_code"], "UNKNOWN")
        self.assertTrue(any(i["code"] == "SOURCE_FIELD_ABSENT"
                            and "error_code" in i["detail"] for i in issues))

    def test_archive_cli_end_to_end_keeps_inputs_and_separates_shas(self):
        from scripts.offline_audit import long1
        digest = long1.sha256_file(self.zip)
        manifest = write_json(self.base / "archive.json",
                              {"sha256": digest, "executed_source": "oldsource"})
        proc = subprocess.run(
            [sys.executable, "-m", "scripts.offline_audit",
             "--archive-zip", str(self.zip), "--manifest", str(manifest),
             "--out", str(self.out), "--tool-sha", "newtool"],
            cwd=str(ROOT), capture_output=True, text=True, timeout=180)
        self.assertEqual(long1.sha256_file(self.zip), digest)
        report = json.loads((self.out / "report.json").read_text(encoding="utf-8"))
        self.assertEqual(report["schema_version"], "offline-run-audit/1")
        self.assertEqual(report["robot_task_outcome"], "NOT_EVALUATED")
        self.assertEqual(report["source"]["source_sha256"], digest)
        self.assertEqual(report["source"]["normalization"]["archive_sha256"], digest)
        self.assertEqual(report["source"]["normalization"]["archive_executed_source"],
                         "oldsource")
        self.assertEqual(report["source"]["normalization"]["current_tool_version"],
                         "newtool")
        self.assertTrue((self.out / "normalized" / "identity.json").is_file())
        self.assertTrue(any(d["path"].startswith("normalized/")
                            for d in report["derived_inputs"]))
        self.assertFalse(any(i["code"] == "NORMALIZER_ERROR"
                             for i in report["issues"]), proc.stderr)
        self.assertIn(proc.returncode, (0, 1, 2))


if __name__ == "__main__":
    unittest.main()
