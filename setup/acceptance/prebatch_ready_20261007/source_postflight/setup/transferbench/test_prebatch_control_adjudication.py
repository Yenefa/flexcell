"""Retained real control receipt and rejection of unsafe post-hoc corrections."""
import copy
import importlib.util
import json
from pathlib import Path
import unittest
REPO=Path(__file__).resolve().parents[2];ROOT=REPO/'setup/acceptance/prebatch_ready_20261007'
spec=importlib.util.spec_from_file_location('control_adjudicator',ROOT/'scripts/adjudicate_control.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class ControlCorrectionTests(unittest.TestCase):
    def setUp(self):
        d=ROOT/'execution/invalid-chain-control';self.command=json.loads((d/'client.json').read_text());self.events=[json.loads(s) for s in (d/'parent.jsonl').read_text().splitlines()]
        self.sizes={p.name:p.stat().st_size for p in (d/'raw').glob('*.jsonl')};self.deployment=json.loads((ROOT/'plan/deployment.json').read_text())
    def test_actual_aborted_six_zero_dispatch_does_not_rewrite_failure(self):
        r=M.audit(self.command,self.events,self.sizes,self.deployment,6)
        self.assertTrue(r['guard_condition_confirmed']);self.assertEqual(r['task_outcome'],'FAILED');self.assertEqual(self.command['return_code'],2)
    def test_signal_unknown_or_other_exit_cannot_be_corrected(self):
        for value in [-6,134,-11,139,None,0,1,False]:
            with self.assertRaises(ValueError):M.audit(dict(self.command,return_code=value),self.events,self.sizes,self.deployment,6)
    def test_any_dispatch_or_ambiguous_terminal_stops_correction(self):
        with self.assertRaises(ValueError):M.audit(self.command,self.events,dict(self.sizes,**{'controller_transport.jsonl':1}),self.deployment,6)
        events=copy.deepcopy(self.events);events[0]['outcome']=False
        with self.assertRaises(ValueError):M.audit(self.command,events,self.sizes,self.deployment,6)
    def test_wrong_action_status_or_runtime_cannot_be_corrected(self):
        with self.assertRaises(ValueError):M.audit(self.command,self.events,self.sizes,self.deployment,5)
        with self.assertRaises(ValueError):M.audit(self.command,self.events,self.sizes,dict(self.deployment,runtime_fingerprint='0'*64),6)


if __name__=='__main__':unittest.main()
