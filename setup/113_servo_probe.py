#!/usr/bin/env python3
"""Isolated Gazebo pinning experiment; mainline world/robot are untouched."""
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
    ap.add_argument('--out', required=True)
    ap.add_argument('--seconds', type=float, default=3)
    ap.add_argument('--velocity-control', action='store_true',
                    help='Isolated falsifier: zero velocity every physics step, with gravity still on')
    args = ap.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=False)
    os.environ['GZ_PARTITION'] = 'flexcell-servo-probe-' + uuid.uuid4().hex
    import gz.transport13 as gz
    from gz.msgs10 import boolean_pb2, entity_factory_pb2, pose_pb2, pose_v_pb2
    repo = Path(__file__).resolve().parents[1]
    original = ET.parse(repo / 'worlds/flexcell_world.sdf').getroot().find('world')
    root = ET.Element('sdf', version='1.9')
    world = ET.SubElement(root, 'world', name='servo_probe')
    for item in original:
        if item.tag in ('physics', 'gravity', 'plugin'):
            world.append(copy.deepcopy(item))
    ground = next(m for m in original.findall('model') if m.get('name') == 'ground_plane')
    world.append(copy.deepcopy(ground))
    template = next(m for m in original.findall('model') if m.get('name') == 'target_box_b')
    sdf = out / 'probe_world.sdf'
    ET.ElementTree(root).write(sdf, encoding='unicode')
    rows = []
    lock = threading.Lock()
    node = gz.Node()

    def poses(msg):
        ns = msg.header.stamp.sec * 1_000_000_000 + msg.header.stamp.nsec
        now = time.monotonic_ns()
        with lock:
            for p in msg.pose:
                if p.name.startswith('probe_box_'):
                    rows.append(dict(kind='pose', mono_ns=now, sim_ns=ns, name=p.name,
                                     xyz=[p.position.x, p.position.y, p.position.z]))

    node.subscribe(pose_v_pb2.Pose_V, '/world/servo_probe/dynamic_pose/info', poses)
    with (out / 'gazebo.log').open('w') as log:
        process = subprocess.Popen(['gz', 'sim', str(sdf.resolve()), '-r', '-s', '-v', '2'],
                                   stdout=log, stderr=log, start_new_session=True)
        try:
            time.sleep(3)
            cases = []
            for gravity, collision in ((True, True), (False, True), (True, False)):
                for period in (.1, .02):
                    for schedule in ('after_reply', 'fixed_deadline'):
                        cases.append((gravity, collision, period, schedule))
            if args.velocity_control:
                cases = [(True, collision, .1, schedule) for collision in (True, False)
                         for schedule in ('after_reply', 'fixed_deadline')]
            summaries = []
            for index, (gravity, collision, period, schedule) in enumerate(cases):
                name = f'probe_box_{index:02d}'
                model = copy.deepcopy(template)
                model.set('name', name)
                model.find('pose').text = f'{index + 1} 0 0.1175 0 0 0'
                link = model.find('link')
                ET.SubElement(link, 'gravity').text = 'true' if gravity else 'false'
                if not collision: link.remove(link.find('collision'))
                if args.velocity_control:
                    plugin = ET.SubElement(model, 'plugin', filename='gz-sim-velocity-control-system',
                                           name='gz::sim::systems::VelocityControl')
                    ET.SubElement(plugin, 'initial_linear').text = '0 0 0'
                    ET.SubElement(plugin, 'initial_angular').text = '0 0 0'
                create = entity_factory_pb2.EntityFactory()
                create.sdf = '<sdf version="1.9">' + ET.tostring(model, encoding='unicode') + '</sdf>'
                (out / (name + '.sdf')).write_text(create.sdf)
                created, reply = node.request('/world/servo_probe/create', create,
                                              entity_factory_pb2.EntityFactory, boolean_pb2.Boolean, 2000)
                if not created or not reply.data:
                    raise RuntimeError('isolated diagnostic object creation failed')
                req = pose_pb2.Pose()
                req.name = name
                req.position.x, req.position.y, req.position.z = index + 1, 0, .1175
                req.orientation.w = 1
                start = time.monotonic()
                next_pin = start
                commands = []
                while time.monotonic() - start < args.seconds:
                    before = time.monotonic_ns()
                    transport_ok, response = node.request('/world/servo_probe/set_pose', req,
                                                          pose_pb2.Pose, boolean_pb2.Boolean, 100)
                    after = time.monotonic_ns()
                    item = dict(kind='command', mono_ns=before, reply_ns=after, name=name,
                                target=[index + 1, 0, .1175], transport_ok=transport_ok,
                                reply_data=response.data, latency_ms=(after - before) / 1e6)
                    commands.append(item)
                    with lock: rows.append(item)
                    if schedule == 'after_reply': time.sleep(period)
                    else:
                        next_pin += period
                        time.sleep(max(0, next_pin - time.monotonic()))
                end = time.monotonic_ns()
                with lock:
                    samples = [r for r in rows if r['kind'] == 'pose' and r['name'] == name
                               and start * 1e9 <= r['mono_ns'] <= end]
                values = sorted(p['xyz'][2] for p in samples)
                intervals = [(b['mono_ns'] - a['mono_ns']) / 1e6 for a, b in zip(commands, commands[1:])]
                summary = dict(name=name, gravity=gravity, collision=collision,
                               velocity_control=args.velocity_control,
                               period_s=period, schedule=schedule, duration_s=args.seconds,
                               samples=len(values), commands=len(commands),
                               transport_failed=sum(not c['transport_ok'] for c in commands),
                               reply_false=sum(not c['reply_data'] for c in commands),
                               z_min=min(values) if values else None,
                               z_max=max(values) if values else None,
                               z_median=values[len(values)//2] if values else None,
                               below_pick_threshold_fraction=sum(z < .0475 for z in values)/len(values) if values else None,
                               command_interval_ms_min=min(intervals) if intervals else None,
                               command_interval_ms_max=max(intervals) if intervals else None)
                summaries.append(summary)
                print(json.dumps(summary), flush=True)
            (out / 'summary.json').write_text(json.dumps(dict(
                purpose='Mechanism diagnostic, not benchmark', partition=os.environ['GZ_PARTITION'],
                physics_dt_s=.005, target_rtf=1, target_z_m=.1175, cases=summaries), indent=2) + '\n')
        finally:
            node.unsubscribe('/world/servo_probe/dynamic_pose/info')
            with lock:
                (out / 'trace.jsonl').write_text('\n'.join(json.dumps(r) for r in sorted(rows, key=lambda r:r['mono_ns'])) + '\n')
            os.killpg(process.pid, signal.SIGTERM)
            try: process.wait(5)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL); process.wait()


if __name__ == '__main__':
    main()
