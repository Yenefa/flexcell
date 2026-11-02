"""Native replay source identity survives text transport, never source edits."""
from copy import deepcopy
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import re
import sys
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[4]
CAPSULE = ROOT/'setup/acceptance/native_audit_20261031'
RECEIPT = json.loads((CAPSULE/'receipt.json').read_text())
BINDING = json.loads((CAPSULE/'source-binding.json').read_text())
SOURCES = tuple(RECEIPT['verification_sources'])


class RawBoundaryReached(RuntimeError):
    pass


@pytest.fixture
def verifier(monkeypatch):
    spec = importlib.util.spec_from_file_location('native_audit_verify',CAPSULE/'verify.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    # The test stops only after actual source and whole-archive identity checks.
    def raw_boundary(*_args):
        raise RawBoundaryReached()
    monkeypatch.setattr(module,'extract',raw_boundary)
    monkeypatch.setattr(sys,'path',sys.path.copy())
    original = module.subprocess.check_output
    def git_output(args, **kwargs):
        if args[-2:] == ['rev-parse', 'HEAD']:
            return BINDING['canonical_source_revision']+'\n'
        args = list(args); args[2] = str(ROOT)
        return original(args, **kwargs)
    monkeypatch.setattr(module.subprocess, 'check_output', git_output)
    return module


def source_tree(directory, endings):
    for name, crlf in zip(SOURCES,endings):
        canonical = subprocess.check_output(['git', '-C', str(ROOT), 'show',
            BINDING['canonical_source_revision']+':'+name]).replace(b'\r\n',b'\n')
        assert hashlib.sha256(canonical).hexdigest() == BINDING['source_files'][name]
        path = directory/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(canonical.replace(b'\n',b'\r\n') if crlf else canonical)
    return directory


@pytest.mark.parametrize('endings',list(itertools.product((False,True),repeat=4)))
def test_every_per_file_lf_crlf_combination_preserves_gate_identity(tmp_path,verifier,endings):
    tree = source_tree(tmp_path,endings)
    with pytest.raises(RawBoundaryReached):
        verifier.verify(CAPSULE,tree)


@pytest.mark.parametrize('name',SOURCES)
def test_mixed_text_line_endings_still_require_exact_canonical_content(tmp_path,verifier,name):
    tree = source_tree(tmp_path,(False,)*4)
    path = tree/name
    path.write_bytes(path.read_bytes().replace(b'\n',b'\r\n',1))
    with pytest.raises(RawBoundaryReached):
        verifier.verify(CAPSULE,tree)


@pytest.mark.parametrize('name',SOURCES)
@pytest.mark.parametrize('change',('code','bom','lone_cr'))
def test_non_transport_byte_changes_cannot_pass(tmp_path,verifier,name,change):
    tree = source_tree(tmp_path,(False,)*4)
    path = tree/name
    data = path.read_bytes()
    if change == 'code': data += b'\n# changed gate bytes\n'
    elif change == 'bom': data = b'\xef\xbb\xbf'+data
    else: data = data.replace(b'\n',b'\r',1)
    path.write_bytes(data)
    with pytest.raises(AssertionError,match='gate changed.*'+re.escape(name)):
        verifier.verify(CAPSULE,tree)


@pytest.mark.parametrize('defect',('missing','extra','digest'))
def test_historical_source_observations_remain_mandatory(tmp_path,verifier,defect):
    tree = source_tree(tmp_path/'repo',(False,)*4)
    capsule = tmp_path/'capsule'; capsule.mkdir()
    receipt = deepcopy(RECEIPT)
    if defect == 'missing': receipt['verification_sources'].pop(SOURCES[-1])
    elif defect == 'extra': receipt['verification_sources']['scripts/other.py'] = '0'*64
    else: receipt['verification_sources'][SOURCES[0]] = '0'*64
    (capsule/'receipt.json').write_text(json.dumps(receipt))
    (capsule/'source-binding.json').write_bytes((CAPSULE/'source-binding.json').read_bytes())
    message = 'recorded checkout digest invalid' if defect=='digest' else 'verification source set differs'
    with pytest.raises(AssertionError,match=message):
        verifier.verify(capsule,tree)


def test_new_revision_reports_superseded_and_still_checks_archive(tmp_path, verifier, monkeypatch):
    tree = source_tree(tmp_path, (False,)*4)
    path = tree/SOURCES[0]
    path.write_bytes(path.read_bytes()+b'\n# new implementation\n')
    original = verifier.subprocess.check_output
    def newer(args, **kwargs):
        if args[-2:] == ['rev-parse', 'HEAD']:
            return 'a'*40+'\n'
        return original(args, **kwargs)
    monkeypatch.setattr(verifier.subprocess, 'check_output', newer)
    report = verifier.verify_sources(tree, RECEIPT, BINDING)
    assert report['status'] == 'SUPERSEDED_BY_'+'a'*40
    with pytest.raises(RawBoundaryReached):
        verifier.verify(CAPSULE, tree)


def test_superseded_revision_does_not_hide_archive_corruption(tmp_path, verifier, monkeypatch):
    tree = source_tree(tmp_path/'repo', (False,)*4)
    original = verifier.subprocess.check_output
    def newer(args, **kwargs):
        if args[-2:] == ['rev-parse', 'HEAD']:
            return 'a'*40+'\n'
        return original(args, **kwargs)
    monkeypatch.setattr(verifier.subprocess, 'check_output', newer)
    capsule = tmp_path/'capsule'
    capsule.mkdir()
    for name in ('receipt.json', 'source-binding.json'):
        (capsule/name).write_bytes((CAPSULE/name).read_bytes())
    (capsule/'raw-evidence.zip').write_bytes(b'corrupt archive')
    with pytest.raises(AssertionError):
        verifier.verify(capsule, tree)
