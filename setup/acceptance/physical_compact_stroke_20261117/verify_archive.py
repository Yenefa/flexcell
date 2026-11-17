"""Replay the fixed budget comparison from raw logs, without ROS or Gazebo."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'src/flexcell/flexcell_skills'))
from flexcell_skills.contracts.contact_task import returned_component_ready

CASE_TASK = ROOT / 'experiments/physical_capabilities/t08_compact_stroke_20261117/budget30.json'
ANCHOR_TASK = ROOT / 'benchmark/tasks/t08_dev/T08-push-seed2000.json'


def sha256(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def read(path):
    return json.loads(path.read_text())


def write(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False) + '\n')


def jsonl(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def reconstruct(case, dest, label, task, source_revision):
    spec = read(task)
    provenance = read(case / 'provenance.json')
    assert provenance['image_source_revision'] == source_revision, label
    assert sha256(task) == provenance['task_sha256'], label
    assert sha256(case / 'sim/initialized.sdf') == provenance['world_sha256'], label
    assert sha256(case / 'sim/params.yaml') == provenance['params_sha256'], label
    for source, expected in provenance['sources'].items():
        assert sha256(ROOT / source.removeprefix('/candidate/')) == expected, source
    target = next(iter(spec['expected_goal']['push']))
    protected = [obj['name'] for obj in spec['objects'] if obj['name'] != target]
    height = next(obj['initial_pose'][2] for obj in spec['objects'] if obj['name'] == target)
    links = [f'open_manipulator_x::{name}::{name}_collision'
             for name in ('link5', 'gripper_left_link', 'gripper_right_link')]
    command = [sys.executable, str(ROOT / 'benchmark/evidence/recorder.py'),
               '--physics-log', str(case / 'physics.jsonl'), '--contact-log', str(case / 'contacts.jsonl'),
               '--joint-log', str(case / 'joints.jsonl'), '--task', str(task),
               '--task-id', spec['task_id'], '--run-id', 'runtime-' + label,
               '--target', target, '--protected', *protected, '--rest-height', str(height),
               '--pusher-links', *links, '--gripper-joint', 'gripper_left_joint',
               '--out', str(dest / 'bundle.json')]
    with (dest / 'recorder.log').open('x') as log:
        subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, check=True)
    bundle = read(dest / 'bundle.json')
    recorded_bundle = read(case / 'evidence_bundle.json')
    assert bundle['manifest']['bundle_sha256'] == recorded_bundle['manifest']['bundle_sha256'], label
    before, final = [read(case / path) for path in ('gt_before.json', 'gt_after.json')]
    runtime = read(case / 'runtime/runtime_result.json')
    net = before['objects'][target][0] - final['objects'][target][0]
    final.update(evidence=bundle, agent_claimed_success=runtime['agent_claimed_success'],
                 trajectory={name: dict(max_z_m=max(s[5] for s in obj['samples']))
                             for name, obj in bundle['objects'].items() if obj['samples']})
    write(dest / 'observation.json', final)
    with (dest / 'verdict.json').open('x') as log:
        subprocess.run([sys.executable, str(ROOT / 'benchmark/evaluators/evaluate.py'), str(task),
                        str(dest / 'observation.json')], stdout=log, check=True)
    verdict = read(dest / 'verdict.json')
    recorded = read(case / 'verdict.json')
    gates = [(g['gate'], g['ok']) for g in verdict['evidence'].get('gates', [])]
    assert verdict['passed'] == recorded['passed'] and gates == [
        (g['gate'], g['ok']) for g in recorded['evidence'].get('gates', [])], label
    components = []
    for journal in sorted((case / 'sim/skills/composites').glob('*.jsonl')):
        for row in jsonl(journal):
            if row['event'] == 'NATIVE_TERMINAL' and row['component'].get('backend') == 'finger_tcp':
                components.append(row['component'])
    assert len(components) == len(list(case.glob('contact_goals/*/action_result.json'))), label
    receipts = []
    for component in components:
        folders = list(case.glob('contact_goals/' + component['request_id'] + '-*'))
        assert len(folders) == 1, component['request_id']
        folder = folders[0]
        events = jsonl(folder / 'events.jsonl')
        dispatches = Counter(e['phase'] for e in events if e['kind'] == 'CONSTRAINED_DISPATCH')
        used = sum(dispatches.values())
        action = read(folder / 'action_result.json')
        assert used == component['motion_goals_used'] == action['motion_goals_used']
        schedule = [e for e in events if e['kind'] == 'STROKE_CHECKPOINTS']
        receipts.append(dict(request_id=component['request_id'], stage_id=component['stage_id'],
                             used=used, dispatches=dict(dispatches),
                             ready=returned_component_ready(component), receipt_age_s=component.get('receipt_age_s'),
                             physical_contact_observed=component.get('physical_contact_observed'),
                             signed_displacement_m=component.get('displacement_m'),
                             checkpoints=schedule[0]['distances_m'] if len(schedule) == 1 else None,
                             goal_limit=schedule[0]['max_motion_goals'] if len(schedule) == 1 else None))
    details = dict(label=label, verdict_passed=verdict['passed'], failed_gates=[name for name, ok in gates if not ok],
                   runtime_status=runtime['status'], detail=runtime.get('detail'), net_signed_m=net,
                   motion_goals=sum(r['used'] for r in receipts), runtime_wall_s=runtime['wall_s'],
                   task_sha256=provenance['task_sha256'], world_sha256=provenance['world_sha256'], receipts=receipts)
    if label == 'CONTROL':
        details['qualified'] = (runtime['status'] == 'FAILED' and 'PushTaskRejected' in runtime.get('detail', '')
                                and 'budget' in runtime['detail'] and not receipts and not verdict['passed']
                                and not (case / 'runtime/decision.json').exists() and abs(net) <= .001)
    else:
        count, limit = (2, 13) if label == 'ANCHOR' else (3, 10)
        decision_path = case / 'runtime/decision.json'
        decision = read(decision_path) if decision_path.is_file() else {}
        observed = runtime.get('runtime_result') or {}
        details['qualified'] = (verdict['passed'] is True and len(gates) == 9 and all(ok is True for _, ok in gates)
                                and runtime['status'] == 'TASK_COMPLETED' and len(receipts) == count
                                and decision.get('capabilities', {}).get('push_motion_goal_limit') == limit
                                and observed.get('completed_stage_ids') == [r['stage_id'] for r in receipts]
                                and all(r['ready'] and r['goal_limit'] == limit and r['used'] <= limit for r in receipts)
                                and details['motion_goals'] <= spec['execution_budget']['max_steps']
                                and runtime['wall_s'] <= spec['execution_budget']['max_wall_s'])
    return details


def replay(archive, out):
    metadata = read(Path(__file__).with_name('archive.json'))
    assert archive.stat().st_size == metadata['size_bytes']
    assert sha256(archive) == metadata['sha256']
    raw = out / 'raw'
    raw.mkdir(parents=True, exist_ok=False)
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        assert len(set(names)) == len(names), 'duplicate archive filename'
        for name in names:
            assert (raw / name).resolve().is_relative_to(raw.resolve()), name
        zipped.extractall(raw)
    manifest = read(raw / 'SHA256_MANIFEST.json')
    actual = {str(p.relative_to(raw)) for p in raw.rglob('*')
              if p.is_file() and p.name != 'SHA256_MANIFEST.json'}
    assert actual == set(manifest), 'complete raw manifest required'
    for name, expected in manifest.items():
        assert sha256(raw / name) == expected, name
    executed = read(raw / 'preexecution.json')
    recorded = read(raw / 'results.json')
    assert executed['source_revision'] == recorded['source_revision'] == metadata['executed_source']
    expected_slots = [slot['id'] for slot in executed['config']['slots']]
    assert [row['label'] for row in recorded['results']] == expected_slots
    for name, expected in {**executed['sources'], **executed['freeze']['sha256'],
                          **read(raw / 'frozen_integrity.json')}.items():
        assert sha256(ROOT / name) == expected, name
    replayed = []
    for row in recorded['results']:
        label = row['label']
        case = raw / label
        if row['kind'] == 'ordinary' and row.get('status') != 'NOT_RUN':
            paths = list(case.glob('run-*/result.json'))
            assert len(paths) == 1, label
            result = read(paths[0])
            ordinary_case, placement = ('normal', ('object_at_place',)) if label == 'REG_NORMAL' else (
                'dual_object', ('object_a_at_zone', 'object_b_at_zone'))
            assert result['case'] == ordinary_case, label
            task = result.get('task') or {}
            qualified = (result['status'] == 'PASS' and result['expectation_met'] is True
                         and task.get('outcome_val') == 0 and task.get('error_code') == 'ERR_NONE'
                         and all(task.get(field) is True for field in placement))
            entry = dict(label=label, qualified=qualified, result=result)
        elif row['kind'] == 'push' and (case / 'verdict.json').is_file():
            dest = out / label
            dest.mkdir()
            entry = reconstruct(case, dest, label, ANCHOR_TASK if label == 'ANCHOR' else CASE_TASK,
                                metadata['executed_source'])
        else:
            entry = dict(label=label, qualified=False, status=row.get('status'), reason='complete evidence unavailable')
        assert entry['qualified'] == row['qualified'], label
        replayed.append(entry)
    compared = replayed[:3]
    same_case = all(len({r.get(key) for r in compared}) == 1 and all(r.get(key) for r in compared)
                    for key in ('task_sha256', 'world_sha256'))
    qualified = bool(same_case and all(r['qualified'] for r in replayed)
                     and recorded['source_unchanged'] and recorded['stop_reason'] is None)
    assert qualified == recorded['all_slots_qualified']
    output = dict(archive_sha256=metadata['sha256'], manifest_files=len(manifest), all_hashes_match=True,
                  same_task_and_world=same_case, independently_reproduced=True,
                  all_slots_qualified=qualified, physical_executions=0, slots=replayed)
    write(out / 'verification.json', output)
    print(json.dumps(dict(manifest_files=len(manifest), all_slots_qualified=qualified,
                          slots=[{k: r.get(k) for k in ('label','qualified','motion_goals','net_signed_m')} for r in replayed])))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('archive', type=Path)
    parser.add_argument('out', type=Path)
    arguments = parser.parse_args()
    replay(arguments.archive, arguments.out)
