"""A schema correction cannot erase raw failures or manufacture latency."""

import copy
import json
from pathlib import Path
import unittest

import adjudicate_t1 as scorer


ROOT = Path(__file__).resolve().parents[1] / 'acceptance/transferbench_t1_20261006'


class AdjudicationTests(unittest.TestCase):
    def setUp(self):
        attempt = ROOT / 'hybrid/attempt01'
        self.episode = json.loads((attempt / 'episode.json').read_text())
        self.client = json.loads((attempt / 'client.json').read_text())
        self.summary = json.loads((attempt / 'summary.json').read_text())

    def test_real_schema_correction_preserves_original_failed_receipt(self):
        before = copy.deepcopy((self.summary, self.episode, self.client))
        self.assertEqual(scorer.corrected_outcome(self.summary, self.episode, self.client), 'SUCCEEDED')
        self.assertEqual(self.summary['outcome'], 'FAILED')
        self.assertEqual((self.summary, self.episode, self.client), before)

    def test_harness_failure_and_abort_are_retained(self):
        summary = dict(self.summary, harness_error='controller quarantined')
        self.assertEqual(scorer.corrected_outcome(summary, self.episode, self.client), 'HARNESS_ERROR')
        for code in (-6, 134, -11, 139):
            summary = dict(self.summary, command_rc=code)
            client = dict(self.client, return_code=code)
            self.assertEqual(scorer.corrected_outcome(summary, self.episode, client), 'ABORTED_PROCESS')
        episode = copy.deepcopy(self.episode)
        episode['final_state']['object_b_at_zone'] = False
        self.assertEqual(scorer.corrected_outcome(self.summary, episode, self.client), 'FAILED')

    def test_client_receipt_mismatch_is_rejected(self):
        with self.assertRaises(scorer.COST.LedgerError):
            scorer.corrected_outcome(dict(self.summary, reported_client_result={}), self.episode, self.client)

    def test_latency_rejects_integer_truncation_and_missing_clock(self):
        measured = scorer.latency([self.episode])
        self.assertEqual(measured['status'], 'MEASURED_DIAGNOSTIC')
        self.assertEqual(measured['n'], 7)
        for key, value in (('decide_latency_ms', 0), ('decide_latency_clock', None)):
            episode = copy.deepcopy(self.episode)
            episode['steps'][1][key] = value
            bad = scorer.latency([episode])
            self.assertEqual(bad['status'], 'NOT_RUN')
            self.assertEqual(bad['missing_samples'], 1)


if __name__ == '__main__':
    unittest.main()
