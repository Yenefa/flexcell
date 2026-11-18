"""Reject new reverse dependencies while keeping historical debt explicit."""
from copy import deepcopy
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('skill_boundaries', Path(__file__).parents[1] / 'check_skill_boundaries.py')
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)


class SkillBoundariesTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.config = dict(rules=[dict(id='runtime', roots=['runtime'],
            forbidden_imports=['evolution', 'development_skills'],
            forbidden_path_parts=['evolution', 'development_skills'])], legacy_exceptions=[])
        (self.root / 'runtime').mkdir()

    def source(self, text):
        (self.root / 'runtime/client.py').write_text(text)

    def write_config(self, payload):
        config = self.root / 'config'
        config.mkdir(exist_ok=True)
        (config / 'skill_boundaries.json').write_text(json.dumps(payload))

    def run_main(self, *extra):
        out = io.StringIO()
        err = io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = module.main(['--root', str(self.root), *extra])
        return code, out.getvalue(), err.getvalue()

    def test_transport_and_local_imports_are_allowed(self):
        self.source('from flexcell_interfaces.action import ContactPush\nfrom .local import helper\n')
        self.assertTrue(module.audit(self.root, self.config)['passed'])

    def test_direct_development_import_is_rejected(self):
        self.source('from development_skills.tools import run\n')
        self.assertFalse(module.audit(self.root, self.config)['passed'])

    def test_runtime_cannot_import_the_physical_implementation(self):
        config = deepcopy(self.config)
        config['rules'][0]['forbidden_imports'] = ['flexcell_capabilities', 'flexcell_skills']
        for dependency in ['flexcell_capabilities.contact_geometry', 'flexcell_skills.contact_executor']:
            with self.subTest(dependency=dependency):
                self.source('import ' + dependency + '\n')
                self.assertFalse(module.audit(self.root, config)['passed'])

    def test_literal_dynamic_import_alias_is_rejected(self):
        self.source('from importlib import import_module as load\nload("evolution.proposals")\n')
        self.assertFalse(module.audit(self.root, self.config)['passed'])

    def test_sys_path_alias_cannot_hide_dependency(self):
        self.source('import sys as system\nsystem.path.insert(0, str(ROOT / "evolution" / "diagnosis"))\n')
        self.assertFalse(module.audit(self.root, self.config)['passed'])

    def test_sys_path_assignment_is_checked(self):
        self.source('import sys\nsys.path[:0] = ["/repo/development_skills"]\n')
        self.assertFalse(module.audit(self.root, self.config)['passed'])

    def test_literal_file_loader_is_checked(self):
        self.source('import importlib.util as loader\nloader.spec_from_file_location("x", ROOT / "evolution" / "x.py")\n')
        self.assertFalse(module.audit(self.root, self.config)['passed'])

    def test_exact_legacy_exception_cannot_cover_another_import(self):
        self.source('import evolution.diagnosis\n')
        violation = module.scan(self.root, self.config)[1][0]
        exception = {k: violation[k] for k in ('rule', 'path', 'kind', 'expression')}
        self.config['legacy_exceptions'] = [dict(exception, count=1, reason='migrate this old client')]
        self.assertTrue(module.audit(self.root, self.config)['passed'])
        self.source('import evolution.diagnosis\nimport evolution.diagnosis\n')
        self.assertFalse(module.audit(self.root, self.config)['passed'])

    def test_removed_legacy_dependency_requires_exception_cleanup(self):
        self.source('import evolution.diagnosis\n')
        violation = module.scan(self.root, self.config)[1][0]
        exception = {k: violation[k] for k in ('rule', 'path', 'kind', 'expression')}
        self.config['legacy_exceptions'] = [dict(exception, count=1, reason='old client')]
        self.source('import json\n')
        self.assertTrue(module.audit(self.root, self.config)['stale_exceptions'])

    def test_physical_core_rejects_ros_and_execution_dependencies(self):
        config = deepcopy(self.config)
        config['rules'] = [dict(id='core', roots=['runtime'],
            allowed_external_imports=['numpy', 'flexcell_capabilities'], forbid_python_path_changes=True)]
        for dependency in ['rclpy', 'flexcell_skills', 'evolution']:
            with self.subTest(dependency=dependency):
                self.source('import ' + dependency + '\n')
                self.assertFalse(module.audit(self.root, config)['passed'])
        self.source('import math\nimport numpy\nfrom .contact_geometry import ARM\n')
        self.assertTrue(module.audit(self.root, config)['passed'])

    def test_missing_source_root_fails(self):
        (self.root / 'runtime').rmdir()
        self.assertFalse(module.audit(self.root, self.config)['passed'])

    def test_parse_failure_is_not_silently_skipped(self):
        self.source('def broken(:\n')
        self.assertFalse(module.audit(self.root, self.config)['passed'])

    def test_undecodable_source_is_a_parse_error_not_a_crash(self):
        (self.root / 'runtime/client.py').write_bytes(b'import json\n# \xff\xfe\n')
        report = module.audit(self.root, self.config)
        self.assertFalse(report['passed'])
        self.assertEqual(report['violations'][0]['kind'], 'parse_error')

    def test_load_config_rejects_malformed_rules(self):
        cases = ({}, {'rules': []}, {'rules': [{}]},
                 {'rules': [{'id': 'runtime', 'roots': []}]},
                 {'rules': [{'id': 'runtime', 'roots': [1]}]},
                 {'rules': [{'id': 'runtime', 'roots': ['runtime'],
                             'forbidden_imports': 'evolution'}]},
                 {'rules': [{'id': 'runtime', 'roots': ['runtime'],
                             'forbid_python_path_changes': 'yes'}]})
        for payload in cases:
            with self.subTest(payload=payload):
                path = self.root / 'bad.json'
                path.write_text(json.dumps(payload))
                with self.assertRaises(module.UsageError):
                    module.load_config(path)

    def test_load_config_rejects_malformed_legacy_exceptions(self):
        base = dict(rules=[{'id': 'runtime', 'roots': ['runtime']}])
        cases = (dict(base, legacy_exceptions={}),
                 dict(base, legacy_exceptions=[{'rule': 'runtime', 'path': 'x',
                                                'kind': 'import', 'expression': 'y',
                                                'count': 0}]),
                 dict(base, legacy_exceptions=[{'rule': 'runtime', 'path': 'x',
                                                'kind': 'import', 'expression': 'y',
                                                'count': True}]),
                 dict(base, legacy_exceptions=[{'rule': '', 'path': 'x',
                                                'kind': 'import', 'expression': 'y',
                                                'count': 1}]))
        for payload in cases:
            with self.subTest(payload=payload):
                path = self.root / 'bad.json'
                path.write_text(json.dumps(payload))
                with self.assertRaises(module.UsageError):
                    module.load_config(path)

    def test_main_returns_2_for_bad_config(self):
        self.write_config({'rules': []})
        code, out, err = self.run_main()
        self.assertEqual((code, out), (2, ''))
        self.assertIn('rules', err)
        self.assertNotIn('Traceback', err)

    def test_main_returns_2_for_missing_config(self):
        code, _, err = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn('skill_boundaries.json', err)

    def test_main_returns_1_for_parse_error(self):
        self.write_config(self.config)
        self.source('def broken(:\n')
        code, out, err = self.run_main()
        self.assertEqual((code, err), (1, ''))
        self.assertEqual(json.loads(out)['violations'][0]['kind'], 'parse_error')

    def test_main_returns_0_for_clean_tree(self):
        self.write_config(self.config)
        self.source('import json\n')
        code, out, err = self.run_main()
        self.assertEqual((code, err), (0, ''))
        self.assertTrue(json.loads(out)['passed'])

    def test_main_returns_2_for_unwritable_out(self):
        self.write_config(self.config)
        code, _, err = self.run_main('--out', str(self.root))
        self.assertEqual(code, 2)
        self.assertIn('cannot write', err)


if __name__ == '__main__':
    unittest.main()
