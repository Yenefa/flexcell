#!/usr/bin/env python3
"""Reproduce the complete first-attempt planning/contact window offline."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tempfile
import zipfile
import yaml

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT/'scripts'), str(ROOT/'src/flexcell/flexcell_skills')]
from joint_follow_gate import verify_run as follow_gate
from integrated_contact_gate import verify_run as contact_gate


def require(value, message):
    if not value: raise ValueError(message)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def verify():
    retained = Path(__file__).resolve().parent
    receipt_path = retained/'receipt.json'
    require(digest(receipt_path) == '722ad470c7dd9fd01ee8abc5834a1b59b869e086bcd066485759e7af6977766d', 'first-attempt receipt changed')
    receipt = json.loads(receipt_path.read_text())
    archive = retained/'window_8df2390.zip'
    require(digest(archive) == receipt['archive_sha256'], 'first-attempt archive changed')
    with tempfile.TemporaryDirectory(prefix='flexcell-mtc-first-') as temporary:
        root = Path(temporary)
        with zipfile.ZipFile(archive) as zipped:
            names = zipped.namelist()
            require(len(names) == len(set(names)) and set(names) == set(receipt['files_sha256']) and
                    all(not PurePosixPath(n).is_absolute() and '..' not in PurePosixPath(n).parts for n in names),
                    'first-attempt archive members changed')
            zipped.extractall(root)
        for name, sha in receipt['files_sha256'].items():
            require(digest(root/name) == sha, 'original first-attempt file changed: '+name)
        window = json.loads((root/'window.json').read_text())
        declaration = json.loads((root/'declaration.json').read_text())
        require(window['status'] == 'FUNCTIONAL_WINDOW_PASS' and window['no_replacements'] is True and
                len(window['episodes']) == 1 and declaration['qualification_no_recovery'] is True and
                digest(root/'declaration.json') == receipt['declaration_sha256'], 'window declaration/terminal changed')
        item = window['episodes'][0]; run = root/receipt['run']
        result = json.loads((run/'result.json').read_text())
        require(result == item['result'] and result['status'] == 'PASS' and result['physical_tasks_dispatched'] == 1 and
                result['task']['outcome_val'] == 0 and
                result['task']['fsm_trace'] == ['PICK_A(attempt=1):OK', 'PLACE_A:OK', 'VERIFY_A(attempt=1):OK'],
                'task did not succeed on its first pick without recovery')
        params = yaml.safe_load((run/'params.yaml').read_text())
        require(params['task_fsm_server']['ros__parameters']['recovery_budget'] == 0, 'qualification recovery enabled')
        identity = json.loads((run/'identity.stdout').read_text())
        require(identity['source_revision'] == receipt['source_revision'] and identity['mismatches'] == [] and
                identity['source_tree_sha256'] == receipt['source_tree_sha256'], 'source/install identity changed')
        loaded = json.loads((run/'loaded_runtime.json').read_text())
        require(len(loaded['planners']) == 1 and loaded['planners'][0]['sha256'] ==
                identity['native_libraries']['lib/flexcell_mtc/mtc_planner'] and any(
                'libflexcell_contact_trace' in p and h == identity['native_libraries']['lib/libflexcell_contact_trace.so']
                for p, h in loaded['libraries'].items()), 'actually loaded planner/observer differs')
        picks = [json.loads(l) for l in (run/'skills/pick.jsonl').read_text().splitlines()]
        require(len(picks) == 1 and picks[0]['outcome'] == '0' and
                'three position-only stages' in picks[0]['planning_detail'], 'unrecorded or repeated pick plan')
        health = json.loads((run/'health_after.stdout').read_text())
        require(health['ok'] is True and health['hard_fail'] == [] and len(health['checks']) == 19 and
                health['checks']['task_state'] == 'IDLE' and health['checks']['carry_engaged'] is False,
                'final health changed')
        follow = follow_gate(run,item['object'],min_duration_s=10.,physics_step_ns=2_000_000)
        contact = contact_gate(run,item['object'],declaration)
        require(follow == item['follow_evidence'] and contact == item['contact_evidence'],
                'independent motion/contact/release result differs')
        return dict(status='FIRST_ATTEMPT_EVIDENCE_REPRODUCED',source_revision=receipt['source_revision'],
                    follow=follow,contact=contact,qualification_recovery_budget=0,default_admission='NO_GO')


if __name__ == '__main__':
    print(json.dumps(verify(),indent=2,allow_nan=False))
