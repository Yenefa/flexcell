#!/usr/bin/env python3
"""Admission spike for the DetachableJoint carry backend (issue-04).

Runs its own throwaway world and never touches a live stack. It answers the
questions that decide GO/NO_GO, because reading the docs has already proved
unreliable on this exact install:

  * the 8.15 plugin requires `<child_link>`; the published docs list
    `<child_model_link>`, and the wrong name fails with one Err line and no joint;
  * child models must be declared *before* the parent model, otherwise the
    plugin logs "Child Model ... could not be found" and nothing is attached;
  * `gz topic -p` takes the message text as an argument, so an empty message is
    `-p ""`, not a bare `-p`.

Usage:
    python3 setup/113_carry_backend_spike.py --out /tmp/spike.json
    python3 setup/113_carry_backend_spike.py --world worlds/detachable_probe.sdf --verbose

Exit codes: 0 all asserted checks passed, 1 a check failed, 2 the world never came up.
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import shutil
import signal
import subprocess
import sys
import time
import hashlib

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_WORLD = os.path.join(os.path.dirname(HERE), 'worlds', 'detachable_probe.sdf')
WORLD_NAME = 'detachable_probe'
PARENT = 'probe_parent'
BOX_A = 'probe_box_a'
BOX_B = 'probe_box_b'
G = 9.8

VEC = re.compile(r'\[\s*(-?\d+\.?\d*(?:[eE][-+]?\d+)?)\s+'
                 r'(-?\d+\.?\d*(?:[eE][-+]?\d+)?)\s+'
                 r'(-?\d+\.?\d*(?:[eE][-+]?\d+)?)\s*\]')

FINDINGS = [
    {'topic': 'parameter name',
     'observed': 'the 8.15 plugin requires <child_link>',
     'documented': 'the sim 8 docs list <child_model_link>',
     'failure_mode': 'one Err line at load, plugin never initialises, no joint created'},
    {'topic': 'model ordering',
     'observed': 'child models must be declared before the parent model',
     'documented': 'not stated',
     'failure_mode': '"Child Model X could not be found" warning, no joint created'},
    {'topic': 'attach while in contact',
     'observed': 'measured below, recorded not asserted',
     'documented': 'reattachment while parent and child touch is not supported',
     'failure_mode': 'attach silently does nothing'},
]


def quadratic_fit(ts, zs):
    """Least-squares z = c + b t + a t^2 via 3x3 normal equations."""
    n = float(len(ts))
    s0, s1 = n, sum(ts)
    s2 = sum(t * t for t in ts)
    s3 = sum(t ** 3 for t in ts)
    s4 = sum(t ** 4 for t in ts)
    r0 = sum(zs)
    r1 = sum(t * z for t, z in zip(ts, zs))
    r2 = sum(t * t * z for t, z in zip(ts, zs))
    m = [[s0, s1, s2, r0], [s1, s2, s3, r1], [s2, s3, s4, r2]]
    for i in range(3):
        piv = max(range(i, 3), key=lambda k: abs(m[k][i]))
        m[i], m[piv] = m[piv], m[i]
        if abs(m[i][i]) < 1e-12:
            raise RuntimeError('singular fit')
        for k in range(i + 1, 3):
            f = m[k][i] / m[i][i]
            for j in range(i, 4):
                m[k][j] -= f * m[i][j]
    x = [0.0] * 3
    for i in (2, 1, 0):
        x[i] = (m[i][3] - sum(m[i][j] * x[j] for j in range(i + 1, 3))) / m[i][i]
    return x[2], x[1], x[0]


class Spike:
    def __init__(self, world, verbose=False, keep_log=False):
        self.world = world
        self.verbose = verbose
        self.keep_log = keep_log
        self.partition = 'probe_%06d' % random.randint(0, 999999)
        self.env = dict(os.environ, GZ_PARTITION=self.partition)
        self.proc = None
        self.log_path = os.path.join('/tmp', 'spike_%s.log' % self.partition)
        self.log = open(self.log_path, 'w')
        self.results = []

    # ------------------------------------------------------------------ setup
    def start(self, timeout=40.0):
        if not shutil.which('gz'):
            raise RuntimeError('gz not on PATH; source /opt/ros/jazzy/setup.bash')
        self.proc = subprocess.Popen(
            ['gz', 'sim', '-s', '-r', '-v', '2', self.world],
            env=self.env, stdout=self.log, stderr=subprocess.STDOUT,
            preexec_fn=os.setsid)
        deadline = time.time() + timeout
        while time.time() < deadline:
            if '/world/%s/pose/info' % WORLD_NAME in self.run(['gz', 'topic', '-l']).stdout:
                time.sleep(1.0)
                return
            if self.proc.poll() is not None:
                raise RuntimeError('gz sim exited: see %s' % self.log_path)
            time.sleep(0.5)
        raise RuntimeError('world did not come up in %.0fs: %s' % (timeout, self.log_path))

    def stop(self):
        if self.proc and self.proc.poll() is None:
            try:
                os.killpg(os.getpgid(self.proc.pid), signal.SIGINT)
                self.proc.wait(timeout=10)
            except Exception:
                try:
                    os.killpg(os.getpgid(self.proc.pid), signal.SIGKILL)
                except Exception:
                    pass
        self.log.close()
        # Keep the owned server log for both passing and failing fixtures.

    # ---------------------------------------------------------------- helpers
    def run(self, args, timeout=12):
        return subprocess.run(args, env=self.env, capture_output=True,
                              text=True, timeout=timeout)

    def pose(self, model):
        out = self.run(['gz', 'model', '-m', model, '-p']).stdout
        m = VEC.search(out)
        if not m:
            raise RuntimeError('cannot parse pose of %s:\n%s' % (model, out))
        return tuple(float(x) for x in m.groups())

    def set_pose(self, model, x, y, z):
        req = ('name: "%s" position { x: %f y: %f z: %f } '
               'orientation { x: 0 y: 0 z: 0 w: 1 }' % (model, x, y, z))
        cp = self.run(['gz', 'service', '-s', '/world/%s/set_pose' % WORLD_NAME,
                       '--reqtype', 'gz.msgs.Pose', '--reptype', 'gz.msgs.Boolean',
                       '--timeout', '3000', '--req', req])
        return cp.returncode == 0 and 'true' in cp.stdout.lower()

    def publish(self, topic):
        cp = self.run(['gz', 'topic', '-t', topic, '-m', 'gz.msgs.Empty', '-p', ''])
        if cp.returncode != 0:
            raise RuntimeError('publish %s failed: %s' % (topic, cp.stderr.strip()))
        return True

    def follows(self, model, dx=0.05, wait=0.3):
        """Functional attachment test: teleport the parent, see if the child does."""
        px, py, pz = self.pose(PARENT)
        before = self.pose(model)
        if not self.set_pose(PARENT, px + dx, py, pz):
            raise RuntimeError('parent set_pose was not confirmed')
        time.sleep(wait)
        after = self.pose(model)
        self.set_pose(PARENT, px, py, pz)
        time.sleep(0.1)
        moved = after[0] - before[0]
        return abs(moved - dx) < 0.006, moved

    # ----------------------------------------------------------------- checks
    def record(self, name, passed, detail, asserted=True, **extra):
        row = dict(check=name, passed=bool(passed), asserted=asserted, detail=detail, **extra)
        self.results.append(row)
        print('%-34s %s  %s' % (name, 'PASS' if passed else 'FAIL', detail))
        return row

    def check_initial(self):
        z0 = self.pose(BOX_A)[2]
        time.sleep(2.0)
        z1 = self.pose(BOX_A)[2]
        self.record('initial_attachment_holds', abs(z1 - z0) < 1e-5
                    and abs(z1 - 0.30) < 0.01,
                    'z %.4f -> %.4f over 2 s' % (z0, z1))

    def start_stream(self):
        """Open the 50 Hz pose stream in one process and let it buffer.

        One CLI call per pose costs ~0.4 s, useless for a 1 s fall; a single
        echo of /world/<w>/dynamic_pose/info carries sim-time stamps instead.
        """
        proc = subprocess.Popen(
            ['gz', 'topic', '-e', '-t', '/world/%s/dynamic_pose/info' % WORLD_NAME,
             '-n', '120', '--json-output'],
            env=self.env, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True)
        time.sleep(0.3)
        return proc

    def collect_stream(self, proc, seconds):
        time.sleep(seconds)
        proc.terminate()
        out = proc.communicate(timeout=5)[0]
        frames = []
        for line in out.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                doc = json.loads(line)
            except ValueError:
                continue
            stamp = doc.get('header', {}).get('stamp', {})
            t = float(stamp.get('sec', 0)) + float(stamp.get('nsec', 0)) * 1e-9
            for pose in doc.get('pose', []):
                if pose.get('name') == BOX_A:
                    pos = pose.get('position', {})
                    frames.append((t, float(pos.get('x', 0.0)),
                                   float(pos.get('y', 0.0)), float(pos.get('z', 0.0))))
        return frames

    def check_freefall(self, height=4.0):
        self.publish('/probe/a/detach')
        time.sleep(0.3)
        proc = self.start_stream()
        self.set_pose(BOX_A, 0, 0, height)
        frames = self.collect_stream(proc, seconds=1.6)
        if not frames:
            self.record('detach_allows_freefall', False, 'no pose frames captured')
            return
        top = max(f[3] for f in frames)
        air = [f for f in frames if f[3] > top - 1.2 and f[3] > 0.05]
        if len(air) < 5:
            self.record('detach_allows_freefall', False,
                        'only %d airborne frames (top %.2f)' % (len(air), top))
            return
        t0 = air[0][0]
        a, _, _ = quadratic_fit([f[0] - t0 for f in air], [f[3] for f in air])
        accel = 2.0 * a
        self.record('detach_allows_freefall', abs(accel + G) <= .2 * G,
                    'fitted a=%+.2f m/s^2 from %d airborne frames over %.2f s' %
                    (accel, len(air), air[-1][0] - air[0][0]),
                    accel=accel, frames=len(air), top=top)

    def check_reattach(self, cycles=5):
        deltas, failures = [], 0
        for _ in range(cycles):
            self.publish('/probe/a/detach')
            time.sleep(0.1)
            px, py, pz = self.pose(PARENT)
            self.set_pose(BOX_A, px, py, pz - 0.20)
            time.sleep(0.1)
            self.publish('/probe/a/attach')
            time.sleep(0.2)
            ok, moved = self.follows(BOX_A)
            deltas.append(moved)
            if not ok:
                failures += 1
        self.record('reattach_5_cycles', failures == 0,
                    '%d/%d followed after re-attach; deltas %s' %
                    (cycles - failures, cycles, ['%+.4f' % d for d in deltas]),
                    deltas=deltas)

    def check_rigidity(self, steps=10, step=0.01):
        px, py, pz = self.pose(PARENT)
        self.set_pose(BOX_A, px, py, pz - 0.20)
        time.sleep(0.1)
        self.publish('/probe/a/attach')
        time.sleep(0.2)
        base = self.pose(BOX_A)
        errors = []
        for i in range(1, steps + 1):
            self.set_pose(PARENT, px + step * i, py, pz)
            time.sleep(0.15)
            errors.append(abs((self.pose(BOX_A)[0] - base[0]) - step * i))
        self.set_pose(PARENT, px, py, pz)
        time.sleep(0.1)
        self.record('rigidity_under_teleport',
                    max(errors) < 0.002 and abs(base[0] - px) < 1e-6,
                    'max tracking error %.4f m over %d steps' % (max(errors), steps),
                    max_error=max(errors))

    def check_independence(self):
        px, py, pz = self.pose(PARENT)
        self.set_pose(BOX_B, px + 0.30, py, pz - 0.20)
        time.sleep(0.1)
        self.publish('/probe/b/attach')
        time.sleep(0.2)
        self.publish('/probe/a/detach')
        time.sleep(0.1)
        a0, b0 = self.pose(BOX_A), self.pose(BOX_B)
        self.set_pose(PARENT, px + 0.05, py, pz)
        time.sleep(0.3)
        a1, b1 = self.pose(BOX_A), self.pose(BOX_B)
        self.set_pose(PARENT, px, py, pz)
        time.sleep(0.1)
        da, db = abs(a1[0] - a0[0]), b1[0] - b0[0]
        self.record('independent_channels', da < 0.01 and abs(db - 0.05) < 0.006,
                    'detached A moved %.4f m, attached B moved %+.4f m' % (da, db),
                    a_moved=da, b_moved=db)

    def check_contact_attach(self):
        """Rest the box on the parent, let contacts resolve, then attach.

        Documented as unsupported. Recorded, never asserted.
        """
        self.publish('/probe/a/detach')
        time.sleep(0.1)
        px, py, pz = self.pose(PARENT)
        self.set_pose(BOX_A, px, py, pz + 0.048)   # sits on top of the parent
        time.sleep(1.0)                            # let the contact settle
        resting = self.pose(BOX_A)
        self.publish('/probe/a/attach')
        time.sleep(0.3)
        ok, moved = self.follows(BOX_A)
        after = self.pose(BOX_A)
        jump = max(abs(a - b) for a, b in zip(after, resting))
        self.record('attach_while_in_contact[recorded]', True,
                    'resting z=%.4f, attached=%s, jump %.4f m, moved %+.4f m' %
                    (resting[2], ok, jump, moved),
                    asserted=False, resting_z=resting[2], attached=ok, jump=jump, moved=moved)

    def run_all(self):
        self.check_initial()
        self.check_freefall()
        self.check_reattach()
        self.check_rigidity()
        self.check_independence()
        self.check_contact_attach()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--world', default=DEFAULT_WORLD)
    ap.add_argument('--out', default='')
    ap.add_argument('--verbose', action='store_true')
    ap.add_argument('--keep-log', action='store_true')
    args = ap.parse_args(argv)

    spike = Spike(args.world, args.verbose, args.keep_log)
    payload = dict(world=os.path.basename(args.world), partition=spike.partition,
                   started=time.strftime('%Y-%m-%dT%H:%M:%S'),
                   findings=FINDINGS, checks=[])
    with open(args.world, 'rb') as stream:
        payload['world_sha256'] = hashlib.file_digest(stream, 'sha256').hexdigest()
    payload.update(scope='STATIC_PARENT_ONLY', default_admission='NO_GO', log=spike.log_path)
    rc = 0
    try:
        spike.start()
        spike.run_all()
        payload['checks'] = spike.results
        rc = 0 if all(r['passed'] for r in spike.results if r['asserted']) else 1
    except Exception as exc:                      # noqa: BLE001 - reported, not raised
        payload['error'] = str(exc)
        payload['checks'] = spike.results
        rc = 2
    finally:
        spike.stop()

    payload['status'] = {0: 'STATIC_PARENT_FUNCTIONAL_PASS', 1: 'CHECK_FAILED', 2: 'WORLD_FAILED'}[rc]
    payload['note'] = ('attach_while_in_contact is recorded, not asserted: the docs '
                       'say it is unsupported. What this spike measures is what the '
                       'installed build does, not what the documentation says.')
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if args.out:
        with open(args.out, 'w', encoding='utf-8') as fh:
            fh.write(text + '\n')
    print(text if args.verbose else '\n' + payload['status'])
    return rc


if __name__ == '__main__':
    sys.exit(main())
