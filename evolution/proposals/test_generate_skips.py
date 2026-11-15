#!/usr/bin/env python3
"""Checks for the pre-generation status check in generate.py (issue #236).

Run directly:  python evolution/proposals/test_generate_skips.py

No pytest and no robot/model call: stdlib unittest only, and every case runs offline
against synthetic run logs.

THE GAP THESE GUARD: a generator that ignores what was already decided will keep
recommending a retired idea. docs/FACT_STATE_20261112.md records exactly that ("Synthetic
reproduction shows re-generation of a superseded release-retry idea"). So the three
required cases are:
  1. an explicitly invalidated / superseded proposal is NOT generated again;
  2. a normal proposal is still generated, and still carries human approval;
  3. a missing status record does NOT become verified or approved - it stays unknown.
Both directions of the unknown case are checked: absent status must not be read as
approval, and an overlay record without a recognised status must be refused outright.

The end-to-end cases copy the real generate.py and regress.py into a temporary
repository and run the generator as a subprocess. That keeps the gate exactly as it is
(it still requires the held-out baseline to exist) while leaving the checked-out
repository untouched - no historical proposal or evidence file is modified by this test.
"""
import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATE = ROOT / "evolution" / "proposals" / "generate.py"
REGRESS = ROOT / "evolution" / "validation" / "regress.py"
REAL_PROPOSALS = ROOT / "evolution" / "proposals"

STALL_DETAIL = ("gripper did not open (position=-0.011 requested=0.02 stalled=True)")
OCCUPIED_DETAIL = "declared destination occupied at target_box_b-1"


def write_text(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


def write_json(path, doc):
    return write_text(path, json.dumps(doc, indent=2, sort_keys=True) + "\n")


def skipped_entries(proc):
    """Parse the machine-readable skipped=[...] line."""
    for line in proc.stdout.splitlines():
        if line.startswith("skipped="):
            return json.loads(line[len("skipped="):])
    raise AssertionError("no skipped=[] line in output:\n" + proc.stdout
                         + "\n" + proc.stderr)


class SyntheticRepo:
    """A minimal repository the real generate.py can run inside."""

    def __init__(self, base):
        self.root = Path(base) / "repo"
        self.proposals = self.root / "evolution" / "proposals"
        self.proposals.mkdir(parents=True)
        (self.root / "evolution" / "validation").mkdir(parents=True)
        shutil.copy2(GENERATE, self.proposals / "generate.py")
        shutil.copy2(REGRESS, self.root / "evolution" / "validation" / "regress.py")
        # the existing gate refuses to run without the held-out baseline on disk;
        # the test supplies a synthetic one and leaves the real gate logic alone
        baseline = (self.root / "setup" / "acceptance"
                    / "evobot_heldout_n6_20261111" / "runs" / "ho-synthetic-1")
        write_json(baseline / "verdict.json", {"passed": True})
        self.runs = Path(base) / "runs"
        self.runs.mkdir()

    # -- evidence --------------------------------------------------------
    def add_failures(self, detail, error_code=25, count=4, prefix="run"):
        for index in range(count):
            run = self.runs / ("%s_%02d" % (prefix, index))
            run.mkdir()
            write_text(run / "task.out", "session start\nRESULT %s\n" % json.dumps(
                {"outcome": 1, "error_code": error_code, "detail": detail,
                 "completed_stage_ids": ["OBSERVE_A"]}, sort_keys=True))

    # -- status records --------------------------------------------------
    def add_invalidated(self, ident="actuator_stall",
                        why="the pre-registration assumed every stall was a real "
                            "release failure"):
        return write_json(self.proposals / ("%s_preregistration.json" % ident), {
            "record_kind": "EVOBOT_PREREGISTRATION",
            "proposal": ident,
            "registered_before_change": True,
            "superseded_basis": {"recorded": "2026-11-11", "why": why,
                                 "evidence": "setup/acceptance/synthetic"},
        })

    def add_supersedes(self, replacement, supersedes, why="the first basis was wrong"):
        write_json(self.proposals / ("%s_preregistration.json" % replacement), {
            "record_kind": "EVOBOT_PROPOSAL_PREREGISTRATION",
            "proposal_id": replacement,
            "registered_before_change": True,
            "supersedes": supersedes,
            "why_the_old_proposal_was_wrong": why,
        })

    def add_overlay(self, records):
        write_json(self.proposals / "superseded.json",
                   {"schema_version": 1, "records": records})

    # -- running ---------------------------------------------------------
    def run_generate(self, *extra):
        command = [sys.executable, str(self.proposals / "generate.py"),
                   str(self.runs)] + list(extra)
        return subprocess.run(command, capture_output=True, text=True,
                              cwd=str(self.root))

    def proposal(self, ident):
        return self.proposals / ("%s.json" % ident)


class SkipCases(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="proposal-skips-")
        self.addCleanup(self.tmp.cleanup)
        self.repo = SyntheticRepo(self.tmp.name)

    # -- 1. an invalidated proposal is not generated again ---------------
    def test_invalidated_proposal_is_not_generated(self):
        self.repo.add_invalidated()
        self.repo.add_failures(STALL_DETAIL)
        proc = self.repo.run_generate()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        entries = skipped_entries(proc)
        self.assertEqual([entry["id"] for entry in entries], ["actuator_stall"])
        self.assertEqual(sorted(entries[0]), ["id", "reason", "source"])
        self.assertIn("assumed every stall was a real release failure",
                      entries[0]["reason"])
        self.assertTrue(entries[0]["source"].endswith(
            "actuator_stall_preregistration.json#superseded_basis"),
            entries[0]["source"])
        self.assertFalse(self.repo.proposal("actuator_stall").exists())
        self.assertNotIn("PROPOSAL actuator_stall", proc.stdout)

    def test_supersedes_record_also_retires_the_named_proposal(self):
        self.repo.add_supersedes("release_confirmation_over_gripper_aperture",
                                 "actuator_stall / bounded_release_retry "
                                 "(basis found wrong)")
        self.repo.add_failures(STALL_DETAIL)
        proc = self.repo.run_generate()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        entries = skipped_entries(proc)
        self.assertEqual([entry["id"] for entry in entries], ["actuator_stall"])
        self.assertIn("superseded by release_confirmation_over_gripper_aperture",
                      entries[0]["reason"])
        self.assertTrue(entries[0]["source"].endswith("#supersedes"))
        self.assertFalse(self.repo.proposal("actuator_stall").exists())

    def test_retired_kind_stops_the_signature_that_produces_it(self):
        # only the KIND is named as replaced; the signature lookup alone would miss it
        self.repo.add_supersedes("release_confirmation_over_gripper_aperture",
                                 "bounded_release_retry")
        self.repo.add_failures(STALL_DETAIL)
        proc = self.repo.run_generate()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        entries = skipped_entries(proc)
        self.assertEqual([entry["id"] for entry in entries],
                         ["bounded_release_retry"])
        self.assertFalse(self.repo.proposal("actuator_stall").exists())

    def test_overlay_can_retire_a_proposal_and_cites_its_source(self):
        self.repo.add_overlay([{
            "id": "occupied_destination",
            "status": "superseded",
            "reason": "replaced by the clearest-available-destination policy",
            "source": "docs/EXPERIMENTS.md#E-009"}])
        self.repo.add_failures(OCCUPIED_DETAIL, error_code=60, count=5)
        proc = self.repo.run_generate()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        entries = skipped_entries(proc)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["id"], "occupied_destination")
        self.assertEqual(entries[0]["source"], "docs/EXPERIMENTS.md#E-009")
        self.assertFalse(self.repo.proposal("occupied_destination").exists())

    # -- 2. a normal proposal is still generated -------------------------
    def test_normal_proposal_is_still_generated(self):
        self.repo.add_invalidated()
        self.repo.add_failures(STALL_DETAIL, count=4, prefix="stall")
        self.repo.add_failures(OCCUPIED_DETAIL, error_code=60, count=5,
                               prefix="occupied")
        proc = self.repo.run_generate()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        out = self.repo.proposal("occupied_destination")
        self.assertTrue(out.is_file(), proc.stdout)
        doc = json.loads(out.read_text(encoding="utf-8"))
        self.assertEqual(doc["signature"], "occupied_destination")
        self.assertEqual(doc["kind"], "spacing_policy")
        self.assertEqual(doc["occurrences"], 5)
        self.assertIn("PROPOSAL occupied_destination", proc.stdout)
        # the retired one is reported, the live one is written
        self.assertEqual([entry["id"] for entry in skipped_entries(proc)],
                         ["actuator_stall"])

    # -- 3. missing status must not become verified/approved -------------
    def test_absent_status_is_unknown_not_approved(self):
        self.repo.add_failures(STALL_DETAIL)
        proc = self.repo.run_generate()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(skipped_entries(proc), [])
        doc = json.loads(self.repo.proposal("actuator_stall").read_text(
            encoding="utf-8"))
        self.assertIs(doc["requires_human_approval"], True)
        for forbidden in ("verified", "approved", "status", "state"):
            self.assertNotIn(forbidden, doc)
        # the run output labels it unverified rather than verified/approved
        self.assertIn("unverified=1", proc.stdout)
        self.assertNotIn("verified=true", proc.stdout.lower())
        self.assertNotIn("approved=true", proc.stdout.lower())
        self.assertIn("approval=required", proc.stdout)

    def test_incomplete_status_record_is_refused_not_read_as_approval(self):
        self.repo.add_failures(STALL_DETAIL)
        for bad_record in ({"id": "actuator_stall", "reason": "no status given",
                            "source": "docs/notes.md"},
                           {"id": "actuator_stall", "status": "approved",
                            "reason": "wishful", "source": "docs/notes.md"}):
            self.repo.add_overlay([bad_record])
            proc = self.repo.run_generate()
            self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
            self.assertIn("proposal status registry unreadable", proc.stderr)
            self.assertIn("expected one of", proc.stderr)
            self.assertFalse(self.repo.proposal("actuator_stall").exists())

    def test_status_entries_from_the_real_repository_are_consumed(self):
        # reads the checked-out registry only; writes nothing anywhere
        spec = importlib.util.spec_from_file_location("real_generate", GENERATE)
        generate = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(generate)
        registry = generate.load_status_registry(REAL_PROPOSALS)
        entries = generate.status_of(registry, "actuator_stall")
        statuses = sorted(entry["status"] for entry in entries)
        self.assertEqual(statuses, ["invalidated", "superseded"], entries)
        self.assertTrue(any(entry["source"].endswith(
            "actuator_stall_preregistration.json#superseded_basis")
            for entry in entries))
        self.assertTrue(any(entry.get("superseded_by")
                            == "release_confirmation_over_gripper_aperture"
                            for entry in entries))
        # nothing recorded for this one: unknown, which is not approval
        self.assertEqual(generate.status_of(registry, "occupied_destination"), [])
        self.assertEqual(generate.status_of(registry, "made_up_proposal"), [])

    # -- history is preserved -------------------------------------------
    def test_existing_proposal_and_its_evidence_are_never_rewritten(self):
        existing = write_text(
            self.repo.proposal("occupied_destination"),
            '{"signature": "occupied_destination", "historical": true}\n')
        before = existing.read_bytes()
        prereg = self.repo.add_invalidated()
        prereg_before = prereg.read_bytes()
        self.repo.add_failures(OCCUPIED_DETAIL, error_code=60, count=5,
                               prefix="occupied")
        self.repo.add_failures(STALL_DETAIL)
        proc = self.repo.run_generate()
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertEqual(existing.read_bytes(), before)
        self.assertIn("KEPT", proc.stdout)
        self.assertEqual(prereg.read_bytes(), prereg_before)


if __name__ == "__main__":
    unittest.main(verbosity=2)
