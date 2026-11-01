#!/usr/bin/env python3
"""Replay one STOPPED diagnostic and its error decomposition; no ROS required."""
import hashlib
import importlib.util
import json
import math
from contextlib import closing
from pathlib import Path
import sqlite3
import sys
import tarfile
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
REVISION = '66cff2e650c7489aa59f8cce4ab8685dad59ae6e'
ERROR = 'contact evidence: the release boundary is not within one sampled period'


def require(condition, message):
    if not condition:
        raise ValueError('legacy release replay: ' + message)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def rows(path):
    with Path(path).open(encoding='utf-8') as stream:
        return [json.loads(line) for line in stream if line.strip()]


def one(values, detail):
    require(len(values) == 1, 'missing or ambiguous ' + detail)
    return values[0]


def load_geometry():
    path = ROOT / 'scripts/release_geometry.py'
    receipt = read(HERE / 'receipt.json')
    canonical = path.read_bytes().replace(b'\r\n', b'\n')
    require(hashlib.sha256(canonical).hexdigest() == receipt['analysis_source_sha256'], 'analysis source changed')
    spec = importlib.util.spec_from_file_location('sealed_release_geometry', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def analyze(root, geometry):
    """Only read the extracted immutable experiment and its frozen source."""
    window = read(root / 'window/window.json')
    require(window['status'] == 'STOPPED' and window['error'] == ERROR, 'original rejection changed')
    run = one(list((root / 'window/trial-01').glob('run-*')), 'physical run')
    result = read(run / 'result.json')
    require(result['status'] == 'PASS' and result['physical_tasks_dispatched'] == 1 and
            result['skill_backend'] == 'legacy' and result['backend'] == 'detachable_joint' and
            result['task']['outcome_val'] == 0 and result['task']['error_code'] == 'ERR_NONE', 'task semantics changed')
    require(result['recorder_exit'] == result['owned_launch_exit'] == 0, 'cleanup incomplete')
    a, b = read(root / 'identity-before.json'), read(root / 'identity-after.json')
    require(a == b and a['source_revision'] == REVISION and a['mismatches'] == [], 'runtime source mismatch')
    source = root / 'frozen-runtime'
    source.mkdir()
    frozen = read(root / 'frozen-source.json')
    require(frozen['revision'] == REVISION and sha(root/'runtime-source.tar') == frozen['archive_sha256'], 'runtime Git archive changed')
    with tarfile.open(root / 'runtime-source.tar') as archive:
        require(archive.pax_headers['comment'] == REVISION, 'Git archive revision mismatch')
        archive.extractall(source, filter='data')
    for relative, digest in a['source_files'].items():
        require(sha(source/relative) == digest, 'runtime source bytes changed: ' + relative)
    native_inputs = read(root/'native-compilation-inputs.json')
    require(all(any(path.endswith(name) for path in native_inputs) for name in
                ('PhysicsTrace.cc','ContactTrace.cc','DetachableCarryGuard.cc')), 'native source coverage incomplete')
    require(all(sha(source/path) == digest for path,digest in native_inputs.items()), 'native source bytes changed')
    require(all(v['source_sha256'] == v['installed_sha256'] for v in a['python_files'].values()) and
            all(v['source_sha256'] == v['installed_sha256'] for v in a['launch_files'].values()), 'imported bytes differ')
    mapped = read(run / 'runtime_native_mapping.json')
    for name in ('libflexcell_physics_trace.so','libflexcell_contact_trace.so','libflexcell_detachable_carry.so'):
        require([digest for path,digest in mapped.items() if Path(path).name == name] ==
                [a['native_libraries']['lib/'+name]], 'mapped native bytes differ')
    config = read(root / 'semantic-config.json')
    config_sha = hashlib.sha256(json.dumps(config,sort_keys=True).encode()).hexdigest()
    declaration = read(root / 'runtime-declaration.json')
    require(config_sha == result['semantic_config_sha256'] == declaration['semantic_config_sha256'], 'configuration hash mismatch')
    params = config['place_server']['ros__parameters']
    require(params['place_tolerance_m'] == .06 and params['release_clearance_m'] == .012 and params['carry_offset_m'] == .16,
            'placement geometry or tolerances changed')
    require(sha(run/'world.sdf') == result['world_sha256'] == declaration['world_sha256'], 'world changed')
    for phase in ('health_after','reset_before','reset_after'):
        require(read(run/(phase+'.stdout'))['ok'] is True, 'failed ' + phase)
    physics = rows(run/'physics_steps.jsonl')
    interval = geometry.attachment_interval(physics,'target_box_a',result['task_start_monotonic_ns'],result['task_end_monotonic_ns'])
    carry = rows(run/'skills/carry.jsonl')
    start = one([r for r in carry if r.get('event')=='start'], 'carry start')
    final = one([r for r in carry if r.get('event')=='follow_final'], 'carry final')
    require(start['session'] == final['session'] == final['follow']['session'] and
            start['object'] == final['object'] == 'target_box_a', 'carry session mismatch')
    follow = final['follow']
    sys.path[:0] = [str(source/'scripts'),str(source/'src/flexcell/flexcell_skills')]
    from joint_follow_gate import verify_run as verify_follow
    from preposition_gate import (_attachment_bounds, _pre_attach_hold, _attached_enforcement,
                                 _runtime_reference, _mean_transform, _spread, relative_pose, FROZEN)
    follow_result = verify_follow(run,'target_box_a',physics_step_ns=2_000_000)
    by_time = {r['sim_ns']:r for r in physics}
    try:
        _attachment_bounds(by_time,'target_box_a',follow['first_sim_ns'],follow['last_sim_ns'])
    except ValueError as error:
        require(str(error) == ERROR, 'a different boundary failure occurred')
    else:
        raise ValueError('original sampled-boundary rejection was not reproduced')
    first, last = interval['first_attached'], interval['last_attached']
    hold_contacts = []
    previous = None
    count = 0
    with (run/'contact_steps.jsonl').open(encoding='utf-8') as stream:
        for line in stream:
            r=json.loads(line)
            require(r['sim_ns'] in by_time and (previous is None or r['sim_ns']-previous==2_000_000), 'contact clock incomplete')
            previous=r['sim_ns']
            count+=1
            if first['sim_ns']-100_000_000 <= r['sim_ns'] <= first['sim_ns']:
                hold_contacts.append(r)
    require(count == len(physics), 'contact/physics count differs')
    # Retain all original qualification checks, including a rejection hidden by
    # the earlier sampled-release-boundary failure. Never turn either into PASS.
    hold_error = None
    try:
        _pre_attach_hold(physics,hold_contacts,'target_box_a',first['sim_ns'],FROZEN)
    except ValueError as error:
        hold_error = str(error)
    require(hold_error == 'contact evidence: the pre-attach hold is not at rest within the declared spread',
            'original 100 ms raw hold outcome changed')
    raw_hold=[r for r in physics if first['sim_ns']-100_000_000 <= r['sim_ns'] < first['sim_ns']]
    transforms=[relative_pose(r['parent_pose'],r['objects']['target_box_a']['pose']) for r in raw_hold]
    spread_m,spread_rad=_spread(transforms)
    mean=_mean_transform(transforms)
    hold=dict(status='REJECTED', original_error=hold_error, samples=len(raw_hold),
              spread_translation_m=spread_m,spread_rotation_rad=spread_rad,
              translation_limit_m=.001,rotation_limit_rad=.0015, measured_mean=mean)
    # The immediately preceding detached step is a measured diagnostic reference,
    # not an asserted stationary/qualified hold and not an attached-frame fit.
    prior=interval['before_bind']
    position,rotation=relative_pose(prior['parent_pose'],prior['objects']['target_box_a']['pose'])
    reference=position+rotation
    rigid, _ = _attached_enforcement(physics,'target_box_a',first['sim_ns'],last['sim_ns'],reference,FROZEN)
    runtime_reference = _runtime_reference(follow,reference,FROZEN)
    decoded = read(root/'tf-decoding/ros-decoded.json')
    raw_db=one(list((run/'data/raw').glob('*.db3')),'raw bag')
    with closing(sqlite3.connect(raw_db.as_uri()+'?mode=ro',uri=True)) as db:
        tf_topic = one(db.execute("SELECT id FROM topics WHERE name='/tf_static' AND type='tf2_msgs/msg/TFMessage'").fetchall(),'static TF topic')[0]
        messages=db.execute('SELECT id,data FROM messages WHERE topic_id=? ORDER BY id',(tf_topic,)).fetchall()
    require(len(messages) == len(decoded) == 1, 'ambiguous static TF messages')
    msg_id, cdr = messages[0]
    d=decoded[0]
    require(sha(raw_db)==d['bag_sha256'] and msg_id==d['message_id'] and
            hashlib.sha256(cdr).hexdigest()==d['cdr_sha256'] and
            cdr==(HERE/'tf-static-1.cdr').read_bytes(), 'raw TF provenance changed')
    transforms=geometry.decode_tf_static(cdr)
    require(transforms==d['transforms'], 'stdlib and independent ROS TF decoders disagree')
    ee=one([t['pose'] for t in transforms if t['parent']=='link5' and t['child']=='end_effector_link'], 'link5 EE transform')
    motion=one([r for r in rows(run/'skills/move_to_pose.jsonl') if r['request_id'].endswith('-descend')],'PLACE descend')
    require(motion['outcome']=='SUCCEEDED' and motion['target']['frame_id']=='world' and
            motion['orientation_enforced'] is False, 'descend motion changed')
    goal=result['goal_pose']
    expected_target=[goal[0],goal[1],goal[2]+.012+.16]
    require(motion['target']['position']==expected_target, 'recorded descend target differs from frozen formula')
    verify=one(rows(run/'skills/verify.jsonl'),'VERIFY result')
    require(verify['verified'] is True and verify['tolerance_m']==.06 and verify['expected']==goal and
            math.isclose(math.dist(verify['measured'],goal),verify['position_error_m'],abs_tol=1e-12), 'VERIFY measurement differs')
    calculation=geometry.decompose(parent=last['parent_pose'],box=last['objects']['target_box_a']['pose'],
        parent_box_reference=reference,parent_ee=ee,ee_target=motion['target']['position'],
        box_goal=goal,clearance_m=.012,settled=interval['last_task_step']['objects']['target_box_a']['pose'][:3])
    post=read(root/'postflight.json')
    require(post['running_simulation_processes']==0 and post['old_wsl_patch_unchanged'] is True, 'postflight incomplete')
    return dict(status='DIAGNOSTIC_REPLAY_COMPLETE', original_window_status='STOPPED', original_error=ERROR,
                task_status='PASS', source_revision=REVISION, window_id=window['window_id'], run=run.name,
                total_physics_steps=len(physics), contact_steps=count, follow=follow_result,
                before_bind=interval['before_bind']['sim_ns'], first_attached=first['sim_ns'], last_attached=last['sim_ns'],
                first_detached=interval['first_detached']['sim_ns'], attached_steps=interval['attached_steps'],
                sampled_last_attached=follow['last_sim_ns'], unmonitored_tail_sim_ns=last['sim_ns']-follow['last_sim_ns'],
                forensic_only=dict(hold=hold,reference_source='LAST_DETACHED_PHYSICS_STEP_NOT_QUALIFIED_HOLD',
                                   reference_sim_ns=prior['sim_ns'],reference=reference,
                                   rigid_interval=rigid,runtime_reference=runtime_reference),
                static_tf=transforms, descend_reported_ee_error_m=motion['position_error_m'],
                verify_error_m=verify['position_error_m'],
                physical_final_age_ms=(result['task_end_monotonic_ns']-interval['last_task_step']['monotonic_ns'])/1e6,
                calculation=calculation, default_admission='NO_GO', controller_changed=False,
                interpretation='The original sampled-boundary rejection remains STOPPED. Full raw-step forensic '
                               'accounting neither repairs that coverage nor qualifies D3 or the #59 CI matrix.')


def main():
    receipt=read(HERE/'receipt.json')
    archive=HERE/'raw-window.zip'
    require(sha(archive)==receipt['archive_sha256'], 'raw archive changed')
    geometry=load_geometry()
    with tempfile.TemporaryDirectory(prefix='flexcell-legacy-release-') as directory:
        root=Path(directory)
        with zipfile.ZipFile(archive) as z:
            require(len(z.namelist())==len(set(z.namelist())) and set(z.namelist())==set(receipt['members']), 'archive members changed')
            for name,digest in receipt['members'].items():
                require(not Path(name).is_absolute() and '..' not in Path(name).parts and '\\' not in name, 'unsafe archive path')
                require(hashlib.sha256(z.read(name)).hexdigest()==digest, 'archive member changed: '+name)
            z.extractall(root)
        return analyze(root,geometry)


if __name__=='__main__':
    if sys.version_info < (3, 12):
        raise SystemExit('Python 3.12+ is required for the sealed tar extraction; no simulation was started.')
    print(json.dumps(main(),indent=2,allow_nan=False))
