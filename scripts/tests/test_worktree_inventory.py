"""Inventory real Git worktrees, including dirty and missing checkouts."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location('inventory', Path(__file__).parents[1] / 'worktree_inventory.py')
inventory = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(inventory)


class WorktreeInventoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / 'base'
        self.root.mkdir()
        self.command('init', '-q', '-b', 'base')
        self.command('config', 'user.name', 'Fixture')
        self.command('config', 'user.email', 'fixture@example.invalid')
        (self.root / 'tracked').write_text('original\n')
        self.command('add', 'tracked')
        self.command('commit', '-qm', 'fixture')
        self.other = self.root.parent / 'tree with spaces'
        self.command('worktree', 'add', '-qb', 'architecture', str(self.other))
        self.config = dict(workstreams=[dict(id='architecture', branch='architecture', status='ACTIVE'),
                                        dict(id='reserved', branch='reserved', status='RESERVED')],
                           worktree_roles=[dict(branch='architecture', role='DEVELOPMENT')])

    def command(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              capture_output=True, text=True).stdout

    def write_config(self, payload, commit=False):
        path = self.root / 'config' / 'development_branches.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload))
        if commit:
            self.command('add', 'config/development_branches.json')
            self.command('commit', '-qm', 'config')
        return path

    def run_main(self, *extra):
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = inventory.main(['--root', str(self.root), *extra])
        return code, err.getvalue()

    def test_dirty_worktree_and_space_in_path_are_reported_without_mutation(self):
        (self.other / 'tracked').write_text('edit\n')
        before = self.command('worktree', 'list', '--porcelain')
        report = inventory.collect(self.root, self.config)
        row = next(t for t in report['worktrees'] if t['branch'] == 'architecture')
        self.assertEqual(row['path'], str(self.other))
        self.assertTrue(row['dirty'])
        self.assertEqual(self.command('worktree', 'list', '--porcelain'), before)
        self.assertEqual((self.other / 'tracked').read_text(), 'edit\n')

    def test_reserved_branch_is_not_invented_as_a_worktree_or_agent(self):
        row = inventory.collect(self.root, self.config)['workstreams'][1]
        self.assertEqual(row['worktrees'], [])
        self.assertIsNone(row['local_head'])
        self.assertIsNone(row['observed_origin_head'])

    def test_missing_worktree_is_reported_without_pruning_its_branch(self):
        head = inventory.revision(self.root, 'refs/heads/architecture')
        shutil.rmtree(self.other)
        row = next(t for t in inventory.collect(self.root, self.config)['worktrees']
                   if t['branch'] == 'architecture')
        self.assertFalse(row['exists'])
        self.assertIsNone(row['dirty'])
        self.assertEqual(inventory.revision(self.root, 'refs/heads/architecture'), head)

    def test_container_ownership_check_trusts_only_the_selected_checkout(self):
        with patch.dict(os.environ, {'GIT_TEST_ASSUME_DIFFERENT_OWNER': 'true',
                                    'GIT_CONFIG_COUNT': '1', 'GIT_CONFIG_KEY_0': 'safe.directory',
                                    'GIT_CONFIG_VALUE_0': ''}):
            report = inventory.collect(self.root, self.config)
        self.assertEqual(len(report['worktrees']), 2)
        self.assertTrue(all(not t['dirty'] for t in report['worktrees']))

    def test_load_config_rejects_missing_or_bad_workstreams(self):
        for payload in ({}, {'workstreams': []},
                        {'workstreams': [{'id': 'x', 'status': 'ACTIVE'}]},
                        {'workstreams': [{'id': 'x', 'branch': 1, 'status': 'ACTIVE'}]}):
            with self.subTest(payload=payload):
                path = self.write_config(payload)
                with self.assertRaises(inventory.UsageError):
                    inventory.load_config(path)

    def test_load_config_rejects_undecodable_config(self):
        path = self.root / 'config' / 'development_branches.json'
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b'\xff\xfe{}')
        with self.assertRaises(inventory.UsageError):
            inventory.load_config(path)

    def test_main_returns_2_for_invalid_config(self):
        self.write_config({'workstreams': []})
        code, err = self.run_main()
        self.assertEqual(code, 2)
        self.assertIn('workstreams', err)

    def test_main_returns_2_for_non_git_root(self):
        plain = Path(self.tmp.name) / 'plain'
        plain.mkdir()
        (plain / 'config').mkdir()
        (plain / 'config' / 'development_branches.json').write_text(json.dumps(self.config))
        with contextlib.redirect_stdout(io.StringIO()), \
                contextlib.redirect_stderr(io.StringIO()) as err:
            code = inventory.main(['--root', str(plain)])
        self.assertEqual(code, 2)
        self.assertIn('git read failed', err.getvalue())

    def test_strict_returns_0_for_clean_worktrees(self):
        self.write_config(self.config, commit=True)
        code, err = self.run_main('--strict')
        self.assertEqual((code, err), (0, ''))

    def test_strict_returns_1_but_default_returns_0_for_missing_worktree(self):
        self.write_config(self.config, commit=True)
        shutil.rmtree(self.other)
        code, err = self.run_main('--strict')
        self.assertEqual(code, 1)
        self.assertIn('missing/dirty/prunable', err)
        code, err = self.run_main()
        self.assertEqual((code, err), (0, ''))


if __name__ == '__main__':
    unittest.main()
