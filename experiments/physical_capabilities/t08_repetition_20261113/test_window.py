"""Ordinary run discovery must retain the real verdict and reject ambiguous runs."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SPEC=importlib.util.spec_from_file_location('physical_window',Path(__file__).with_name('run_window.py'))
window=importlib.util.module_from_spec(SPEC);SPEC.loader.exec_module(window)


class OrdinaryResultTest(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)

    def write(self,run,value):
        p=self.root/run/'result.json';p.parent.mkdir();p.write_text(json.dumps(value));return p

    def test_read_real_subdirectory_result(self):
        p=self.write('run-a',dict(case='normal',status='PASS'))
        value,path=window.ordinary_result(self.root,'normal')
        self.assertEqual(path,p);self.assertEqual(value['status'],'PASS')

    def test_failure_stays_failure(self):
        self.write('run-a',dict(case='normal',status='ROBOT_FAILURE'))
        value,_=window.ordinary_result(self.root,'normal')
        self.assertEqual(value['status'],'ROBOT_FAILURE')

    def test_multiple_runs_cannot_select_a_favourable_one(self):
        self.write('run-a',dict(case='normal',status='PASS'))
        self.write('run-b',dict(case='normal',status='ROBOT_FAILURE'))
        with self.assertRaises(ValueError):window.ordinary_result(self.root,'normal')

    def test_missing_run_is_not_success(self):
        with self.assertRaises(ValueError):window.ordinary_result(self.root,'normal')

    def test_wrong_task_is_not_a_regression_result(self):
        self.write('run-a',dict(case='dual_object',status='PASS'))
        with self.assertRaises(ValueError):window.ordinary_result(self.root,'normal')


if __name__=='__main__':unittest.main()
