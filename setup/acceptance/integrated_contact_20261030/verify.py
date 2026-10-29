#!/usr/bin/env python3
"""Reproduce the preserved same-round motion/contact/release window offline."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import sys
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'scripts'), str(ROOT/'src/flexcell/flexcell_skills')]
from integrated_contact_gate import verify_run
from joint_follow_gate import verify_run as verify_follow
from export_lerobot import episode


def require(value, detail):
    if not value: raise ValueError(detail)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify(video=False):
    retained = Path(__file__).resolve().parent
    receipt_path = retained/'receipt.json'
    require(digest(receipt_path) == '5aa304225bb333e2dcfb53cd2f409c56b2d1501b13ccebea3bdd4177e904290c', 'integrated receipt changed')
    receipt = json.loads(receipt_path.read_text())
    archive = retained/'window_bba0ae3.zip'
    require(digest(archive) == receipt['archive_sha256'], 'integrated archive changed')
    with tempfile.TemporaryDirectory(prefix='flexcell-contact-audit-') as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(archive) as zipped:
            names = zipped.namelist()
            require(len(names) == len(set(names)) and set(names) == set(receipt['archived_files_sha256']) and
                    all(not PurePosixPath(name).is_absolute() and '..' not in PurePosixPath(name).parts
                        for name in names), 'integrated archive file set or paths changed')
            zipped.extractall(root)
        for relative, sha in receipt['archived_files_sha256'].items():
            require(digest(root/relative) == sha, 'archive member changed: '+relative)
        declaration = json.loads((root/'declaration.json').read_text())
        require(digest(root/'declaration.json') == receipt['declaration_sha256'], 'declaration changed')
        window = json.loads((root/'window.json').read_text())
        require(window['status'] == 'FUNCTIONAL_WINDOW_PASS' and window['no_replacements'] is True and
                len(window['episodes']) == 1 and window['runtime_fingerprint'] == receipt['runtime_fingerprint'],
                'window terminal or identity changed')
        run = root/receipt['run']; item = window['episodes'][0]
        result = json.loads((run/'result.json').read_text())
        identity = json.loads((run/'identity.stdout').read_text())
        require(result == item['result'] and result['status'] == 'PASS' and result['physical_tasks_dispatched'] == 1
                and result['task']['outcome_val'] == 0, 'task terminal changed')
        require(identity['source_revision'] == receipt['source_revision'] and identity['mismatches'] == [] and
                identity['source_tree_sha256'] == receipt['source_tree_sha256'], 'source/install identity changed')
        loaded = json.loads((run/'loaded_contact_libraries.json').read_text())
        require(any('libflexcell_contact_trace' in p and sha == identity['native_libraries']['lib/libflexcell_contact_trace.so']
                    for p, sha in loaded.items()) and any('dartsim' in p for p in loaded), 'loaded observer/engine missing')
        require(digest(run/'world.sdf') == declaration['world_sha256'] == result['world_sha256'] and
                declaration['semantic_config_sha256'] == result['semantic_config_sha256'], 'profile identity changed')
        health = json.loads((run/'health_after.stdout').read_text())
        require(health['ok'] is True and health['hard_fail'] == [] and len(health['checks']) == 19 and
                health['checks']['task_state'] == 'IDLE' and health['checks']['carry_engaged'] is False,
                'final health changed')
        follow = verify_follow(run, item['object'], min_duration_s=10., physics_step_ns=2_000_000)
        _, aligned, _ = episode(run)
        follow['camera_frames'] = len(aligned)
        require(follow == item['follow_evidence'], 'independent follow recomputation differs')
        contact = verify_run(run, item['object'], declaration)
        require(contact == item['contact_evidence'], 'independent contact/release recomputation differs')
        count = 0
        if video:
            spec = importlib.util.spec_from_file_location('follow_video_audit',
                ROOT/'setup/acceptance/joint_follow_20261029/verify_follow.py')
            module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
            metadata = json.loads((run/'data/rgb-pixels.json').read_text())
            count = module.decode_rgb(run, metadata)
            require(count == receipt['camera_frames'], 'RGB frame count changed')
            verify_follow(run,item['object'],min_duration_s=10.,physics_step_ns=2_000_000,require_camera=True)
        return dict(status='INTEGRATED_CONTACT_EVIDENCE_REPRODUCED',source_revision=receipt['source_revision'],
                    follow=follow,contact=contact,lossless_rgb_frames_checked=count,default_admission='NO_GO')


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--video',action='store_true')
    print(json.dumps(verify(parser.parse_args().video),indent=2,allow_nan=False))
