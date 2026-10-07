"""Read-only readiness gates must never authorize a batch or trust abort output."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
REPO=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('prebatch',REPO/'setup/131_prebatch_readiness.py');M=importlib.util.module_from_spec(spec);spec.loader.exec_module(M)


class ReadinessTests(unittest.TestCase):
    def health(self):return dict(ok=True,busy=False,hard_fail=[],checks=dict(task_state='IDLE',carry_engaged=False))
    def test_current_idle_health_is_only_a_readonly_prerequisite(self):
        self.assertTrue(M.confirmed_health(dict(return_code=0,stdout=json.dumps(self.health())))['ok'])
    def test_success_json_never_hides_a_signal_or_unknown_exit(self):
        for rc in [-6,134,-11,139,None,False,1]:
            with self.assertRaises(ValueError):M.confirmed_health(dict(return_code=rc,stdout=json.dumps(self.health())))
    def test_busy_carry_or_partial_health_fail_closed(self):
        for change in [dict(ok=1),dict(busy=True),dict(hard_fail=['carry']),dict(checks=dict(task_state='BUSY',carry_engaged=False)),dict(checks=dict(task_state='IDLE',carry_engaged=0))]:
            data=self.health();data.update(change)
            with self.assertRaises(ValueError):M.confirmed_health(dict(return_code=0,stdout=json.dumps(data)))
    def test_changed_or_extra_sealed_file_is_refused(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'evidence.json';p.write_text('{}')
            (root/'SHA256SUMS.json').write_text(json.dumps({'evidence.json':dict(bytes=p.stat().st_size,sha256=M.sha(p))}))
            self.assertTrue(M.verify_seal(root)['ok']);p.write_text('{"ok":true}')
            with self.assertRaises(ValueError):M.verify_seal(root)
            p.write_text('{}');(root/'extra.json').write_text('{}')
            with self.assertRaises(ValueError):M.verify_seal(root)
    def test_deployment_digest_mismatch_is_refused_before_file_reads(self):
        with self.assertRaises(ValueError):M.verify_deployment(dict(policy='hybrid',runtime_fingerprint='0'*64),REPO)
    def test_fsm_has_no_remote_backend_dependency(self):
        with patch.object(M, 'remote_probe', side_effect=AssertionError('FSM must stay local')):
            report=M.policy_probe(dict(policy='fsm'))
        self.assertTrue(report['ok']);self.assertFalse(report['model_routes_required'])
        self.assertEqual(report['model_health'],'NOT_REQUIRED_FOR_FSM')
        self.assertIsNone(report['tcp_reachable']);self.assertIsNone(report['route_eligible'])
        self.assertEqual(report['inference_calls'],0)
    def test_hybrid_keeps_the_real_remote_gate(self):
        failed=dict(ok=False,tcp_reachable=False,error='offline')
        with patch.object(M, 'remote_probe', return_value=failed) as probe:
            report=M.policy_probe(dict(policy='hybrid'))
        probe.assert_called_once_with(dict(policy='hybrid'));self.assertFalse(report['ok'])
    def test_nested_receipt_manifest_is_part_of_the_outer_seal(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);(root/'inputs').mkdir()
            inner=root/'inputs/SHA256SUMS.json';inner.write_text('{}')
            (root/'SHA256SUMS.json').write_text(json.dumps({'inputs/SHA256SUMS.json':dict(bytes=inner.stat().st_size,sha256=M.sha(inner))}))
            self.assertTrue(M.verify_seal(root)['ok']);inner.write_text('{"changed":true}')
            with self.assertRaises(ValueError):M.verify_seal(root)


if __name__=='__main__':unittest.main()
