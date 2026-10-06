"""Read-only audits against retained actual receipts, with corrupted copies."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import sys

REPO=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(REPO/'src/flexcell/flexcell_skills'))
ROOT=REPO/'setup/acceptance/composite_api_20261007'
spec=importlib.util.spec_from_file_location('composite_audit',REPO/'setup/127_composite_audit.py')
AUDIT=importlib.util.module_from_spec(spec);spec.loader.exec_module(AUDIT)


class CompositeAuditTests(unittest.TestCase):
    def setUp(self):
        self.events=[json.loads(x) for x in (ROOT/'execution/composite/parent.jsonl').read_text().splitlines()]
        self.deployment=json.loads((ROOT/'plan/deployment.json').read_text())
        self.directory=tempfile.TemporaryDirectory();self.addCleanup(self.directory.cleanup)
        self.path=Path(self.directory.name)/'copy.jsonl'

    def run_audit(self):
        self.path.write_text(''.join(json.dumps(e)+'\n' for e in self.events))
        return AUDIT.audit(self.path,ROOT/'execution/composite/episodes',self.deployment)

    def test_actual_precision_difference_uses_existing_episode_serialization(self):
        c=next(e['component'] for e in self.events if e['event']=='NATIVE_TERMINAL')
        self.assertNotEqual(c['final_state']['final_position_error_m'],round(c['final_state']['final_position_error_m'],9))
        report=self.run_audit();self.assertTrue(report['ok']);self.assertEqual(report['observations'],7)

    def test_changed_uuid_rejected(self):
        next(e for e in self.events if e['event']=='STARTED')['component_goal_uuid']='wrong'
        with self.assertRaises(ValueError):self.run_audit()

    def test_false_terminal_is_not_success(self):
        self.events[-1]['outcome']=False
        with self.assertRaises(ValueError):self.run_audit()

    def test_missing_joint_final_observation_rejected(self):
        del self.events[-2]
        for seq,e in enumerate(self.events):e['seq']=seq
        with self.assertRaises(ValueError):self.run_audit()

    def test_changed_full_precision_native_error_not_hidden_by_rounding(self):
        c=next(e['component'] for e in self.events if e['event']=='NATIVE_TERMINAL')
        c['final_state']['final_position_error_m']=.06000000001;c['final_position_error_m']=.06000000001
        with self.assertRaises(ValueError):self.run_audit()

    def test_source_snapshot_cannot_be_replaced_with_measured_nan(self):
        e=next(e for e in self.events if e['event']=='OBSERVATION')
        e['observation']['objects'][0]['position'][0]=float('nan')
        with self.assertRaises(ValueError):self.run_audit()


if __name__=='__main__':unittest.main()
