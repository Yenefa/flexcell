"""Task evidence must be complete and bound to the registered trial."""

import copy
import importlib.util
from pathlib import Path
import unittest


SPEC = importlib.util.spec_from_file_location('t1_pilot', Path(__file__).with_name('t1_pilot.py'))
pilot = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pilot)


class T1PilotTests(unittest.TestCase):
    def setUp(self):
        final = dict(outcome=0, error_code=0, goal_uuid='goal', object_a_at_zone=True,
                     object_b_at_zone=True, zone_a_error_m=0.01, zone_b_error_m=0.02)
        self.episode = dict(run_id='run', final_state=final,
                            steps=[dict(policy_output=dict(action=action, target=target),
                                        executor_result=dict(outcome=0))
                                   for target in pilot.OBJECTS for action in ('PICK', 'PLACE', 'VERIFY')])
        self.result = dict(final, run_id='run', outcome_val=0)

    def test_complete_same_goal_task_passes(self):
        self.assertTrue(pilot.success_predicate(self.episode, self.result, 0))

    def test_success_label_cannot_hide_signal_or_uuid_mismatch(self):
        for rc in (-6, 134, -11, 139, None):
            self.assertFalse(pilot.success_predicate(self.episode, self.result, rc))
        self.assertFalse(pilot.success_predicate(self.episode, dict(self.result, goal_uuid='other'), 0))
        self.assertFalse(pilot.success_predicate(self.episode, dict(self.result, run_id='other'), 0))

    def test_both_objects_need_measured_valid_verification(self):
        for value in (None, True, float('nan'), float('inf'), -0.1, 0.061):
            episode = copy.deepcopy(self.episode)
            episode['final_state']['zone_b_error_m'] = value
            self.assertFalse(pilot.success_predicate(episode, self.result, 0))
        episode = copy.deepcopy(self.episode)
        episode['steps'].pop()
        self.assertFalse(pilot.success_predicate(episode, self.result, 0))

    def test_outcomes_and_success_booleans_do_not_coerce(self):
        for value in (False, 0.0, '00', '0.0', ' 0', 'OUTCOME_SUCCEEDED', 1, None):
            episode = copy.deepcopy(self.episode)
            episode['final_state']['outcome'] = value
            self.assertFalse(pilot.success_predicate(episode, self.result, 0))
        episode = copy.deepcopy(self.episode)
        episode['final_state']['object_b_at_zone'] = 1
        self.assertFalse(pilot.success_predicate(episode, self.result, 0))

    def test_actual_serialized_episode_schema_and_client_receipt(self):
        import json
        root = Path(__file__).resolve().parents[1] / 'acceptance/transferbench_t1_20261006'
        for arm in ('fsm', 'hybrid'):
            for attempt in sorted((root / arm).glob('attempt*')):
                episode = json.loads((attempt / 'episode.json').read_text())
                client = json.loads((attempt / 'client.json').read_text())
                self.assertEqual(episode['EpisodeSchemaVersion'], 1)
                self.assertEqual(episode['final_state']['outcome'], '0')
                result = pilot.result_from_output(client['stdout'])
                self.assertTrue(pilot.success_predicate(episode, result, client['return_code']))
                for rc in (-6, 134):
                    self.assertFalse(pilot.success_predicate(episode, result, rc))
        self.assertEqual(len(list(root.glob('*/attempt*/episode.json'))), 6)

    def test_layout_binding_uses_actual_three_dimensional_position(self):
        source = copy.deepcopy(pilot.SOURCE)
        self.assertTrue(pilot.same_layout(source, pilot.SOURCE))
        source['target_box_b'][0] += 0.005
        self.assertFalse(pilot.same_layout(source, pilot.SOURCE))
        source['target_box_b'][0] = float('nan')
        self.assertFalse(pilot.same_layout(source, pilot.SOURCE))
        self.assertFalse(pilot.same_layout({}, pilot.SOURCE))

    def test_result_parser_rejects_missing_or_wrong_json_shape(self):
        self.assertEqual(pilot.result_from_output('noise\nRESULT {"run_id":"r"}\n'), {'run_id':'r'})
        for raw in ('CLIENT_TIMEOUT', 'RESULT invalid', 'RESULT []', 'RESULT null'):
            self.assertIsNone(pilot.result_from_output(raw))

    def test_new_call_cost_keeps_unknown_reservations_and_excludes_old_settlements(self):
        old = dict(calls=[dict(id='old', reserved_microyuan=10000)])
        after = dict(calls=[dict(id='old', reserved_microyuan=10000, settled_microyuan=2000),
                           dict(id='new-settled', reserved_microyuan=9000, settled_microyuan=3000),
                           dict(id='new-unknown', reserved_microyuan=8000)])
        self.assertEqual(pilot.new_call_upper_bound(old, after), 11000)


if __name__ == '__main__':
    unittest.main()
