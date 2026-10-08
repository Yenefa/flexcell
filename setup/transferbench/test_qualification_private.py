from pathlib import Path

import pytest

import qualification_prepare as q
import qualification_private as p
from test_qualification_prepare import fixture, dump


@pytest.fixture
def staged(tmp_path, fixture, monkeypatch):
    for rel in p.TOOL_FILES:
        path = fixture['workspace'] / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text('private wrapper fixture\n')
    public = tmp_path / 'published'
    old = q.prepare(public, **fixture)
    # A history addition after the published package must be included, not ignored.
    (fixture['history_root'] / 'new.json').write_bytes((fixture['history_root'] / 'old.json').read_bytes())
    refs = [{'root': str(public), 'package_sha256': old['package_sha256']}]
    kwargs = {k: v for k, v in fixture.items() if k != 'seed'}
    seeds = iter([fixture['seed'], 2026100801])
    monkeypatch.setattr(p.secrets, 'randbits', lambda bits: next(seeds))
    root, receipt = tmp_path / 'private/inputs', tmp_path / 'commitment.json'
    result = p.prepare(root, receipt, refs, **kwargs)
    check = {k: kwargs[k] for k in ('workspace', 'history_root', 'calibration_path', 'budget_path')}
    return root, receipt, result, refs, kwargs, check


def test_excludes_public_geometry_and_new_history_without_executing(staged):
    root, receipt, result, refs, kwargs, check = staged
    assert result['target_cases'] == 200 and result['schedule_slots'] == 450
    assert result['history_files'] == 2 and result['published_layouts'] == 200
    assert result['model_calls'] == result['native_episodes_executed'] == 0
    assert not result['sampling_authorized'] and result['n_ge_50'] == 'FROZEN'
    assert p.verify(receipt, result['commitment_sha256'], **check) == result
    # The first mocked seed recreated the public geometry and was rejected.
    protocol = q.loads((root / 'protocol.json').read_bytes())
    assert protocol['seed'] == 2026100801
    private = q.loads((root / 'cases.json').read_bytes())
    public = q.loads((Path(refs[0]['root']) / 'cases.json').read_bytes())
    assert p.collisions(private, [item['initial_objects'] for item in public]) == 0
    assert q.verify(root, result['private_package_sha256'], workspace=kwargs['workspace'],
                    history_root=kwargs['history_root'])['history_verified']


def test_only_commitment_disclosed_and_budget_unchanged(staged):
    root, receipt, result, refs, kwargs, check = staged
    value = q.loads(receipt.read_bytes())
    assert value['independent_custody'] == 'NOT_ESTABLISHED'
    assert value['storage_visibility'] == 'PRIVATE_UNPUBLISHED_STAGING'
    def keys(obj):
        if isinstance(obj, dict):
            return set(obj) | set().union(*(keys(v) for v in obj.values()))
        if isinstance(obj, list):
            return set().union(*(keys(v) for v in obj))
        return set()
    assert not keys(value) & {'seed', 'initial_objects', 'position', 'cases', 'request', 'plan'}
    assert value['budget_sha256'] == q.sha(kwargs['budget_path'])
    assert root.stat().st_mode & 0o777 == 0o700
    assert all(file.stat().st_mode & 0o777 == 0o600 for file in root.iterdir())


@pytest.mark.parametrize('field,value', [('sampling_authorized', True), ('model_calls', False),
                                       ('target_cases', 201), ('independent_custody', 'ESTABLISHED'),
                                       ('wrapper_source_sha256', {})])
def test_resealed_commitment_gate_or_counter_tampering_rejected(staged, field, value):
    root, receipt, result, refs, kwargs, check = staged
    changed = q.loads(receipt.read_bytes()); changed[field] = value
    receipt.write_bytes(q.encoded(changed))
    with pytest.raises(ValueError, match='expected digest'):
        p.verify(receipt, result['commitment_sha256'], **check)
    with pytest.raises(ValueError, match='semantic mismatch'):
        p.verify(receipt, q.sha(receipt), **check)


@pytest.mark.parametrize('change', ['source', 'history', 'calibration', 'budget', 'published', 'private', 'permissions'])
def test_drift_fails_closed_and_preserves_commitment(staged, change):
    root, receipt, result, refs, kwargs, check = staged
    if change == 'source':
        (kwargs['workspace'] / p.TOOL_FILES[0]).write_text('changed wrapper\n')
    elif change == 'history':
        (kwargs['history_root'] / 'late.json').write_text('{"steps": []}')
    elif change == 'calibration':
        kwargs['calibration_path'].write_text('{}')
    elif change == 'budget':
        budget = q.loads(kwargs['budget_path'].read_bytes()); budget['calls'] = []
        dump(kwargs['budget_path'], budget)
    elif change == 'published':
        (Path(refs[0]['root']) / 'cases.json').write_text('[]')
    elif change == 'private':
        (root / 'cases.json').write_text('[]')
    else:
        (root / 'protocol.json').chmod(0o644)
    with pytest.raises(ValueError):
        p.verify(receipt, result['commitment_sha256'], **check)
    assert q.sha(receipt) == result['commitment_sha256']


@pytest.mark.parametrize('existing', ['root', 'commitment'])
def test_existing_output_never_replaced(staged, tmp_path, existing):
    root, receipt, result, refs, kwargs, check = staged
    target = root if existing == 'root' else tmp_path / 'elsewhere/inputs'
    out = receipt if existing == 'commitment' else tmp_path / 'another.json'
    with pytest.raises(ValueError, match='already exists'):
        p.prepare(target, out, refs, **kwargs)
    assert q.sha(receipt) == result['commitment_sha256']
    assert q.sha(root / 'SHA256SUMS.json') == result['private_package_sha256']


@pytest.mark.parametrize('location', ['workspace', 'git_file', 'git_dir', 'symlink', 'traversal'])
def test_private_paths_cannot_enter_checkout_or_follow_symlink(tmp_path, staged, location):
    root, receipt, result, refs, kwargs, check = staged
    parent = tmp_path / 'unsafe'; parent.mkdir()
    if location == 'workspace':
        path = kwargs['workspace'] / 'new/inputs'
    elif location in ('git_file', 'git_dir'):
        if location == 'git_file': (parent / '.git').write_text('gitdir: outside\n')
        else: (parent / '.git').mkdir()
        path = parent / 'inputs'
    elif location == 'symlink':
        link = tmp_path / 'link'; link.symlink_to(parent, target_is_directory=True)
        path = link / 'inputs'
    else:
        path = parent / '..' / 'inputs'
    with pytest.raises(ValueError):
        p.prepare(path, tmp_path / 'unused.json', refs, **kwargs)
    assert not (tmp_path / 'unused.json').exists()


def test_geometric_retry_limit_writes_no_package(staged, tmp_path, monkeypatch):
    root, receipt, result, refs, kwargs, check = staged
    monkeypatch.setattr(p.secrets, 'randbits', lambda bits: 2026100701)
    newroot, out = tmp_path / 'retry/inputs', tmp_path / 'retry.json'
    with pytest.raises(ValueError, match='generation exhausted'):
        p.prepare(newroot, out, refs, **kwargs)
    assert not newroot.exists() and not out.exists()
