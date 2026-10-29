#!/usr/bin/env python3
"""Recompute the retained standalone contact probe without starting simulation."""
import gzip
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'scripts'))
from contact_gate import require, verify_rows


def digest(data):
    return hashlib.sha256(data).hexdigest()


def verify():
    root = Path(__file__).resolve().parent
    manifest = root / 'inputs.json'
    require(digest(manifest.read_bytes()) == 'bc1f60d5a483cd9e86f02172ce03cdab3bef0a505b861c55ce937b7113112e94',
            'archive manifest changed')
    inputs = json.loads(manifest.read_text())
    for relative, sha in inputs['files_sha256'].items():
        path = (root / relative).resolve()
        require(path.is_relative_to(root) and path.is_file() and digest(path.read_bytes()) == sha,
                'archive input missing or changed: ' + relative)
    run = root / 'probe_3d9e9b4'
    raw = gzip.decompress((run / 'contact_steps.jsonl.gz').read_bytes())
    require(digest(raw) == inputs['decompressed_raw_sha256'] and len(raw) == inputs['decompressed_raw_bytes'],
            'lossless contact records changed')
    declaration = json.loads((run / 'declaration.json').read_text())
    result = json.loads((run / 'result.json').read_text())
    identity = json.loads((run / 'identity.stdout').read_text())
    loaded = json.loads((run / 'loaded_libraries.json').read_text())
    require(result['status'] == 'CONTACT_PIPELINE_PASS' and result['logical_robot_tasks'] == 0 and
            result['no_replacements'] is True and result['simulator_exit'] == result['owned_exit'] == 0,
            'probe terminal result changed')
    require(result['source_world_sha256'] == declaration['world_sha256'] == digest((run / 'world.sdf').read_bytes()) and
            result['declaration_sha256'] == digest((run / 'declaration.json').read_bytes()), 'declared world changed')
    require(identity['source_revision'] == inputs['source_revision'] and
            identity['source_tree_sha256'] == inputs['source_tree_sha256'] and identity['mismatches'] == [],
            'source/install identity differs')
    expected = identity['native_libraries']['lib/libflexcell_contact_trace.so']
    require(any('libflexcell_contact_trace' in path and sha == expected for path, sha in loaded.items()) and
            any('dartsim' in path for path in loaded) and any('contact-system' in path for path in loaded) and
            any('physics-system' in path for path in loaded), 'loaded observer/engine evidence missing')
    actual = verify_rows([json.loads(line) for line in raw.splitlines()], declaration)
    require(actual.keys() == result['evidence'].keys(), 'evidence schema changed')
    for key, value in result['evidence'].items():
        equal = math.isclose(actual[key], value, rel_tol=0., abs_tol=1e-12) if type(value) is float else actual[key] == value
        require(equal, 'independent contact result differs: ' + key)
    require(result['raw_sha256'] == inputs['decompressed_raw_sha256'], 'published raw hash differs')
    return dict(status='CONTACT_PIPELINE_EVIDENCE_REPRODUCED', source_revision=inputs['source_revision'],
                samples=actual['samples'], settled_force_samples=actual['settled_force_samples'],
                mean_force_magnitude_n=actual['mean_force_magnitude_n'], states=actual['states'],
                logical_robot_tasks=0, integrated_attachment_force_observed=False, default_admission='NO_GO')


if __name__ == '__main__':
    print(json.dumps(verify(), indent=2, allow_nan=False))
