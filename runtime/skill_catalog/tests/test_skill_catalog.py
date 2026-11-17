#!/usr/bin/env python3
"""Acceptance cases for the declaration-only skill catalog (issue #245)."""
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.skill_catalog import (CatalogError, SkillNotFound, get_skill,
                                   list_skills, load_catalog)
from runtime.skill_catalog.core import sha256_file

EXAMPLE = ROOT / "config" / "skill_catalog" / "contact_push.example.json"


def sample_skill(skill_id="skill.a"):
    return {
        "id": skill_id,
        "kind": "ROBOT_ACTION",
        "interface": "flexcell_interfaces/action/ContactPush",
        "implementation_state": "IMPLEMENTED",
        "availability": "OPT_IN",
        "default_enabled": False,
        "parameter_constraints": {"distance_m": {"const": 0.03}},
        "preconditions": ["fresh observation"],
        "limitations": ["scoped evidence"],
        "validation": {"level": "SCOPED_SIMULATION",
                       "executed_source_commit": "abc123",
                       "evidence_ref": "path/to/evidence.md"},
    }


def catalog_doc(skills=None, version="skill-catalog/1"):
    return {"schema_version": version,
            "skills": [sample_skill()] if skills is None else skills}


class SkillCatalogCase(unittest.TestCase):

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="skill-catalog-")
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name)

    def write(self, doc, name="catalog.json"):
        path = self.base / name
        path.write_text(json.dumps(doc), encoding="utf-8")
        return path

    def test_example_catalog_loads_and_lists_and_gets(self):
        catalog = load_catalog(EXAMPLE)
        skills = list_skills(catalog)
        self.assertEqual(len(skills), 1)
        skill = get_skill(catalog, "contact_push.finger_tcp.v1")
        self.assertEqual(skill["implementation_state"], "IMPLEMENTED")
        self.assertEqual(skill["availability"], "OPT_IN")
        self.assertIs(skill["default_enabled"], False)
        self.assertEqual(skill["validation"]["executed_source_commit"],
                         "31a002f6cf4980750207fc7b09def6483ccfb971")

    def test_missing_id_raises_keyerror(self):
        catalog = load_catalog(self.write(catalog_doc()))
        with self.assertRaises(KeyError):
            get_skill(catalog, "not.there")

    def test_duplicate_id_is_rejected(self):
        path = self.write(catalog_doc([sample_skill("dup"), sample_skill("dup")]))
        with self.assertRaises(CatalogError) as ctx:
            load_catalog(path)
        self.assertIn("duplicate", str(ctx.exception))

    def test_missing_field_and_bad_enums_are_rejected(self):
        broken = sample_skill()
        broken.pop("limitations")
        with self.assertRaises(CatalogError):
            load_catalog(self.write(catalog_doc([broken])))
        for field, value in (("implementation_state", "PROVEN"),
                             ("availability", "ENABLED"),
                             ("default_enabled", "false")):
            bad = sample_skill()
            bad[field] = value
            with self.assertRaises(CatalogError):
                load_catalog(self.write(catalog_doc([bad])))

    def test_unknown_version_and_broken_json_are_rejected(self):
        with self.assertRaises(CatalogError):
            load_catalog(self.write(catalog_doc(version="skill-catalog/9")))
        path = self.base / "broken.json"
        path.write_text("{not json", encoding="utf-8")
        with self.assertRaises(CatalogError):
            load_catalog(path)

    def test_nonfinite_numbers_are_rejected(self):
        path = self.base / "nan.json"
        path.write_text(json.dumps(catalog_doc()).replace("0.03", "NaN"),
                        encoding="utf-8")
        with self.assertRaises(CatalogError):
            load_catalog(path)
        huge = self.base / "inf.json"
        huge.write_text(json.dumps(catalog_doc()).replace("0.03", "1e999"),
                        encoding="utf-8")
        with self.assertRaises(CatalogError):
            load_catalog(huge)

    def test_empty_catalog_stays_empty(self):
        catalog = load_catalog(self.write(catalog_doc([])))
        self.assertEqual(list_skills(catalog), [])

    def test_states_and_unknown_sources_are_preserved(self):
        proposed = sample_skill("skill.proposed")
        proposed.update(implementation_state="PROPOSED", availability="UNKNOWN")
        proposed["validation"] = {"level": "UNKNOWN",
                                  "executed_source_commit": None,
                                  "evidence_ref": ""}
        catalog = load_catalog(self.write(catalog_doc([sample_skill(),
                                                       proposed])))
        result = get_skill(catalog, "skill.proposed")
        self.assertEqual(result["implementation_state"], "PROPOSED")
        self.assertEqual(result["availability"], "UNKNOWN")
        self.assertEqual(result["validation"]["executed_source_commit"], "UNKNOWN")
        self.assertEqual(result["validation"]["evidence_ref"], "UNKNOWN")

    def test_load_is_read_only_and_returns_detached_data(self):
        path = self.write(catalog_doc())
        before = sha256_file(path)
        catalog = load_catalog(path)
        self.assertEqual(sha256_file(path), before)
        source = copy.deepcopy(catalog)
        list_skills(catalog)[0]["default_enabled"] = True
        get_skill(catalog, "skill.a")["id"] = "mutated"
        self.assertEqual(catalog, source)

    def test_cli_exit_codes_and_json_shape(self):
        path = self.write(catalog_doc())
        cases = [
            (["list", "--catalog", str(path)], 0, "skills"),
            (["get", "--catalog", str(path), "--id", "skill.a"], 0, "skill"),
            (["get", "--catalog", str(path), "--id", "nope"], 1, "error"),
            (["list", "--catalog", str(self.base / "missing.json")], 2, "error"),
        ]
        for argv, expected_code, key in cases:
            proc = subprocess.run(
                [sys.executable, "-m", "runtime.skill_catalog"] + argv,
                cwd=str(ROOT), capture_output=True, text=True, timeout=60)
            self.assertEqual(proc.returncode, expected_code, proc.stdout + proc.stderr)
            payload = json.loads(proc.stdout)
            self.assertIn(key, payload)
            if expected_code == 0:
                self.assertIs(payload["declaration_only"], True)
            else:
                self.assertIn("reason", payload)
                self.assertNotIn("skills", payload)


if __name__ == "__main__":
    unittest.main()
