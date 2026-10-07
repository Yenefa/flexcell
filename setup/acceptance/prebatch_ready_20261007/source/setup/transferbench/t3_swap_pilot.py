#!/usr/bin/env python3
"""One registered buffer-assisted swap per arm, plus one source regression.

The common outer executor owns the dependency chain; models route native tasks.
Native episodes stay separate. A composite receipt is not an EpisodeSchema record.
"""

import argparse
from collections import Counter
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import sys
import time
import uuid

import t1_pilot as base


REPO, COST, LOGS, RUNTIME = base.REPO, base.COST, base.LOGS, base.RUNTIME
OBJECTS = base.OBJECTS
CLIENT = REPO / 'src/flexcell/flexcell_skills/test/w1_client.py'
BUFFER = [0.12, -0.15, 0.0175]
STAGES = [('buffer-B', OBJECTS[1], BUFFER),
          ('relocate-A', OBJECTS[0], base.SOURCE[OBJECTS[1]]),
          ('return-B', OBJECTS[1], base.SOURCE[OBJECTS[0]])]


def load(path):
    return COST.decode(Path(path).read_text())


def point(value):
    return (type(value) is list and len(value) == 3
            and all(type(x) in (int, float) and math.isfinite(x) for x in value))


def observed_positions(result):
    if not result or type(result.get('outcome_val')) is not int or result['outcome_val'] != 0:
        return None
    carry = result.get('carry') or {}
    if carry.get('engaged') is not False or carry.get('object_id'):
        return None
    objects = result.get('objects') or []
    if len({o.get('name') for o in objects}) != len(objects):
        return None
    positions = {o['name']: o.get('position') for o in objects if o.get('available') is True}
    if not all(name in positions and point(positions[name]) for name in OBJECTS):
        return None
    return {name: positions[name] for name in OBJECTS}


def matches(positions, expected, tolerance=.06):
    return bool(positions and all(point(expected[name]) and
                math.dist(positions[name], expected[name]) <= tolerance for name in OBJECTS))


def vacant(positions, destination, moving=None, clearance=.05):
    return bool(positions and point(destination) and all(math.dist(xyz, destination) > clearance
                for name, xyz in positions.items() if name != moving))


def single_pass(episode, result, rc, target):
    if not episode or not result or rc is None or base.signal_return_code(rc):
        return False
    final = episode.get('final_state') or {}
    if not ((type(final.get('outcome')) is str and final['outcome'] == '0')
            or (type(final.get('outcome')) is int and final['outcome'] == 0)):
        return False
    if type(final.get('error_code')) is not int or final['error_code'] != 0:
        return False
    if type(result.get('outcome_val')) is not int or result['outcome_val'] != 0:
        return False
    if not final.get('goal_uuid') or final['goal_uuid'] != result.get('goal_uuid') or not episode.get('run_id'):
        return False
    for item in (final, result):
        error = item.get('final_position_error_m')
        if item.get('object_at_place') is not True or type(error) not in (int, float) or not math.isfinite(error) or not 0 <= error <= .06:
            return False
    if result.get('skip_verify') is not False:
        return False
    for step in episode.get('steps', []):
        if step['policy_input']['goal']['assignments'] != [[target, 'task_place']]:
            return False
    return all(any(step['policy_output']['action'] == action and step['policy_output']['target'] == target
                   and type((step.get('executor_result') or {}).get('outcome')) is int
                   and step['executor_result']['outcome'] == 0 for step in episode.get('steps', []))
               for action in ('PICK', 'PLACE', 'VERIFY'))


def composite_pass(components, final_result):
    expected = {OBJECTS[0]: base.SOURCE[OBJECTS[1]], OBJECTS[1]: base.SOURCE[OBJECTS[0]]}
    return (len(components) == 3 and [c['stage_id'] for c in components] == [s[0] for s in STAGES]
            and len({c['run_id'] for c in components}) == 3
            and all(c['outcome'] == 'SUCCEEDED' and not c['harness_error'] for c in components)
            and matches(observed_positions(final_result), expected)
            and vacant(observed_positions(final_result), BUFFER))


def observe(directory, name):
    command = base.command(directory, name, [sys.executable, str(CLIENT), '--action', 'observe'], 40)
    result = base.result_from_output(command['stdout'])
    ok = command['return_code'] is not None and not base.signal_return_code(command['return_code']) and observed_positions(result) is not None
    return command, result, ok


def prepare(directory, arm, label):
    reset = base.command(directory, 'reset', [sys.executable, str(REPO / 'setup/flexcell_admin.py'), 'reset'], 300)
    try:
        ok = reset['return_code'] is not None and not base.signal_return_code(reset['return_code']) and COST.decode(reset['stdout'])['ok'] is True
    except (ValueError, KeyError, TypeError):
        ok = False
    if not ok:
        return 'reset did not confirm JSON ok:true without signal'
    clear = base.command(directory, 'clear-injection', [sys.executable, str(CLIENT), '--action', 'inject',
                         '--inject', '', '--inject-request-id', arm+'-t3-'+label, '--expect-inject-state', 'cleared'], 30)
    return None if clear['return_code'] == 0 else 'injection clear unconfirmed'


def usage(root, arm, directory, episode, before, after, purpose):
    out = directory / 'usage'
    out.mkdir()
    old = {c['id'] for c in before['calls']}
    for call in after['calls']:
        if call['id'] in old:
            continue
        receipt = out / ('slow-' + call['id'] + '.json')
        base.write(receipt, dict(record_kind='OBSERVED_BUDGET_RECEIPT', call=call, invoice='UNKNOWN; peak uncached ceiling only'))
        COST.append(root/'cost.jsonl', dict(event_id=arm+'-slow-'+call['id'], kind='api', arm=arm,
                    request_id=call['id'], scope='adaptation' if purpose == 'adaptation' else 'evaluation',
                    input_tokens=call.get('prompt_tokens'), output_tokens=call.get('completion_tokens'),
                    amount=None, currency='CNY', evidence=[COST.pin(receipt)]))
    for step in (episode or {}).get('steps', []):
        for index, proposal in enumerate((step['policy_output'].get('policy_trace') or {}).get('proposals', [])):
            if proposal.get('policy') != 'jev' or proposal.get('skipped'):
                continue
            name = 'fast-%s-%d-%d' % (episode['run_id'], step['seq'], index)
            receipt = out / (name + '.json')
            base.write(receipt, dict(record_kind='OBSERVED_POLICY_PROPOSAL', run_id=episode['run_id'], seq=step['seq'],
                                    proposal=proposal, invoice='UNKNOWN; input/output token split unavailable'))
            COST.append(root/'cost.jsonl', dict(event_id=name, kind='api', arm=arm, request_id=name,
                        scope='adaptation' if purpose == 'adaptation' else 'evaluation', input_tokens=None,
                        output_tokens=None, amount=None, currency='CNY', evidence=[COST.pin(receipt)]))


def native(root, arm, directory, deployment, case, target=None, destination=None):
    from flexcell_skills.contracts.routing_audit import audit_routing_episode
    from flexcell_skills.contracts.episode import replay_episode
    from flexcell_skills.decision_policy import FSMPolicy
    directory.mkdir()
    purpose = 'regression' if target is None else 'adaptation'
    before = base.budget_snapshot()
    base.write(directory/'budget_before.json', before)
    offsets = {p.name:p.stat().st_size for p in LOGS.glob('*.jsonl')}
    base.write(directory/'offsets.json', offsets)
    old_files = set((LOGS/'episodes').glob('*.json'))
    args = [sys.executable, str(CLIENT), '--action', 'task', '--object', target, '--pose', *map(str, destination)] if target else [sys.executable, str(CLIENT), '--action', 'demo', '--scenario', 'week1_demo_v1']
    client = base.command(directory, 'client', args, 220)
    result = base.result_from_output(client['stdout'])
    episode, audit, harness = None, None, None
    if not result or client['return_code'] is None or base.signal_return_code(client['return_code']):
        harness = 'native terminal result unconfirmed or signal exit'
    if result:
        candidates = [(p,load(p)) for p in set((LOGS/'episodes').glob('*.json')) - old_files]
        candidates = [(p,e) for p,e in candidates if (e.get('final_state') or {}).get('goal_uuid') == result.get('goal_uuid')]
        if len(candidates) == 1:
            original, episode = candidates[0]
            shutil.copyfile(original, directory/'episode.json')
        else:
            harness = 'expected one episode for native goal UUID'
    if episode:
        if episode['runtime_fingerprint'] != deployment['runtime_fingerprint']:
            harness = 'native fingerprint mismatch'
        if arm == 'hybrid':
            audit = audit_routing_episode(episode, deployment)
            if not audit['ok']:
                harness = 'hybrid routing audit failed'
        else:
            replay = replay_episode(episode, FSMPolicy())
            audit = dict(replay_status='PASS' if replay and all(r['ok'] for r in replay) else 'FAIL', replayed_steps=len(replay))
            if audit['replay_status'] != 'PASS':
                harness = 'FSM replay failed'
        if any((s.get('executor_result') or {}).get('outcome') is None for s in episode['steps']):
            harness = 'unknown skill terminal result'
    passed = single_pass(episode, result, client['return_code'], target) if target else base.success_predicate(episode, result, client['return_code'])
    after = base.budget_snapshot()
    base.write(directory/'budget_after.json', after)
    usage(root, arm, directory, episode, before, after, purpose)
    raw = directory/'raw'
    raw.mkdir()
    for p in LOGS.glob('*.jsonl'):
        if p.stat().st_size < offsets.get(p.name, 0):
            raise ValueError('runtime log truncated')
        (raw/p.name).write_bytes(p.read_bytes()[offsets.get(p.name, 0):])
    for p in raw.glob('*transport.jsonl'):
        if any('quarantin' in str(COST.decode(line).get('event','')) or COST.decode(line).get('event') in ('goal_send_timeout','goal_response_unknown','goal_response_error')
               for line in p.read_text().splitlines() if line.strip()):
            harness = 'unknown/quarantined transport ownership'
    summary = dict(record_kind='ACTUAL_NATIVE_TASK' if episode else 'HARNESS_ATTEMPT', arm=arm,
                   stage_id=case, purpose=purpose, target=target, destination=destination,
                   run_id=episode.get('run_id') if episode else None,
                   outcome='HARNESS_ERROR' if harness else 'SUCCEEDED' if passed else 'FAILED',
                   harness_error=harness, command_rc=client['return_code'], reported_client_result=result,
                   runtime_fingerprint=deployment['runtime_fingerprint'], audit=audit,
                   raw_evidence=[COST.pin(directory/'client.json')]+([COST.pin(directory/'episode.json')] if episode else []))
    base.write(directory/'summary.json', summary)
    COST.append(root/'cost.jsonl', dict(event_id=arm+'-'+case+'-trial',kind='trial',arm=arm,
                trial_id=summary['run_id'] or arm+'-'+case+'-harness',purpose=purpose,case_id=case,
                runtime_fingerprint=deployment['runtime_fingerprint'],calibration_sha256=deployment['active_backends']['fast']['calibration_sha256'] if arm=='hybrid' else None,
                reported_outcome=summary['outcome'],return_code=client['return_code'],evidence=[COST.pin(directory/'summary.json')]))
    print(json.dumps(dict(arm=arm, case=case, outcome=summary['outcome'], run_id=summary['run_id'], audit=audit)),flush=True)
    return summary


def register(root, deployment_path, baseline_revision, executor_revision, development):
    deployment = load(deployment_path)
    base.verify_deployment(deployment)
    COST.require(deployment['policy']=='hybrid' and deployment['threshold']==.85
                 and deployment.get('startup_health_timeout_s')==10, 'expected configured hybrid starting point')
    budget = base.budget_snapshot()
    COST.require(budget['limit_microyuan']==5_000_000,'existing budget must not be reset')
    root.mkdir()
    plan_dir=root/'plan';plan_dir.mkdir()
    artifacts={}
    def freeze(name, data):
        p=plan_dir/(name.replace('/','_')+'.json');base.write(p,data);artifacts[name]=str(p)
    stages=[dict(id=s[0],target=s[1],destination=s[2],depends_on=None if i==0 else STAGES[i-1][0]) for i,s in enumerate(STAGES)]
    freeze('initial_states',dict(source=base.SOURCE,buffer=BUFFER,stages=stages,final={OBJECTS[0]:base.SOURCE[OBJECTS[1]],OBJECTS[1]:base.SOURCE[OBJECTS[0]]}))
    freeze('success_predicate',dict(version=1,native='same goal UUID; typed success; verified finite error <=.06m; PICK/PLACE/VERIFY per native task; no signal exit',
          composite='B buffer -> A B-source -> B A-source; all three distinct native episodes succeed; final fresh Observe jointly matches both swapped positions <=.06m and buffer clear >.05m; carry disengaged',
          source_sha256=base.sha(Path(__file__))))
    freeze('skill_contracts',dict(source_sha256=deployment['source_sha256'],installed_source_sha256=deployment['installed_source_sha256'],interfaces=deployment['interface_sources_sha256']))
    expected={}
    for arm in ('fsm','hybrid'):
        data=base.profile(deployment);data['policy']=arm
        expected[arm]=hashlib.sha256(json.dumps(data,sort_keys=True).encode()).hexdigest()
        freeze('baseline_config/'+arm,dict(data,runtime_fingerprint=expected[arm]))
    manifest=dict(protocol_id='flexcell-transferbench-t3-swap-v1',migration_axis='T3',arms=['fsm','hybrid'],order='FSM then Hybrid, fixed',
                  composite_attempts_per_arm=1,components_per_composite=3,source_regression_per_arm=1,total_max_native_episodes=8,
                  stages=stages,expected_fingerprints=expected,baseline_revision=baseline_revision,shared_executor_revision=executor_revision,
                  shared_executor_sha256=base.sha(Path(__file__)),ledger_sha256=base.sha(REPO/'setup/125_transfer_cost.py'),
                  no_failure_replacement=True,qualification='FROZEN',additional_paid_stop_threshold_cny=.25,
                  admission='require confirmed reset, cleared injection, measured expected initial state and vacant destination; stop globally on unknown/quarantined goal, signal, identity or routing failure; ordinary task failure ends composite then one source regression',
                  adaptation='fixed common outer chain; no model/prompt/calibration tuning; models route within native tasks, not cross-stage planning',
                  cost='shared new executor code is engineering work, reported once; not zero-cost migration; human minutes and early planning not measured',
                  n_ge_50='FROZEN')
    freeze('task_manifest',manifest);freeze('registration_budget',budget);freeze('shared_development',load(development))
    spec=dict(schema_version=1,protocol_id=manifest['protocol_id'],record_kind='PROSPECTIVE_PLAN',migration_axis='T3',arms=manifest['arms'],
              cases=[s[0] for s in STAGES]+['S1-source-regression','T3-orchestration-check'],baseline_revisions={a:baseline_revision for a in manifest['arms']},
              qualification=dict(status='FROZEN',target_success_rate=.9),freeze_artifacts=artifacts)
    base.write(plan_dir/'spec.json',spec)
    COST.initialize(root/'cost.jsonl',dict(spec,freeze_artifacts={name:COST.pin(p) for name,p in artifacts.items()}))
    print(json.dumps(dict(status='REGISTERED',root=str(root),expected_fingerprints=expected)),flush=True)


def run_arm(root, arm):
    rows=COST.read_ledger(root/'cost.jsonl');manifest=load(root/'plan/task_manifest.json');registration_budget=load(root/'plan/registration_budget.json')
    COST.require(base.sha(Path(__file__))==manifest['shared_executor_sha256'] and base.sha(REPO/'setup/125_transfer_cost.py')==manifest['ledger_sha256'],'registered executor changed')
    if arm=='hybrid':
        previous=load(root/'fsm/status.json');COST.require(previous['stop_reason'] is None,'FSM ownership/identity failure stopped the whole pilot')
    directory=root/arm;directory.mkdir()
    COST.append(root/'cost.jsonl',dict(event_id=arm+'-start',kind='effort_start',arm=arm,session_id=arm+'-orchestration',actor='coding_agent',
                activity='bounded composite and source regression orchestration elapsed',clock_id=COST.clock_id(),start_ns=0),stamp_start=True)
    before=set(RUNTIME.iterdir());switch=base.command(directory,'switch',['bash',str(REPO/'setup/102_mainline_runtime.sh'),'switch',arm,'0.85'],150)
    created=set(RUNTIME.iterdir())-before
    COST.require(switch['return_code']==0 and len(created)==1,'activation failed; retain open session and stop')
    runtime=created.pop();deployment=load(runtime/'deployment.json');base.verify_deployment(deployment)
    COST.require(deployment['runtime_fingerprint']==manifest['expected_fingerprints'][arm],'activation profile mismatch')
    shutil.copyfile(runtime/'deployment.json',directory/'deployment.json')
    composite_dir=directory/'composite';composite_dir.mkdir()
    composite_id='t3-swap-'+arm+'-'+uuid.uuid4().hex[:8]
    base.write(composite_dir/'admission.json',dict(composite_id=composite_id,max_attempts=1))
    stop=prepare(composite_dir,arm,'target');components=[];expected=dict(base.SOURCE);final_result=None;failure=stop
    if not stop:
        for stage_id,target,destination in STAGES:
            if base.new_call_upper_bound(registration_budget,base.budget_snapshot())>=250000:
                stop=failure='additional paid upper-bound stop threshold';break
            _,result,ok=observe(composite_dir,'pre-'+stage_id)
            if not ok:
                stop=failure='pre-stage Observe unconfirmed';break
            positions=observed_positions(result)
            if not matches(positions,expected) or not vacant(positions,destination,target):
                failure='measured precondition failed before '+stage_id;break
            component=native(root,arm,composite_dir/stage_id,deployment,stage_id,target,destination);components.append(component)
            if component['harness_error']:
                stop=failure=component['harness_error'];break
            if component['outcome']!='SUCCEEDED':
                failure='native task failed at '+stage_id;break
            expected[target]=destination
            _,final_result,ok=observe(composite_dir,'post-'+stage_id)
            if not ok:
                stop=failure='post-stage Observe unconfirmed';break
            if not matches(observed_positions(final_result),expected):
                failure='measured postcondition failed at '+stage_id;break
    success=composite_pass(components,final_result) and not failure
    if not success and failure is None:
        failure='final joint swap/buffer predicate failed'
    composite=dict(record_kind='ACTUAL_COMPOSITE_TASK',composite_id=composite_id,arm=arm,runtime_fingerprint=deployment['runtime_fingerprint'],
                   outcome='HARNESS_ERROR' if stop else 'SUCCEEDED' if success else 'FAILED',failure=failure,
                   components=components,final_observe=final_result,scheduled_components=3,completed_native_components=len(components),
                   unexecuted_components=[s[0] for s in STAGES[len(components):]],qualifications='NOT_RUN',
                   model_scope='native-task action routing; common fixed outer dependency executor')
    base.write(composite_dir/'summary.json',composite)
    if failure and not any(c['outcome'] != 'SUCCEEDED' for c in components):
        # Reset/Observe/precondition/budget failures have no native task episode.
        # Keep that distinct attempt in the ledger rather than silently omitting it.
        COST.append(root/'cost.jsonl',dict(event_id=arm+'-outer-check',kind='trial',arm=arm,
                    trial_id=composite_id+'-orchestration-check',purpose='adaptation',case_id='T3-orchestration-check',
                    runtime_fingerprint=deployment['runtime_fingerprint'],calibration_sha256=deployment['active_backends']['fast']['calibration_sha256'] if arm=='hybrid' else None,
                    reported_outcome='HARNESS_ERROR' if stop else 'FAILED',return_code=None,
                    evidence=[COST.pin(composite_dir/'summary.json')]))
    regression=None
    if not stop and base.new_call_upper_bound(registration_budget,base.budget_snapshot())>=250000:
        stop='additional paid upper-bound stop threshold before regression'
    if not stop:
        regression_dir=directory/'regression';regression_dir.mkdir()
        stop=prepare(regression_dir,arm,'source')
        if not stop:
            regression=native(root,arm,regression_dir/'S1',deployment,'S1-source-regression')
            stop=regression['harness_error']
    base.verify_deployment(deployment)
    shutil.copyfile(runtime/'fleet.log',directory/'fleet.log')
    status=dict(arm=arm,stop_reason=stop,composite_outcome=composite['outcome'],regression_outcome=(regression or {}).get('outcome','NOT_RUN'),
                native_episode_count=sum(c['run_id'] is not None for c in components)+(1 if regression and regression['run_id'] else 0),
                native_trial_count=len(components)+(1 if regression else 0),model_or_skill_tuning_during_run=False,
                shared_new_executor_engineering='reported once in plan/shared_development.json, not free',human_minutes='NOT_RUN',
                additional_paid_upper_bound_microyuan=base.new_call_upper_bound(registration_budget,base.budget_snapshot()),final_budget=base.budget_snapshot(),
                runtime=str(runtime),AC90='NOT_RUN',qualification='FROZEN')
    base.write(directory/'status.json',status)
    COST.append(root/'cost.jsonl',dict(event_id=arm+'-stop',kind='effort_stop',arm=arm,session_id=arm+'-orchestration',clock_id=COST.clock_id(),
                end_ns=time.perf_counter_ns(),evidence=[COST.pin(directory/'status.json')]))
    base.write(directory/'cost_report.json',COST.summarize(COST.read_ledger(root/'cost.jsonl')))
    print(json.dumps(dict(arm=arm,composite=composite['outcome'],regression=status['regression_outcome'],stop_reason=stop)),flush=True)
    return 1 if stop else 0


def main():
    parser=argparse.ArgumentParser(description=__doc__);sub=parser.add_subparsers(dest='command',required=True)
    prepare_parser=sub.add_parser('register');prepare_parser.add_argument('--deployment',type=Path,required=True)
    prepare_parser.add_argument('--baseline-revision',required=True);prepare_parser.add_argument('--executor-revision',required=True)
    prepare_parser.add_argument('--development',type=Path,required=True)
    run=sub.add_parser('run-arm');run.add_argument('--arm',choices=('fsm','hybrid'),required=True)
    for command in (prepare_parser,run):command.add_argument('--root',type=Path,required=True)
    args=parser.parse_args()
    if args.command=='register':register(args.root,args.deployment,args.baseline_revision,args.executor_revision,args.development);return 0
    return run_arm(args.root,args.arm)


if __name__=='__main__':sys.exit(main())
