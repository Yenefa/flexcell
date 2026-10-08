"""Unpublished candidate staging; commitments disclose no new seed or layout.

This wraps the frozen schema-1 preparer without modifying its source or custody
template. Private local storage does not establish independent custody.
"""

from pathlib import Path
import secrets

import qualification_prepare as q

TOOL_FILES = ('setup/134_qualification_private.py',
              'setup/transferbench/qualification_private.py')
MAX_SEEDS = 20


def plain_path(path):
    path = Path(path).absolute()
    q.require('..' not in path.parts, 'parent traversal paths are not allowed')
    q.require(not any(p.is_symlink() for p in (path, *path.parents)),
              'symlink paths are not allowed')
    return path


def private_path(path, workspace):
    path = plain_path(path)
    q.require(not path.is_relative_to(workspace.resolve()),
              'private staging must be outside the workspace')
    q.require(not any((p / '.git').exists() for p in (path, *path.parents)),
              'private staging must be outside Git checkouts')
    return path


def exposures(refs, workspace):
    q.require(type(refs) is list and bool(refs), 'published exclusions required')
    result, layouts, seen = [], [], set()
    for ref in refs:
        q.require(type(ref) is dict and set(ref) == {'root', 'package_sha256'},
                  'invalid published package reference')
        q.require(type(ref['root']) is str and Path(ref['root']).is_absolute(),
                  'absolute published package path required')
        root = plain_path(ref['root'])
        q.verify(root, ref['package_sha256'], workspace=workspace)
        q.require(ref['package_sha256'] not in seen, 'duplicate published exclusion')
        seen.add(ref['package_sha256'])
        items = q.loads(q.regular(root, 'cases.json').read_bytes())
        layouts.extend(q.layout(item['initial_objects']) for item in items)
        result.append({'root': str(root), 'package_sha256': ref['package_sha256']})
    return sorted(result, key=lambda r: r['package_sha256']), layouts


def collisions(items, published):
    return sum(any(q.near(item['initial_objects'], old) for old in published)
               for item in items)


def secure_parent(path):
    missing, parent = [], path.parent
    while not parent.exists():
        missing.append(parent)
        parent = parent.parent
    for p in reversed(missing):
        p.mkdir(mode=0o700)
    q.require(path.parent.stat().st_mode & 0o777 == 0o700,
              'private parent must have permissions 0700')


def commitment(root, package_sha, refs, published, *, workspace, history_root,
               calibration_path, budget_path):
    q.verify(root, package_sha, workspace=workspace, history_root=history_root)
    history = q.loads(q.regular(root, 'history.json').read_bytes())
    identity = q.loads(q.regular(root, 'identity.json').read_bytes())
    items = q.loads(q.regular(root, 'cases.json').read_bytes())
    q.require(collisions(items, published) == 0, 'candidate overlaps published inputs')
    q.require(q.sha(calibration_path) == identity['model_identity']['calibration_sha256'],
              'current calibration differs from private snapshot')
    budget = q.loads(q.regular(root, 'budget.json').read_bytes())
    q.require(q.same_typed(q.budget_snapshot(budget_path.read_bytes()), budget),
              'current budget differs from private snapshot; never reset')
    q.require(root.stat().st_mode & 0o777 == 0o700 and
              root.parent.stat().st_mode & 0o777 == 0o700 and
              all(p.stat().st_mode & 0o777 == 0o600 for p in root.iterdir()),
              'private package permissions must be 0700/0600')
    return {'schema_version': 1, 'record_kind': 'PRIVATE_CANDIDATE_COMMITMENT',
            'status': 'PREPARED_NOT_RATIFIED', 'private_root': str(root),
            'private_package_sha256': package_sha,
            'implementation_revision': identity['implementation_revision'],
            'wrapper_source_sha256': {rel: q.sha(q.regular(workspace, rel)) for rel in TOOL_FILES},
            'identity_sha256': q.sha(root / 'identity.json'),
            'model_identity_sha256': q.digest(identity['model_identity']),
            'calibration_sha256': identity['model_identity']['calibration_sha256'],
            'proposed_runtime_fingerprints': identity['proposed_runtime_fingerprints'],
            'baseline_use': 'FROZEN_CONFIGURATION_SNAPSHOT; not current live Hybrid deployment',
            'history_sha256': q.digest(history), 'history_files': len(history['files']),
            'history_observed_states': history['observed_states'],
            'history_unique_layouts': len(history['layouts']),
            'published_exclusions': refs, 'published_layouts': len(published),
            'published_overlap_count': 0,
            'exclusion_rule': 'both object positions within 1mm; recorded history and published candidates',
            'generation_policy': 'CSPRNG; reject geometric exposure collisions before writing; at most 20 seeds; no outcome selection',
            'target_cases': len(items), 'schedule_slots': len(q.loads((root / 'schedule.json').read_bytes())),
            'storage_visibility': 'PRIVATE_UNPUBLISHED_STAGING',
            'independent_custody': 'NOT_ESTABLISHED',
            'legacy_custody_template': 'schema-1 conservative NOT_INDEPENDENT declaration retained; storage visibility stated here',
            'budget_sha256': budget['source_sha256'], 'budget_reset': False,
            'budget_envelope': 'NOT_RATIFIED', 'unrecorded_exposure': 'UNKNOWN',
            'reachability': 'NOT_EVALUATED', 'AC90': 'NOT_RUN', 'n_ge_50': 'FROZEN',
            'sampling_authorized': False, 'dispatch_authorized': False,
            'ready_for_large_test': False, 'large_tests_started': False,
            'model_calls': 0, 'native_episodes_executed': 0}


def prepare(root, public_out, refs, *, history_root, deployment_path,
            calibration_path, reference_path, budget_path, revision, workspace):
    root = private_path(root, workspace)
    public_out = plain_path(public_out)
    q.require(not root.exists() and not public_out.exists(),
              'output already exists; preserve original preparation')
    q.require(not public_out.is_relative_to(root.parent),
              'public commitment must be outside private parent')
    refs, published = exposures(refs, workspace)
    history = q.history_snapshot(history_root)
    # Validate all non-geometric inputs before creating private output.
    calibration_raw = calibration_path.read_bytes()
    deployment = q.loads(deployment_path.read_bytes())
    q.require(q.sha_bytes(calibration_raw) == deployment['active_backends']['fast']['calibration_sha256'],
              'calibration file hash mismatch')
    q.identities(deployment, revision, workspace, q.loads(calibration_raw))
    q.regressions(q.loads(reference_path.read_bytes()))
    q.budget_snapshot(budget_path.read_bytes())
    for rel in TOOL_FILES:
        q.regular(workspace, rel)
    for _ in range(MAX_SEEDS):
        seed = secrets.randbits(63)
        if collisions(q.cases(seed, history), published) == 0:
            break
    else:
        raise ValueError('published-exclusion generation exhausted; no package written')
    secure_parent(root)
    # The private parent is inaccessible to other users before q creates files.
    result = q.prepare(root, seed=seed, history_root=history_root,
                       deployment_path=deployment_path, calibration_path=calibration_path,
                       reference_path=reference_path, budget_path=budget_path,
                       revision=revision, workspace=workspace)
    root.chmod(0o700)
    for p in root.iterdir():
        p.chmod(0o600)
    value = commitment(root, result['package_sha256'], refs, published,
                       workspace=workspace, history_root=history_root,
                       calibration_path=calibration_path, budget_path=budget_path)
    public_out.parent.mkdir(parents=True, exist_ok=True)
    with public_out.open('xb') as stream:
        stream.write(q.encoded(value))
    return report(value, q.sha(public_out))


def report(value, commitment_sha):
    return {'ok': True, 'status': value['status'], 'commitment_sha256': commitment_sha,
            'private_package_sha256': value['private_package_sha256'],
            'target_cases': value['target_cases'], 'schedule_slots': value['schedule_slots'],
            'history_files': value['history_files'], 'published_layouts': value['published_layouts'],
            'published_overlap_count': 0, 'independent_custody': 'NOT_ESTABLISHED',
            'sampling_authorized': False, 'ready_for_large_test': False, 'n_ge_50': 'FROZEN',
            'model_calls': 0, 'native_episodes_executed': 0}


def verify(public_path, expected_sha, *, workspace, history_root,
           calibration_path, budget_path):
    public_path = plain_path(public_path)
    q.sha_value(expected_sha)
    q.require(q.sha(public_path) == expected_sha, 'commitment differs from expected digest')
    value = q.loads(public_path.read_bytes())
    q.require(type(value) is dict, 'commitment object required')
    root = private_path(value['private_root'], workspace)
    refs, published = exposures(value['published_exclusions'], workspace)
    expected = commitment(root, value['private_package_sha256'], refs, published,
                          workspace=workspace, history_root=history_root,
                          calibration_path=calibration_path, budget_path=budget_path)
    q.require(q.same_typed(value, expected),
              'commitment semantic mismatch; reject re-sealed gate or metadata')
    return report(value, expected_sha)
