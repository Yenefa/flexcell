"""Which archive does scripts/evidence_manifest.py actually check?

WHY THESE CASES EXIST (review item 9): the tool's own error message told the operator
to set FLEXCELL_EVIDENCE_ROOT, but the code never read it. The default was the bare
relative path 'setup/acceptance', so a relocated archive was silently ignored: verify
hashed the in-tree copy and reported OK for bytes nobody was asking about. The cases
below pin the resolution order - explicit --root, then FLEXCELL_EVIDENCE_ROOT, then
the in-tree checkout - for generate and verify, and reproduce the two-archives
counter-example with the archives actually differing.

Run: python scripts/tests/test_evidence_manifest.py
 or: python -m unittest discover -s scripts/tests -p 'test_evidence_manifest.py'
"""
import argparse
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'scripts' / 'evidence_manifest.py'
ENV = 'FLEXCELL_EVIDENCE_ROOT'


def load_module():
    """Load the tool by path, the way the repository invokes it as a script."""
    spec = importlib.util.spec_from_file_location('evidence_manifest_under_test',
                                                  SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def run_main(module, argv):
    """(exit code, stdout, stderr) for one invocation, without polluting the report."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


class ArchiveRootCase(unittest.TestCase):

    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='evidence-manifest-')
        self.addCleanup(temporary.cleanup)
        self.tmp = Path(temporary.name)
        self.manifest = self.tmp / 'manifest.json'
        self.module = load_module()

        # the in-tree checkout: what the tool used to hash unconditionally
        self.in_tree = self.tmp / 'in-tree'
        self.in_tree_archive = self.in_tree / 'setup' / 'acceptance'
        write(self.in_tree_archive / 'case_a' / 'run.txt', b'in-tree bytes\n')

        # the relocated evidence root: repository-root shaped, different bytes
        self.external = self.tmp / 'external'
        self.external_archive = self.external / 'setup' / 'acceptance'
        write(self.external_archive / 'case_a' / 'run.txt', b'external bytes\n')

        # the tool is imported rather than run from the checkout, so the in-tree root
        # it falls back to is replaceable without touching the repository
        self.original_repo_root = self.module.REPO_ROOT
        self.module.REPO_ROOT = self.in_tree
        self.saved_env = os.environ.get(ENV)
        self.addCleanup(self._restore)

    def _restore(self):
        self.module.REPO_ROOT = self.original_repo_root
        if self.saved_env is None:
            os.environ.pop(ENV, None)
        else:
            os.environ[ENV] = self.saved_env

    def set_env(self, value):
        if value is None:
            os.environ.pop(ENV, None)
        else:
            os.environ[ENV] = str(value)

    # -- helpers ---------------------------------------------------------
    def generate(self, root=None):
        argv = ['generate', '--out', str(self.manifest)]
        if root is not None:
            argv += ['--root', str(root)]
        return run_main(self.module, argv)

    def verify(self, root=None):
        argv = ['verify', '--manifest', str(self.manifest)]
        if root is not None:
            argv += ['--root', str(root)]
        return run_main(self.module, argv)

    def stored_manifest(self):
        return json.loads(self.manifest.read_text(encoding='utf-8'))

    # -- resolution order ------------------------------------------------
    def test_default_root_is_the_evidence_root_then_the_checkout(self):
        self.set_env(None)
        self.assertEqual(self.module.default_archive_root(),
                         self.in_tree / 'setup' / 'acceptance')
        self.set_env(self.external)
        self.assertEqual(self.module.default_archive_root(),
                         self.external / 'setup' / 'acceptance')
        # an empty variable means "not set", not "the current directory"
        self.set_env('')
        self.assertEqual(self.module.default_archive_root(),
                         self.in_tree / 'setup' / 'acceptance')

    def test_explicit_root_outranks_the_environment(self):
        self.set_env(self.external)
        explicit = argparse.Namespace(root=str(self.in_tree_archive))
        self.assertEqual(self.module.resolve_archive_root(explicit),
                         self.in_tree_archive)
        self.set_env(None)
        self.assertEqual(
            self.module.resolve_archive_root(argparse.Namespace(root=None)),
            self.in_tree / 'setup' / 'acceptance')

    # -- the counter-example: two archives, different bytes --------------
    def test_verify_checks_the_relocated_archive_not_the_in_tree_copy(self):
        # the manifest describes the in-tree copy, so an in-tree verify is a true OK
        # for that directory - which is exactly the misleading answer under test
        self.assertEqual(self.generate(root=self.in_tree_archive)[0], 0)
        code, _out, err = self.verify(root=self.in_tree_archive)
        self.assertEqual(code, 0, err)

        self.set_env(self.external)
        code, out, err = self.verify()
        self.assertEqual(code, 1, 'default verify ignored ' + ENV)
        self.assertIn('changed: case_a/run.txt', err)
        # the report names the directory it hashed, so the wrong-directory case is visible
        self.assertIn(str(self.external_archive), out)

    def test_verify_accepts_an_unchanged_relocated_archive(self):
        self.assertEqual(self.generate(root=self.external_archive)[0], 0)
        self.set_env(self.external)
        code, out, err = self.verify()
        self.assertEqual(code, 0, err)
        self.assertIn('match the manifest', out)
        self.assertIn(str(self.external_archive), out)

    def test_explicit_root_wins_over_the_environment_on_the_command_line(self):
        self.assertEqual(self.generate(root=self.in_tree_archive)[0], 0)
        self.set_env(self.external)          # the environment differs on purpose
        code, out, err = self.verify(root=self.in_tree_archive)
        self.assertEqual(code, 0, err)
        self.assertIn('match the manifest', out)

    def test_generate_reads_the_environment_default(self):
        self.set_env(self.external)
        code, _out, err = self.generate()
        self.assertEqual(code, 0, err)
        stored = self.stored_manifest()
        self.assertEqual(stored['root'], self.external_archive.as_posix())
        self.assertEqual(sorted(stored['files']), ['case_a/run.txt'])
        self.assertEqual(stored['files']['case_a/run.txt']['sha256'],
                         hashlib.sha256(b'external bytes\n').hexdigest())

    def test_missing_relocated_archive_is_an_error_not_a_pass(self):
        # a manifest that exists is not enough: if the environment points at a root
        # without setup/acceptance, that is an error rather than an empty OK
        self.assertEqual(self.generate(root=self.in_tree_archive)[0], 0)
        self.set_env(self.tmp / 'absent')
        code, _out, err = self.verify()
        self.assertEqual(code, 2)
        self.assertIn('archive root not found', err)
        self.assertIn(ENV, err)
        code, _out, err = self.generate()
        self.assertEqual(code, 2)
        self.assertIn(ENV, err)

    # -- the real CLI, not just the imported module ----------------------
    def test_cli_subprocess_reads_the_environment(self):
        self.assertEqual(self.generate(root=self.in_tree_archive)[0], 0)
        environment = dict(os.environ)
        environment[ENV] = str(self.external)
        command = [sys.executable, str(SCRIPT), 'verify',
                   '--manifest', str(self.manifest)]

        changed = subprocess.run(command, capture_output=True, text=True,
                                 env=environment)
        self.assertEqual(changed.returncode, 1, changed.stdout + changed.stderr)
        self.assertIn('changed: case_a/run.txt', changed.stderr)

        self.assertEqual(self.generate(root=self.external_archive)[0], 0)
        matching = subprocess.run(command, capture_output=True, text=True,
                                  env=environment)
        self.assertEqual(matching.returncode, 0, matching.stdout + matching.stderr)
        self.assertIn(str(self.external_archive), matching.stdout)


if __name__ == '__main__':
    unittest.main(verbosity=2)
