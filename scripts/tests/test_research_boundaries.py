"""Exercise real entrypoints and recovery with research imports unavailable."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


class ResearchBoundariesTest(unittest.TestCase):
    def test_baseline_cli_dry_run_from_an_unrelated_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = subprocess.run([sys.executable, '-I', str(ROOT / 'experiments/baselines/run_baseline_b.py'),
                                     str(ROOT / 'benchmark/tasks/train/T01-train-seed1000.json'),
                                     '--out', tmp, '--dry'], cwd=tmp, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            results = list(Path(tmp).glob('*/result.json'))
            self.assertEqual(len(results), 1)
            self.assertEqual(json.loads(results[0].read_text())['tokens'], 0)

    def test_recovery_has_no_development_import_requirement(self):
        code = '''import sys, importlib.abc
sys.path.insert(0, sys.argv[1])
class BlockDevelopment(importlib.abc.MetaPathFinder):
    def find_spec(self, name, path=None, target=None):
        if name.split('.')[0] in ('evolution', 'experiments', 'pilot', 'development_skills', 'benchmark'):
            raise ImportError('development dependency: ' + name)
sys.meta_path.insert(0, BlockDevelopment())
from runtime.recovery.recover import decide, apply_respread
assert decide({'detail': 'occupied destination'})['action'] == 'respread'
plan = {'stages': [{'object_name': 'a', 'place_pose': [0.1, 0.1, 0.0175]},
                   {'object_name': 'b', 'place_pose': [0.1, 0.1, 0.0175]}]}
assert apply_respread(plan)['stages'][0]['place_pose'] != plan['stages'][0]['place_pose']
'''
        result = subprocess.run([sys.executable, '-I', '-c', code, str(ROOT)],
                                cwd='/tmp', capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_compatibility_imports_use_the_same_shared_functions(self):
        sys.path.insert(0, str(ROOT))
        from evolution.diagnosis.classify import classify
        from runtime.recovery.failure_classification import classify as runtime_classify
        from experiments.baselines.spread_destinations import spread
        from runtime.planner.spread_destinations import spread as runtime_spread
        self.assertIs(classify, runtime_classify)
        self.assertIs(spread, runtime_spread)

    def test_legacy_cli_consumes_the_planner_result_without_a_real_model_call(self):
        spec = importlib.util.spec_from_file_location('plan_cli', ROOT / 'experiments/baselines/plan_v1.py')
        cli = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cli)
        pilot = types.ModuleType('pilot')
        llm = types.ModuleType('pilot.llm')
        class FakeChat:
            def chat(self, messages):
                return dict(content=json.dumps(dict(moves=[dict(object='a', zone='z')], unmoved=[])),
                            tokens=3, seconds=0, model='stub')
            def metadata(self):
                return dict(model='stub')
        llm.Chat = FakeChat
        with tempfile.TemporaryDirectory() as tmp, patch.dict(sys.modules, {'pilot': pilot, 'pilot.llm': llm}):
            observation = Path(tmp) / 'observation.json'
            output = Path(tmp) / 'plan.json'
            observation.write_text(json.dumps(dict(instruction='move a to z', skills=['pick'],
                objects=[dict(name='a', color='red', position=[0, 0, 0])],
                zones=[dict(name='z', position=[0.1, 0, 0], radius=0.06)])))
            self.assertEqual(cli.main([str(observation), str(output)]), 0)
            self.assertEqual(json.loads(output.read_text())['usage']['tokens'], 3)


if __name__ == '__main__':
    unittest.main()
