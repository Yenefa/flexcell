"""A compatibility comparison must expose new failures and lost coverage."""
import importlib.util
from pathlib import Path
import tempfile
import unittest

SPEC = importlib.util.spec_from_file_location('comparison', Path(__file__).parents[1] / 'compare_test_reports.py')
comparison = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(comparison)


class DifferentialRegressionTest(unittest.TestCase):
    def test_shared_failure_is_explicit_and_is_not_reported_as_a_suite_pass(self):
        result = comparison.compare({'a': 'passed', 'b': 'failed'}, {'a': 'passed', 'b': 'failed'})
        self.assertTrue(result['passed'])
        self.assertEqual(result['unchanged_failures'], ['b'])
        self.assertEqual(result['qualification'], 'DIFFERENTIAL_COMPATIBILITY_ONLY')

    def test_new_failure_or_skip_is_a_regression(self):
        for state in ('failed', 'skipped'):
            with self.subTest(state=state):
                self.assertFalse(comparison.compare({'a': 'passed'}, {'a': state})['passed'])

    def test_removing_a_failing_test_cannot_make_the_comparison_pass(self):
        self.assertFalse(comparison.compare({'a': 'failed', 'b': 'passed'}, {'b': 'passed'})['passed'])

    def test_empty_and_duplicate_reports_are_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'report.xml'
            for xml in ('<testsuite/>', '<testsuite><testcase name="a"/><testcase name="a"/></testsuite>'):
                path.write_text(xml)
                with self.assertRaises(ValueError):
                    comparison.cases(path)


if __name__ == '__main__':
    unittest.main()
