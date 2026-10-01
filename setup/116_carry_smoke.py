#!/usr/bin/env python3
"""Real plugin hold/release/lease smoke in a private Gazebo partition."""
import argparse
import copy
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time
import uuid
import xml.etree.ElementTree as ET


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--out', required=True, type=Path)
    ap.add_argument('--record', action='store_true')
    args = ap.parse_args()
    if args.record:
        import gz.transport13 as gz
        from gz.msgs10 import pose_v_pb2
        node = gz.Node()
        done, lock = threading.Event(), threading.Lock()
        signal.signal(signal.SIGTERM, lambda *a: done.set())
        with (args.out/'poses.jsonl').open('w') as stream:
            def record(message):
                with lock:
                    for pose in message.pose:
                        if pose.name == 'target_box_a':
                            stream.write(json.dumps(dict(event='pose',mono_ns=time.monotonic_ns(),
                                sim_ns=message.header.stamp.sec*10**9+message.header.stamp.nsec,
                                z=pose.position.z))+'\n')
                    stream.flush()
            node.subscribe(pose_v_pb2.Pose_V,'/world/carry_probe/dynamic_pose/info',record)
            done.wait()
            node.unsubscribe('/world/carry_probe/dynamic_pose/info')
        return
    args.out.mkdir(parents=True, exist_ok=False)
    os.environ['GZ_PARTITION'] = 'carry-lifecycle-' + uuid.uuid4().hex
    import gz.transport13 as gz
    from gz.msgs10 import boolean_pb2, empty_pb2, pose_pb2, pose_v_pb2, stringmsg_pb2
    repo = Path(__file__).resolve().parents[1]
    original = ET.parse(repo/'worlds/flexcell_velocity_servo.sdf').getroot().find('world')
    root = ET.Element('sdf', version='1.10')
    world = ET.SubElement(root, 'world', name='carry_probe')
    for item in original:
        if item.tag in ('physics', 'gravity', 'plugin') or (
                item.tag=='model' and item.get('name') in ('ground_plane', 'target_box_a')):
            world.append(copy.deepcopy(item))
    sdf = args.out/'world.sdf'
    ET.ElementTree(root).write(sdf, encoding='unicode')
    rows = []
    node = gz.Node()
    def samples():
        path = args.out/'poses.jsonl'
        if not path.exists(): return []
        return [json.loads(line) for line in path.read_text().splitlines() if line.endswith('}')]
    prefix = '/world/carry_probe/flexcell/carry/'

    def command(operation, request, request_type, expected):
        began = time.monotonic_ns()
        transport, reply = node.request(prefix+operation, request, request_type, boolean_pb2.Boolean, 1500)
        rows.append(dict(event=operation, mono_ns=began, reply_ns=time.monotonic_ns(),
                         transport=transport, reply=reply.data, expected=expected))
        if not transport or reply.data != expected:
            native = subprocess.run(['gz','service','-s',prefix+operation,
                '--reqtype', request_type.DESCRIPTOR.full_name,
                '--reptype','gz.msgs.Boolean','--timeout','2000','--req',str(request)],
                capture_output=True,text=True,timeout=4)
            (args.out/('native_'+operation+'.txt')).write_text(native.stdout+native.stderr)
            raise RuntimeError(operation+' acknowledgement differs from expected')

    def status():
        ok, reply = node.request(prefix+'status', empty_pb2.Empty(), empty_pb2.Empty, stringmsg_pb2.StringMsg, 1500)
        if not ok: raise RuntimeError('status unavailable')
        value = json.loads(reply.data)
        rows.append(dict(event='status', mono_ns=time.monotonic_ns(), value=value))
        return value

    def pose(session):
        request = pose_pb2.Pose()
        request.name = 'target_box_a'
        request.position.x, request.position.z, request.orientation.w = .22, .2, 1
        item = request.header.data.add(); item.key='carry_session'; item.value.append(session)
        return request

    def release(session):
        request = stringmsg_pb2.StringMsg(); request.data=session
        return request

    summary = dict(stage='LIFECYCLE_SMOKE_NOT_BENCHMARK', partition=os.environ['GZ_PARTITION'], passed=False)
    with (args.out/'gazebo.log').open('w') as log:
        process = subprocess.Popen(['gz','sim',str(sdf.resolve()),'-r','-s','-v','4'],
                                   stdout=log,stderr=log,start_new_session=True)
        recorder = subprocess.Popen(['python3',__file__,'--out',str(args.out),'--record'],stdout=log,stderr=log)
        try:
            deadline = time.monotonic()+20
            needed = {prefix+name for name in ('engage','pin','release','status')}
            while not needed.issubset(set(node.service_list())):
                if time.monotonic()>deadline: raise RuntimeError('carry endpoints not discovered')
                time.sleep(.1)
            (args.out/'discovered_services.json').write_text(json.dumps(node.service_list(),indent=2)+'\n')
            time.sleep(.3)
            first, second = uuid.uuid4().hex, uuid.uuid4().hex
            status()
            command('pin', pose(first), pose_pb2.Pose, False)
            command('release', release(''), stringmsg_pb2.StringMsg, True)
            command('engage', pose(first), pose_pb2.Pose, True)
            begin = time.monotonic_ns()
            for _ in range(6):
                command('pin', pose(first), pose_pb2.Pose, True)
                time.sleep(.1)
            held = [r['z'] for r in samples() if r['mono_ns']>=begin+100_000_000]
            summary['held_min_z_m'] = min(held)
            assert min(held) > .17 and status()['engaged']
            command('pin', pose(second), pose_pb2.Pose, False)
            command('release', release(first), stringmsg_pb2.StringMsg, True)
            assert not status()['engaged']
            command('pin', pose(first), pose_pb2.Pose, False)
            command('engage', pose(first), pose_pb2.Pose, False)
            time.sleep(.7)
            z = samples()[-1]['z']
            summary['released_z_m'] = z
            assert z < .0475, 'velocity constraints survived explicit release'
            command('engage', pose(second), pose_pb2.Pose, True)
            command('release', release(first), stringmsg_pb2.StringMsg, False)
            assert status()['engaged'], 'old session released new owner'
            time.sleep(1.1)  # no heartbeat: native steady-clock lease must release
            assert not status()['engaged']
            z = samples()[-1]['z']
            summary['lease_expired_z_m'] = z
            assert z < .0475, 'lease expiration retained velocity constraints'
            command('release', release(''), stringmsg_pb2.StringMsg, True)
            summary['passed'] = True
        except Exception as exc:
            summary['error'] = type(exc).__name__+': '+str(exc)
            raise
        finally:
            recorder.terminate()
            try: recorder.wait(3)
            except subprocess.TimeoutExpired: recorder.kill();recorder.wait()
            rows.extend(samples())
            (args.out/'trace.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in sorted(rows,key=lambda r:r['mono_ns'])))
            (args.out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n')
            os.killpg(process.pid,signal.SIGTERM)
            try: process.wait(5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait()
    print(json.dumps(summary))


if __name__=='__main__':
    main()
