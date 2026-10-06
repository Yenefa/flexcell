"""Offline evidence-accounting regressions; never instantiate a ROS node."""

import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


CLI = Path(__file__).resolve().parents[1] / '125_transfer_cost.py'
SPEC = importlib.util.spec_from_file_location('transfer_cost', CLI)
ledger = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ledger)


class TransferCostTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(dir=os.environ.get('FLEXCELL_TEST_TMPDIR'))
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.path = self.root / 'ledger.jsonl'
        self.plan = json.loads((CLI.parent / 'transferbench/pilot_draft_v1.json').read_text())
        self.plan['record_kind'] = 'SYNTHETIC_TOOL_FIXTURE'
        ledger.initialize(self.path, self.plan)

    def evidence(self, name):
        path = self.root / (name + '.json')
        path.write_text(json.dumps({'record_kind': 'SYNTHETIC_TOOL_FIXTURE', 'id': name}))
        return [ledger.pin(path)]

    def trial(self, name='trial-1', **updates):
        event = dict(event_id=name, kind='trial', arm='hybrid', trial_id=name,
                     purpose='adaptation', case_id='T1-layout-01', runtime_fingerprint='a'*64,
                     calibration_sha256='b'*64, reported_outcome='SUCCEEDED',
                     return_code=0, evidence=self.evidence(name))
        event.update(updates)
        return event

    def start(self, name='work-1', **updates):
        event = dict(event_id=name, kind='effort_start', arm='hybrid', session_id=name,
                     actor='human', activity='fixture adaptation', clock_id='fixture-boot',
                     start_ns=100)
        event.update(updates)
        return event

    def stop(self, name='work-1', **updates):
        event = dict(event_id=name+'-stop', kind='effort_stop', arm='hybrid', session_id=name,
                     clock_id='fixture-boot', end_ns=60_000_000_100, evidence=self.evidence(name+'-stop'))
        event.update(updates)
        return event

    def report(self):
        return ledger.summarize(ledger.read_ledger(self.path))

    def reject_without_mutation(self, event):
        before = self.path.read_bytes()
        with self.assertRaises(ledger.LedgerError):
            ledger.append(self.path, event)
        self.assertEqual(self.path.read_bytes(), before)

    def test_refuses_reset_and_prospective_plan_without_manifests(self):
        before = self.path.read_bytes()
        with self.assertRaises(FileExistsError):
            ledger.initialize(self.path, self.plan)
        self.assertEqual(self.path.read_bytes(), before)
        plan = copy.deepcopy(self.plan)
        plan['record_kind'] = 'PROSPECTIVE_PLAN'
        with self.assertRaises(ledger.LedgerError):
            ledger.validate_plan(plan)

    def test_prospective_plan_requires_each_frozen_baseline_config(self):
        plan = copy.deepcopy(self.plan)
        plan['record_kind'] = 'PROSPECTIVE_PLAN'
        names = ('task_manifest', 'initial_states', 'success_predicate', 'skill_contracts',
                 'baseline_config/fsm', 'baseline_config/hybrid')
        plan['freeze_artifacts'] = {name: self.evidence(name.replace('/', '-'))[0] for name in names}
        ledger.validate_plan(plan)
        del plan['freeze_artifacts']['baseline_config/hybrid']
        with self.assertRaises(ledger.LedgerError):
            ledger.validate_plan(plan)

    def test_chain_edit_and_incomplete_tail_fail_closed(self):
        ledger.append(self.path, self.trial())
        raw = self.path.read_bytes()
        self.path.write_bytes(raw.replace(b'SUCCEEDED', b'FAILED'))
        with self.assertRaises(ledger.LedgerError):
            ledger.read_ledger(self.path)
        self.path.write_bytes(raw[:-1])
        with self.assertRaises(ledger.LedgerError):
            ledger.read_ledger(self.path)

    def test_changed_evidence_is_detected(self):
        event = self.trial()
        ledger.append(self.path, event)
        Path(event['evidence'][0]['path']).write_text('changed')
        with self.assertRaises(ledger.LedgerError):
            self.report()

    def test_failure_cannot_be_replaced_or_evidence_reused(self):
        failed = self.trial(reported_outcome='FAILED')
        ledger.append(self.path, failed)
        self.reject_without_mutation(dict(failed, reported_outcome='SUCCEEDED'))
        duplicate = self.trial('trial-2', evidence=failed['evidence'])
        self.reject_without_mutation(duplicate)
        cell = self.report()['trial_cells'][0]
        self.assertEqual(cell['outcomes'], {'FAILED': 1})

    def test_mixed_fingerprints_calibrations_arms_and_purposes_are_separate(self):
        variants = ({}, {'runtime_fingerprint': 'c'*64}, {'calibration_sha256': 'd'*64},
                    {'arm': 'fsm', 'calibration_sha256': None}, {'purpose': 'regression'})
        for i, variant in enumerate(variants):
            ledger.append(self.path, self.trial('trial-'+str(i), **variant))
        cells = self.report()['trial_cells']
        self.assertEqual(len(cells), 5)
        self.assertTrue(all(c['retained_attempts'] == 1 for c in cells))
        totals = self.report()['attempt_totals']
        self.assertEqual(sum(c['retained_attempts'] for c in totals), 5)

    def test_five_successes_do_not_certify_ac90(self):
        for i in range(5):
            ledger.append(self.path, self.trial('trial-'+str(i)))
        report = self.report()
        self.assertEqual(report['trial_cells'][0]['observed_success_rate'], 1)
        self.assertLess(report['trial_cells'][0]['diagnostic_wilson_95_lower'], 0.9)
        self.assertEqual(report['AC@90']['status'], 'NOT_RUN')
        self.assertEqual(report['decision_latency']['status'], 'NOT_RUN')

    def test_aborted_process_never_counts_as_success(self):
        for i, rc in enumerate((-6, 134)):
            ledger.append(self.path, self.trial('trial-'+str(i), return_code=rc))
        cell = self.report()['trial_cells'][0]
        self.assertEqual(cell['outcomes'], {'ABORTED_PROCESS': 2})
        self.assertEqual(cell['observed_success_rate'], 0)

    def test_harness_error_and_unknown_remain_outside_completed_denominator(self):
        ledger.append(self.path, self.trial('failure', reported_outcome='FAILED'))
        ledger.append(self.path, self.trial('harness', reported_outcome='HARNESS_ERROR', return_code=None))
        ledger.append(self.path, self.trial('unknown', reported_outcome='UNKNOWN', return_code=None))
        cell = self.report()['trial_cells'][0]
        self.assertEqual(cell['retained_attempts'], 3)
        self.assertEqual(cell['completed_denominator'], 1)
        self.assertEqual(cell['observed_success_rate'], 0)

    def test_qualification_cannot_be_enabled_or_recorded(self):
        self.reject_without_mutation(self.trial(purpose='qualification'))
        plan = copy.deepcopy(self.plan)
        plan['qualification']['status'] = 'ENABLED'
        with self.assertRaises(ledger.LedgerError):
            ledger.validate_plan(plan)

    def test_non_finite_bool_coercive_and_extra_fields_rejected(self):
        for invalid in (True, '100', -1, 1.5, float('nan'), float('inf'), 2**1000):
            with self.subTest(invalid=repr(invalid)):
                self.reject_without_mutation(self.start(start_ns=invalid))
        self.reject_without_mutation(self.trial(unrecognized_field='value'))
        for raw in ('{"x":1,"x":2}', '{"x":NaN}'):
            with self.assertRaises(ledger.LedgerError):
                ledger.decode(raw)

    def test_effort_uses_one_boot_clock_and_missing_time_is_not_zero(self):
        self.assertIsNone(self.report()['effort_minutes']['hybrid']['human'])
        ledger.append(self.path, self.start())
        self.assertEqual(len(self.report()['open_effort_sessions']), 1)
        self.reject_without_mutation(self.stop(clock_id='different-boot'))
        self.reject_without_mutation(self.stop(end_ns=99))
        self.reject_without_mutation(self.start('overlap'))
        self.reject_without_mutation(self.start('pure-wait', actor='wait'))
        ledger.append(self.path, self.stop())
        self.reject_without_mutation(self.stop())
        report = self.report()
        self.assertEqual(report['effort_minutes']['hybrid']['human'], 1)
        self.assertIsNone(report['effort_minutes']['hybrid']['coding_agent'])
        self.assertEqual(report['open_effort_sessions'], [])

    def test_start_clock_is_sampled_after_lock_and_history_validation(self):
        clock = [0]
        real_read = ledger.read_rows
        def slow_read(raw):
            clock[0] += 10_000_000_000  # simulate costly history validation, no actual sleep
            return real_read(raw)
        with patch.object(ledger, 'read_rows', side_effect=slow_read), \
             patch.object(ledger.time, 'perf_counter_ns', side_effect=lambda: clock[0]):
            ledger.append(self.path, self.start(start_ns=0), stamp_start=True)
        self.assertEqual(ledger.read_ledger(self.path)[1]['payload']['start_ns'], 10_000_000_000)

    def test_unknown_clock_gap_is_retained_and_continuation_is_possible(self):
        ledger.append(self.path, self.start())
        unknown = dict(event_id='gap', kind='effort_unknown', arm='hybrid', session_id='work-1',
                       reason='fixture reboot', evidence=self.evidence('reboot'))
        ledger.append(self.path, unknown)
        ledger.append(self.path, self.start('after-reboot', clock_id='new-boot'))
        ledger.append(self.path, self.stop('after-reboot', clock_id='new-boot'))
        report = self.report()
        self.assertEqual(report['effort_minutes']['hybrid']['human'], 1)
        self.assertEqual(report['effort_status']['hybrid']['human'], 'INCOMPLETE')
        self.assertEqual(len(report['unmeasured_effort_sessions']), 1)
        self.assertEqual(report['open_effort_sessions'], [])
        self.reject_without_mutation(self.stop())

    def test_primary_receipt_is_distinct_from_shared_support(self):
        shared = self.evidence('shared-config')
        event = self.trial()
        self.reject_without_mutation(dict(event, evidence=event['evidence'] + shared))
        # Shared config is frozen once in the plan; unique primary receipts can
        # then be recorded independently without support-file collisions.
        ledger.append(self.path, event)
        ledger.append(self.path, self.trial('independent-2'))
        self.assertEqual(self.report()['trial_cells'][0]['retained_attempts'], 2)

    def test_api_unknown_cost_remains_incomplete_and_requests_are_unique(self):
        event = dict(event_id='api-1', kind='api', arm='hybrid', request_id='req-1',
                     scope='calibration', input_tokens=100, output_tokens=20, amount=0.03,
                     currency='USD', evidence=self.evidence('api-1'))
        ledger.append(self.path, event)
        self.reject_without_mutation(dict(event, event_id='api-copy'))
        self.reject_without_mutation(dict(event, event_id='api-alias', request_id='req-alias'))
        ledger.append(self.path, dict(event, event_id='api-2', request_id='req-2',
                                     amount=None, input_tokens=None, evidence=self.evidence('api-2')))
        cell = self.report()['api_usage'][0]
        self.assertEqual(cell['requests'], 2)
        self.assertEqual(cell['known_amount_subtotal'], 0.03)
        self.assertEqual(cell['amount_status'], 'INCOMPLETE')
        self.assertEqual(cell['unknown_token_requests'], 1)

    def test_change_snapshots_are_not_summed(self):
        event = dict(event_id='diff-1', kind='change_snapshot', arm='hybrid',
                     base_revision=self.plan['baseline_revisions']['hybrid'], target_revision='b'*40,
                     code_added=10, code_deleted=2, config_added=1, config_deleted=0,
                     rules_added=None, states_added=None, evidence=self.evidence('diff-1'))
        ledger.append(self.path, event)
        ledger.append(self.path, dict(event, event_id='diff-2', code_added=12,
                                     target_revision='c'*40, evidence=self.evidence('diff-2')))
        self.assertEqual(self.report()['latest_change_snapshot']['hybrid']['code_added'], 12)
        self.reject_without_mutation(dict(event, event_id='wrong-base', base_revision='d'*40))

    def test_cli_round_trip_and_report_refuses_overwrite(self):
        spec = self.root / 'spec.json'
        spec.write_text(json.dumps(self.plan))
        path = self.root / 'cli.jsonl'
        def run(*args):
            return subprocess.run([sys.executable, str(CLI), *args, '--ledger', str(path)],
                                  capture_output=True, text=True)
        self.assertEqual(run('init', '--spec', str(spec)).returncode, 0)
        self.assertEqual(run('start', '--arm', 'hybrid', '--actor', 'coding_agent',
                             '--session', 'cli-work', '--activity', 'fixture').returncode, 0)
        evidence = self.evidence('cli-result')[0]['path']
        self.assertEqual(run('stop', '--session', 'cli-work', '--evidence', evidence).returncode, 0)
        event = self.trial('cli-trial')
        event['evidence'] = [p['path'] for p in event['evidence']]
        receipt = self.root / 'trial.json'
        receipt.write_text(json.dumps(event))
        self.assertEqual(run('record', '--event', str(receipt)).returncode, 0)
        out = self.root / 'report.json'
        self.assertEqual(run('report', '--out', str(out)).returncode, 0)
        report = json.loads(out.read_text())
        self.assertGreater(report['effort_minutes']['hybrid']['coding_agent'], 0)
        self.assertEqual(report['record_kind'], 'SYNTHETIC_TOOL_FIXTURE')
        before = out.read_bytes()
        self.assertEqual(run('report', '--out', str(out)).returncode, 2)
        self.assertEqual(out.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
