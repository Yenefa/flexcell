#!/usr/bin/env python3
"""One declared five-cycle native fixture on a stationary simulated arm."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time
import traceback
import uuid
import yaml

from sim_profile import ROOT, profile
from sim_smoke import command, remember_owned, terminate_owned
from contact_probe import mapped_libraries
from contact_gate import observation, require
from native_cycle_gate import limits, pose_error, verify_cycle, verify_run
from flexcell_skills.joint_follow import relative_pose


class Follower:
    def __init__(self, out):
        self.streams = [(out/name).open() for name in ('physics_steps.jsonl', 'contact_steps.jsonl')]
        self.tables = [{}, {}]
        # A live subscriber starts at new data. Complete immutable files remain
        # the offline gate's authority; startup/cycle history is never deleted.
        for stream in self.streams: stream.seek(0,os.SEEK_END)
        self.align_new_record = [True,True]

    def diagnostic(self):
        """Preserve the failed reader position without consuming newer data."""
        try:
            now = time.monotonic_ns()
            common = self.tables[0].keys() & self.tables[1].keys()
            newest = max(common) if common else None
            return dict(observed_monotonic_ns=now, latest_common_sim_ns=newest,
                common_age_ns=now-self.tables[0][newest]['monotonic_ns'] if newest is not None else None,
                latest_rows=[dict(sim_ns=max(table),monotonic_ns=table[max(table)]['monotonic_ns'])
                             if table else None for table in self.tables],
                table_sizes=[len(table) for table in self.tables],
                file_offsets=[stream.tell() for stream in self.streams],
                file_sizes=[os.fstat(stream.fileno()).st_size for stream in self.streams])
        except Exception as exc:
            return dict(diagnostic_error=repr(exc))

    def collect(self):
        for index,(stream, table) in enumerate(zip(self.streams, self.tables)):
            while True:
                position = stream.tell(); line = stream.readline()
                if not line or not line.endswith('\n'):
                    stream.seek(position); break
                if self.align_new_record[index]:
                    self.align_new_record[index] = False
                    continue  # EOF may have landed inside an in-progress write.
                row = json.loads(line); table[row['sim_ns']] = row
                if len(table) > 1024: table.pop(next(iter(table)))
        return sorted(self.tables[0].keys() & self.tables[1].keys())

    def wait(self, condition, timeout=5., *, earliest=False, watch=None):
        deadline = time.monotonic()+timeout
        while time.monotonic() < deadline:
            keys = self.collect()
            if keys:
                newest = self.tables[0][keys[-1]]
                newest_age = time.monotonic_ns()-newest['monotonic_ns']
                require(newest_age < 500_000_000, 'native stream stale; age_ns='+str(newest_age))
                choices = keys if earliest else keys[-1:]
                for ns in choices:
                    p, c = self.tables[0][ns], self.tables[1][ns]
                    if watch: watch(p,c)
                    # Pre-trigger history is not a live reference candidate.
                    # The first eligible candidate still must be fresh; never
                    # skip an eligible stale reference to find a passing one.
                    if condition(p,c):
                        age = time.monotonic_ns()-p['monotonic_ns']
                        require(age < 500_000_000, 'native candidate stale; age_ns='+str(age))
                        return p,c
            time.sleep(.002)
        raise RuntimeError('native frame condition timed out; no replacement cycle')


def audit_cycle(out, cycle, declaration, offsets=None):
    """Read each raw record once across cycles; gate before dispatching the next.

    The next cycle waits >1 sim s detached before preposition, so all of its
    required one-second prehistory is newer than the previous audit's EOF.
    Full files remain untouched and verify_run independently checks them at exit.
    """
    if offsets is None:
        offsets = {}
    def complete(path):
        position, previous = offsets.get(path.name, (0, None))
        records = []
        with path.open('rb') as stream:
            stream.seek(position)
            end = os.fstat(stream.fileno()).st_size
            while True:
                position = stream.tell()
                if position >= end:
                    break
                line = stream.readline()
                if not line.endswith(b'\n') or stream.tell() > end:
                    break  # retain a partial append for the next read
                row = json.loads(line)
                if 'sim_ns' in row:
                    require(previous is None or row['sim_ns'] > previous,
                            'duplicate or reordered native step')
                    previous = row['sim_ns']
                records.append(row)
        offsets[path.name] = position, previous
        return records
    p_rows, c_rows = complete(out/'physics_steps.jsonl'), complete(out/'contact_steps.jsonl')
    require(len({p['sim_ns'] for p in p_rows}) == len(p_rows) and
            len({c['sim_ns'] for c in c_rows}) == len(c_rows), 'duplicate native step')
    for c in c_rows:
        for target in c['targets'].values(): observation(target)
    return verify_cycle({p['sim_ns']:p for p in p_rows},{c['sim_ns']:c for c in c_rows},
        cycle,complete(out/'native-events.jsonl'),declaration)


def worker(out, world, declaration):
    import gz.transport13
    from gz.msgs10 import pose_pb2, empty_pb2, stringmsg_pb2, boolean_pb2
    node = gz.transport13.Node(); follow = None
    events = (out/'native-events.jsonl').open('x'); log_lock = threading.Lock()
    stop = threading.Event(); heartbeat = None; heartbeat_errors = []
    result = dict(status='STOPPED', cycles=[], robot_motion_tasks=0, max_cycles=5, no_replacements=True)
    audit_offsets = {}

    def pose(name, values, session=''):
        message = pose_pb2.Pose(); message.name = name
        message.position.x, message.position.y, message.position.z = values[:3]
        message.orientation.x, message.orientation.y, message.orientation.z, message.orientation.w = values[3:]
        if session:
            item = message.header.data.add(); item.key = 'carry_session'; item.value.append(session)
        return message

    def rpc(operation, label, index, *, name='', token='', values=None):
        if operation == 'status': message, response_type = empty_pb2.Empty(), stringmsg_pb2.StringMsg
        elif operation == 'release': message, response_type = stringmsg_pb2.StringMsg(data=token), boolean_pb2.Boolean
        else: message, response_type = pose(name, values, token), boolean_pb2.Boolean
        path = '/world/'+world+('/set_pose' if operation == 'set_pose' else '/flexcell/carry/'+operation)
        started = time.monotonic_ns()
        ok, reply = node.request(path,message,type(message),response_type,1000)
        value = (json.loads(reply.data) if operation == 'status' else bool(reply.data)) if ok else None
        event = dict(cycle=index,label=label,operation=operation,object=name,session=token,pose=values,
                     request_mono_ns=started,reply_mono_ns=time.monotonic_ns(),transport_ok=ok,reply=value)
        with log_lock: events.write(json.dumps(event,allow_nan=False)+'\n'); events.flush()
        require(ok, operation+' reply unknown')
        return value,event

    def stop_heartbeat():
        stop.set()
        if heartbeat is not None:
            heartbeat.join(timeout=2.)
            require(not heartbeat.is_alive(), 'lease thread terminal unknown')

    try:
        previous = ''
        for index,name in enumerate(declaration['objects']):
            if follow is not None:
                for stream in follow.streams: stream.close()
            follow = Follower(out)  # previous cycle's complete raw files were already gated
            token = uuid.uuid4().hex
            cycle = dict(index=index,object=name,session=token,previous_session=previous)
            result['cycles'].append(cycle)
            status,_ = rpc('status','initial_status',index)
            require(status['ready'] and not status['engaged'] and status['component_present'] == [False,False],
                    'native guard is not explicitly detached before preposition')
            initial,_ = follow.wait(lambda p,c: all(not p['objects'][n]['joint_component'] for n in ('target_box_a','target_box_b')))
            follow.wait(lambda p,c: p['sim_ns'] >= initial['sim_ns']+1_050_000_000,timeout=8.)
            status,detached_status = rpc('status','before_preposition',index)
            require(status['ready'] and not status['engaged'] and not status['session'] and
                    status['component_present'] == [False,False], 'preposition precondition changed')
            follow.wait(lambda p,c: p['monotonic_ns'] >= detached_status['reply_mono_ns'] and
                        all(p['objects'][n]['joint_component'] is False for n in ('target_box_a','target_box_b')))
            command_target = declaration['preposition_poses'][name]
            ok,prepose = rpc('set_pose','preposition',index,name=name,values=command_target)
            require(ok, 'detached preposition rejected')
            def eligible(p,c):
                import math
                return (p['monotonic_ns'] >= prepose['reply_mono_ns'] and
                        all(not p['objects'][n]['joint_component'] for n in ('target_box_a','target_box_b')) and
                        math.dist(p['objects'][name]['pose'][:3],command_target[:3]) <= .005 and
                        observation(c['targets'][name])['state'] == 'NO_REPORTED_CONTACTS')
            reference,_ = follow.wait(eligible,earliest=True)
            cycle['reference_sim_ns'] = reference['sim_ns']
            ref = relative_pose(reference['parent_pose'],reference['objects'][name]['pose'])
            target = reference['objects'][name]['pose']
            ok,_ = rpc('engage','engage',index,name=name,token=token,values=target)
            require(ok, 'native engage rejected')
            stop.clear()
            def renew(i=index,n=name,t=token,v=target):
                while not stop.wait(.06):
                    try:
                        ok,_ = rpc('pin','heartbeat',i,name=n,token=t,values=v)
                        if not ok: heartbeat_errors.append('active native heartbeat rejected'); return
                    except Exception as exc: heartbeat_errors.append(str(exc)); return
            heartbeat = threading.Thread(target=renew,daemon=True); heartbeat.start()
            other = 'target_box_b' if name == 'target_box_a' else 'target_box_a'
            require(not rpc('engage','reject_other_engage',index,name=other,token=uuid.uuid4().hex,
                            values=reference['objects'][other]['pose'])[0], 'other object stole ownership')
            require(not rpc('pin','reject_other_pin',index,name=other,token=token,
                            values=reference['objects'][other]['pose'])[0], 'other object pin accepted')
            if previous:
                require(not rpc('release','reject_old_release',index,token=previous)[0], 'old release accepted')
                require(not rpc('pin','reject_old_pin',index,name=name,token=previous,values=target)[0], 'old pin accepted')
            status,_ = rpc('status','after_probes',index)
            require(status['engaged'] and status['object'] == name and status['session'] == token,
                    'ownership changed after rejection probes')
            def watch(p,c):
                require(not heartbeat_errors, str(heartbeat_errors))
                require(p['objects'][name]['joint_component'] is True, 'joint disappeared before requested release')
                require(observation(c['targets'][name])['state'] == 'NO_REPORTED_CONTACTS', 'unexpected active contact')
                position,angle = pose_error(p['parent_pose'],p['objects'][name]['pose'],ref)
                require(position < .002 and angle < declaration['rotation_limit_rad'], 'preposition reference drift')
            attached,_ = follow.wait(lambda p,c:p['objects'][name]['joint_component'] is True)
            follow.wait(lambda p,c:p['sim_ns'] >= attached['sim_ns']+declaration['hold_ns'],timeout=50.,watch=watch)
            stop_heartbeat()
            require(rpc('release','release',index,token=token)[0], 'native release rejected')
            released,_ = follow.wait(lambda p,c:p['objects'][name]['joint_component'] is False)
            settled,_ = follow.wait(lambda p,c:p['sim_ns'] >= released['sim_ns']+declaration['settle_ns'],timeout=8.)
            status,_ = rpc('status','after_release',index)
            require(status['ready'] and not status['engaged'] and status['component_present'] == [False,False],
                    'native release not reconciled')
            cycle['retired_probe_sim_ns'] = settled['sim_ns']
            require(not rpc('engage','reject_retired_engage',index,name=name,token=token,
                            values=settled['objects'][name]['pose'])[0], 'retired session re-engaged')
            final,_ = rpc('status','final_status',index)
            require(not final['engaged'] and not final['session'], 'retired probe changed ownership')
            # A supervisor deadline must still leave the completed operations and
            # the pending audit visible; an incomplete checkpoint is never PASS.
            (out/'worker.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
            cycle['evidence'] = audit_cycle(out,cycle,declaration,audit_offsets)
            previous = token
        require(not heartbeat_errors, str(heartbeat_errors))
        result['status'] = 'PASS'
    except Exception as exc:
        result.update(error=repr(exc),failure_monotonic_ns=time.monotonic_ns(),
                      failure_traceback=traceback.format_exc())
        result['live_reader'] = follow.diagnostic() if follow is not None else None
    finally:
        try: stop_heartbeat()
        except Exception as exc: result.update(status='STOPPED',error=repr(exc))
        events.close()
        result['heartbeat_errors'] = heartbeat_errors
        (out/'worker.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
    return 0 if result['status'] == 'PASS' else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--worker',action='store_true'); parser.add_argument('--world',default='empty')
    args = parser.parse_args(); declaration = json.loads(args.manifest.read_text()); limits(declaration)
    if args.worker: return worker(args.out,args.world,declaration)
    out = args.out; out.mkdir(parents=True,exist_ok=False)
    (out/'declaration.json').write_bytes(args.manifest.read_bytes())
    params,world = profile(out,'detachable_joint',False,'legacy',0.,.002,
                           contact_trace=True,synchronous_step_logs=True)
    semantic = yaml.safe_load(params.read_text())
    for node in semantic.values():
        for key in ('log_dir','episode_dir'):
            if key in node.get('ros__parameters',{}): node['ros__parameters'][key] = '$RUN/'+key
    sha = lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
    identity_matches = (sha(world) == declaration['world_sha256'] and
        hashlib.sha256(json.dumps(semantic,sort_keys=True).encode()).hexdigest() == declaration['semantic_config_sha256'])
    result = dict(status='STOPPED',robot_motion_tasks=0,max_cycles=5,no_replacements=True,default_admission='NO_GO',
                  declaration_sha256=sha(args.manifest),world_sha256=sha(world))
    os.environ.update(FLEXCELL_PHYSICS_STEP_LOG=str(out/'physics_steps.jsonl'),
                      FLEXCELL_CONTACT_STEP_LOG=str(out/'contact_steps.jsonl'),GZ_PARTITION='flexcell-native5-'+uuid.uuid4().hex)
    result['partition'] = os.environ['GZ_PARTITION']
    stack = recorder = None; stack_log = (out/'stack.log').open('x')
    def interrupted(signum,_frame): raise RuntimeError('native fixture interrupted: '+str(signum))
    signal.signal(signal.SIGTERM,interrupted); signal.signal(signal.SIGINT,interrupted)
    try:
        require(identity_matches,'native fixture world/config differ from committed declaration')
        require(command([sys.executable,str(ROOT/'infra/runtime_identity.py')],out/'identity') == 0,'source/install mismatch')
        identity = json.loads((out/'identity.stdout').read_text())
        result['runtime_fingerprint'] = hashlib.sha256(json.dumps(dict(identity=identity,declaration=declaration,
            config=semantic),sort_keys=True).encode()).hexdigest()
        stack = subprocess.Popen(['ros2','launch','flexcell_skills','trusted_sim.launch.py',
            'world:='+str(world),'params_file:='+str(params)],stdout=stack_log,stderr=subprocess.STDOUT,start_new_session=True)
        remember_owned(out,stack); ready = False
        for attempt in range(6):
            time.sleep(3); target = out/('health_before_%d'%attempt)
            if command([sys.executable,str(ROOT/'setup/flexcell_admin.py'),'health'],target,timeout=40) == 0:
                doc = json.loads(target.with_suffix('.stdout').read_text())
                if doc['ok'] and not doc['hard_fail'] and doc['checks']['task_state'] == 'IDLE' and not doc['checks']['carry_engaged']:
                    ready = True; break
        require(ready, 'strict startup health failed; no cycle dispatched')
        names = ('flexcell_contact_trace','flexcell_physics_trace','flexcell_detachable_carry')
        loaded = mapped_libraries(stack.pid,names)
        for name in names:
            require(any(name in p and h == identity['native_libraries']['lib/lib'+name+'.so'] for p,h in loaded.items()),
                    'actual native library not confirmed: '+name)
        (out/'loaded_libraries.json').write_text(json.dumps(loaded,indent=2)+'\n')
        require(command([sys.executable,str(ROOT/'setup/flexcell_admin.py'),'reset'],out/'reset_before') == 0,'initial reset failed')
        follower = Follower(out); first,_ = follower.wait(lambda p,c:True)
        last,_ = follower.wait(lambda p,c:p['sim_ns'] >= first['sim_ns']+500_000_000)
        result['preflight_rtf'] = (last['sim_ns']-first['sim_ns'])/(last['monotonic_ns']-first['monotonic_ns'])
        require(result['preflight_rtf'] >= declaration['min_preflight_rtf'],'native fixture too slow; no cycle dispatched')
        recorder_log = (out/'recorder.log').open('x')
        recorder = subprocess.Popen([sys.executable,str(ROOT/'scripts/record_sim_data.py'),'--out',str(out/'data')],
            stdout=recorder_log,stderr=subprocess.STDOUT,start_new_session=True)
        remember_owned(out,recorder); time.sleep(2)
        require(recorder.poll() is None,'recorder exited before fixture')
        import xml.etree.ElementTree as ET
        world_name = ET.parse(world).getroot().find('world').get('name')
        with (out/'worker.log').open('x') as stream:
            proc = subprocess.run([sys.executable,__file__,'--worker','--out',str(out),
                '--manifest',str(out/'declaration.json'),'--world',world_name],stdout=stream,stderr=subprocess.STDOUT,
                env=dict(os.environ,PROTOCOL_BUFFERS_PYTHON_IMPLEMENTATION='python'),timeout=330)
        result['worker_exit'] = proc.returncode
        require(proc.returncode == 0,'native cycle failed; window stopped without reset')
        require(command([sys.executable,str(ROOT/'setup/flexcell_admin.py'),'health'],out/'health_after_cycles') == 0,
                'post-cycle health failed')
        require(command([sys.executable,str(ROOT/'setup/flexcell_admin.py'),'reset'],out/'reset_after') == 0,
                'final detached reset failed')
        require(command([sys.executable,str(ROOT/'setup/flexcell_admin.py'),'health'],out/'health_after') == 0,
                'final health failed')
        result['status'] = 'PASS'
    except (Exception,KeyboardInterrupt) as exc:
        result['error'] = repr(exc)
    finally:
        if recorder is not None:
            terminate_owned(recorder); recorder_log.close(); result['recorder_exit'] = recorder.returncode
            if recorder.returncode != 0: result.update(status='STOPPED',error='native fixture recorder failed')
        if stack is not None: terminate_owned(stack); result['owned_exit'] = stack.returncode
        stack_log.close()
        if result['status'] == 'PASS':
            try: result['evidence'] = verify_run(out,declaration)
            except Exception as exc: result.update(status='STOPPED',error=repr(exc))
        (out/'result.json').write_text(json.dumps(result,indent=2,allow_nan=False)+'\n')
        print(json.dumps(result,indent=2,allow_nan=False))
    return 0 if result['status'] == 'PASS' else 1


if __name__ == '__main__':
    raise SystemExit(main())
