"""Archive integrity and source compatibility are independent, including in images."""
from copy import deepcopy
import hashlib
import importlib.util
import itertools
import json
from pathlib import Path
import re
import sys

import pytest

ROOT = Path(__file__).resolve().parents[4]
CAPSULE = ROOT/'setup/acceptance/native_audit_20261031'
RECEIPT = json.loads((CAPSULE/'receipt.json').read_text())
BINDING = json.loads((CAPSULE/'source-binding.json').read_text())
SOURCES = tuple(RECEIPT['verification_sources'])
REVISION = 'a'*40


@pytest.fixture
def verifier(monkeypatch):
    spec = importlib.util.spec_from_file_location('native_audit_verify',CAPSULE/'verify.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(sys,'path',sys.path.copy())
    monkeypatch.setattr(module,'source_revision',lambda repo: REVISION)
    return module


def source_tree(directory, endings):
    # Bind transport fixtures to their own bytes, never to today's copy of an old gate.
    receipt, binding = deepcopy(RECEIPT), deepcopy(BINDING)
    receipt['patched_source_revision'] = binding['canonical_source_revision'] = REVISION
    for index, (name, crlf) in enumerate(zip(SOURCES,endings)):
        canonical = (ROOT/name).read_bytes().replace(b'\r\n',b'\n')
        binding['source_files'][name] = hashlib.sha256(canonical).hexdigest()
        recorded = canonical.replace(b'\n',b'\r\n') if index % 2 else canonical
        receipt['verification_sources'][name] = hashlib.sha256(recorded).hexdigest()
        path = directory/name
        path.parent.mkdir(parents=True,exist_ok=True)
        path.write_bytes(canonical.replace(b'\n',b'\r\n') if crlf else canonical)
    return directory, receipt, binding


@pytest.mark.parametrize('endings',list(itertools.product((False,True),repeat=4)))
def test_every_per_file_lf_crlf_combination_preserves_gate_identity(tmp_path,verifier,endings):
    tree, receipt, binding = source_tree(tmp_path,endings)
    assert verifier.verify_sources(tree,receipt,binding)['status'] == 'CURRENT_SOURCE_MATCH'


@pytest.mark.parametrize('name',SOURCES)
def test_mixed_text_line_endings_still_require_exact_canonical_content(tmp_path,verifier,name):
    tree, receipt, binding = source_tree(tmp_path,(False,)*4)
    path = tree/name
    path.write_bytes(path.read_bytes().replace(b'\n',b'\r\n',1))
    assert verifier.verify_sources(tree,receipt,binding)['status'] == 'CURRENT_SOURCE_MATCH'


@pytest.mark.parametrize('name',SOURCES)
@pytest.mark.parametrize('change',('code','bom','lone_cr'))
def test_non_transport_byte_changes_cannot_pass_at_recorded_revision(tmp_path,verifier,name,change):
    tree, receipt, binding = source_tree(tmp_path,(False,)*4)
    path = tree/name
    data = path.read_bytes()
    if change == 'code': data += b'\n# changed gate bytes\n'
    elif change == 'bom': data = b'\xef\xbb\xbf'+data
    else: data = data.replace(b'\n',b'\r',1)
    path.write_bytes(data)
    with pytest.raises(AssertionError,match='gate changed.*'+re.escape(name)):
        verifier.verify_sources(tree,receipt,binding)


@pytest.mark.parametrize('defect',('missing','extra','digest'))
def test_historical_source_observations_remain_mandatory_at_recorded_revision(tmp_path,verifier,defect):
    tree, receipt, binding = source_tree(tmp_path,(False,)*4)
    if defect == 'missing': receipt['verification_sources'].pop(SOURCES[-1])
    elif defect == 'extra': receipt['verification_sources']['scripts/other.py'] = '0'*64
    else: receipt['verification_sources'][SOURCES[0]] = '0'*64
    message = 'recorded checkout digest invalid' if defect=='digest' else 'verification source set differs'
    with pytest.raises(AssertionError,match=message):
        verifier.verify_sources(tree,receipt,binding)


def test_new_revision_reports_superseded_without_loading_current_gate(tmp_path,verifier):
    tree, _, _ = source_tree(tmp_path,(False,)*4)
    path = tree/SOURCES[0]
    path.write_bytes(b'raise RuntimeError("must not import a superseding gate")\n')
    report = verifier.verify_sources(tree,RECEIPT,BINDING)
    assert report['status'] == 'SUPERSEDED_BY_'+REVISION
    assert report['files'][SOURCES[0]]['canonical_sha256'] != BINDING['source_files'][SOURCES[0]]


@pytest.mark.parametrize('name',('receipt.json','source-binding.json','raw-evidence.zip'))
def test_superseded_revision_does_not_hide_archive_corruption(tmp_path,verifier,name):
    capsule = tmp_path/'capsule'
    capsule.mkdir()
    for member in ('receipt.json','source-binding.json'):
        (capsule/member).write_bytes((CAPSULE/member).read_bytes())
    (capsule/name).write_bytes(b'corrupted')
    with pytest.raises(AssertionError):
        verifier.verify(capsule,ROOT)


def test_superseded_still_reaches_raw_member_checks(verifier,monkeypatch):
    class RawBoundaryReached(RuntimeError):
        pass
    def boundary(*args):
        raise RawBoundaryReached()
    monkeypatch.setattr(verifier,'extract',boundary)
    with pytest.raises(RawBoundaryReached):
        verifier.verify(CAPSULE,ROOT)


@pytest.mark.parametrize('revision',('b'*40,'WORKTREE',''))
def test_gitless_image_uses_build_revision_or_explicit_unknown(tmp_path,verifier,monkeypatch,revision):
    # Import a fresh instance so this exercises the real metadata reader.
    spec = importlib.util.spec_from_file_location('gitless_verify',CAPSULE/'verify.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    monkeypatch.setenv('FLEXCELL_SOURCE_REV',revision)
    monkeypatch.setenv('PATH','')
    expected = revision if len(revision) == 40 else None
    assert module.source_revision(tmp_path) == expected
    monkeypatch.setattr(verifier,'source_revision',lambda repo: expected)
    report = verifier.verify_sources(ROOT,RECEIPT,BINDING)
    assert report['status'] == ('SUPERSEDED_BY_'+revision if expected else 'SOURCE_REVISION_UNKNOWN')
