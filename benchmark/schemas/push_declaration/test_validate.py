#!/usr/bin/env python3
"""Issue #243 regression: valid / missing / illegal / legacy-compatible declarations."""
import copy
import glob
import hashlib
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, HERE)
import validate as vd


def v2_decl():
    return {
        'declaration_version': '2.0',
        'task_id': 'T08-push-sample',
        'template_id': 'T08_push',
        'random_seed': 4102,
        'instruction': 'Push the blue block into the marked zone without picking it up.',
        'objects': [
            {'name': 'target_box_a', 'size': [0.035, 0.035, 0.035], 'color': 'red',
             'initial_pose': [0.2, -0.18, 0.0175, 0.0]},
            {'name': 'target_box_b', 'size': [0.035, 0.035, 0.035], 'color': 'blue',
             'initial_pose': [0.235, 0.025, 0.0175, 0.0]},
        ],
        'zones': [{'name': 'zone_1', 'pose': [0.105, 0.025, 0.0175], 'radius': 0.06}],
        'constraints': {'order': [], 'must_not_move': ['target_box_a']},
        'expected_goal': {
            'push': {'target_box_b': {
                'min_displacement_m': 0.03,
                'max_displacement_m': 0.15,
                'max_vertical_m': 0.02,
                'direction': [-1.0, 0.0],
                'min_direction_cosine': 0.9,
                'zone': 'zone_1',
            }},
            'unmoved': ['target_box_a'],
        },
        'evaluator_version': '0.5.0',
        'execution_budget': {'max_steps': 40, 'max_wall_s': 600.0},
        'split': 'val',
    }


def frozen_paths():
    out = []
    for pattern in ('benchmark/tasks/t08_dev/*.json',
                    'benchmark/tasks/t08_unseen/*.json',
                    'benchmark/tasks/t08_fresh_zone_20261112/T08*.json'):
        out += sorted(glob.glob(os.path.join(REPO, pattern)))
    return out


class ValidDeclarations(unittest.TestCase):
    def test_valid_v2_is_accepted(self):
        r = vd.validate(v2_decl())
        self.assertEqual(r['status'], 'VALID', r['problems'])
        self.assertEqual(r['source_format'], 'v2')
        self.assertEqual(r['declaration_version'], '2.0')
        self.assertEqual(r['problems'], [])

    def test_all_frozen_push_tasks_are_valid_legacy_v1(self):
        paths = frozen_paths()
        self.assertEqual(len(paths), 12, 'expected the 12 frozen push TaskSpecs')
        for p in paths:
            r, _ = vd.validate_file(p)
            self.assertEqual(r['status'], 'VALID', (p, r['problems']))
            self.assertEqual(r['source_format'], 'legacy_v1')

    def test_frozen_files_are_read_only(self):
        """Validating must not rewrite a frozen TaskSpec or any evidence file."""
        for p in frozen_paths():
            with open(p, 'rb') as fh:
                before = hashlib.sha256(fh.read()).hexdigest()
            vd.validate_file(p)
            with open(p, 'rb') as fh:
                after = hashlib.sha256(fh.read()).hexdigest()
            self.assertEqual(before, after, p)


class MissingFields(unittest.TestCase):
    def test_missing_required_field_is_refused(self):
        d = v2_decl()
        del d['execution_budget']
        r = vd.validate(d)
        self.assertEqual(r['status'], 'INVALID')
        self.assertTrue(any('execution_budget' in p for p in r['problems']))

    def test_missing_declaration_version_is_not_promoted_to_v2(self):
        """A missing version must NOT silently become a validated v2 declaration."""
        d = v2_decl()
        del d['declaration_version']
        r = vd.validate(d)
        self.assertEqual(r['status'], 'INVALID')
        self.assertEqual(r['source_format'], 'unknown')
        self.assertTrue(any('unrecognised' in p for p in r['problems']))

    def test_explicit_unknown_version_is_refused(self):
        d = v2_decl()
        d['declaration_version'] = '9.9'
        r = vd.validate(d)
        self.assertEqual(r['status'], 'INVALID')
        self.assertEqual(r['source_format'], 'unknown')

    def test_push_clause_missing_subfield_is_refused(self):
        d = v2_decl()
        del d['expected_goal']['push']['target_box_b']['direction']
        r = vd.validate(d)
        self.assertEqual(r['status'], 'INVALID')
        self.assertTrue(any('direction' in p for p in r['problems']))


class IllegalValues(unittest.TestCase):
    def test_legacy_template_id_is_refused_in_v2(self):
        d = v2_decl()
        d['template_id'] = 'T08_push_manipulation'
        r = vd.validate(d)
        self.assertEqual(r['status'], 'INVALID')

    def test_legacy_zone_name_is_refused_in_v2(self):
        d = v2_decl()
        d['zones'][0]['name'] = 'zone_push'
        r = vd.validate(d)
        self.assertEqual(r['status'], 'INVALID')

    def test_negative_radius_is_refused(self):
        d = v2_decl()
        d['zones'][0]['radius'] = -1.0
        r = vd.validate(d)
        self.assertEqual(r['status'], 'INVALID')

    def test_legacy_integrity_field_is_refused_in_v2(self):
        d = v2_decl()
        d['instance_sha256'] = 'deadbeef'
        r = vd.validate(d)
        self.assertEqual(r['status'], 'INVALID')
        self.assertTrue(any('additional property' in p for p in r['problems']))

    def test_bad_seed_type_is_refused(self):
        d = v2_decl()
        d['random_seed'] = True  # bool is an int in Python; must not pass as integer
        r = vd.validate(d)
        self.assertEqual(r['status'], 'INVALID')

    def test_undeclared_zone_reference_is_refused(self):
        d = v2_decl()
        d['expected_goal']['push']['target_box_b']['zone'] = 'zone_9'
        r = vd.validate(d)
        self.assertEqual(r['status'], 'INVALID')
        self.assertTrue(any('not a declared zone' in p for p in r['problems']))

    def test_min_not_less_than_max_is_refused(self):
        d = v2_decl()
        d['expected_goal']['push']['target_box_b']['min_displacement_m'] = 0.2
        r = vd.validate(d)
        self.assertEqual(r['status'], 'INVALID')


class LegacyCompatibility(unittest.TestCase):
    def _legacy(self):
        path = os.path.join(REPO, 'benchmark/tasks/t08_dev/T08-push-seed2000.json')
        with open(path, encoding='utf-8') as fh:
            return json.load(fh), path

    def test_legacy_is_labelled_not_silently_upgraded(self):
        obj, _ = self._legacy()
        r = vd.validate(obj)
        self.assertEqual(r['status'], 'VALID')
        self.assertEqual(r['source_format'], 'legacy_v1')
        self.assertEqual(r['declaration_version'], '1.0 (implicit, legacy)')
        self.assertTrue(r['compat_notes'])

    def test_legacy_split_labels_are_not_rejected(self):
        """Observed frozen splits: train, t08_fresh_20261112, t08_unseen."""
        for p in frozen_paths():
            r, _ = vd.validate_file(p)
            self.assertFalse(any('split' in x for x in r['problems']), (p, r['problems']))

    def test_v2_view_is_read_only_and_not_a_valid_v2(self):
        obj, path = self._legacy()
        with open(path, 'rb') as fh:
            before = hashlib.sha256(fh.read()).hexdigest()
        view = vd.to_v2_view(obj)
        self.assertFalse(view['is_valid_v2'])
        self.assertEqual(view['view']['declaration_version'], '2.0')
        self.assertEqual(view['view']['template_id'], 'T08_push')
        self.assertNotIn('instance_sha256', view['view'])
        self.assertIn('UNRESOLVED zone name', ' '.join(view['compat_notes']))
        # validating the view as v2 must still fail: adaptation is not validation
        self.assertEqual(vd.validate(view['view'])['status'], 'INVALID')
        with open(path, 'rb') as fh:
            after = hashlib.sha256(fh.read()).hexdigest()
        self.assertEqual(before, after)

    def test_explicit_v1_declaration_uses_v1_contract(self):
        obj, _ = self._legacy()
        obj = copy.deepcopy(obj)
        obj['declaration_version'] = '1.0'
        r = vd.validate(obj)
        self.assertEqual(r['status'], 'VALID')
        self.assertEqual(r['source_format'], 'v1')


if __name__ == '__main__':
    unittest.main(verbosity=2)
