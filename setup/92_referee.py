#!/usr/bin/env python3
"""Independent referee for the Week-1 demo (M2.3 audit P1-6).

The batteries gate on fields the servers report about themselves - the audit
showed exactly why that is not enough (the PLACE ghost success passed every
self-reported gate).  This tool recomputes the two headline measured values
from the raw gz ground-truth stream, OUTSIDE any skill server, and
cross-checks them against the servers' own jsonl:

  referee_box_rise_m   = max(z during run) - z_rest          vs pick.jsonl   box_rise_m
  referee_zone_error_m = dist(final position, zone pose)     vs place.jsonl  place_error_m

Usage (ROS env sourced, stack running):
  python3 setup/92_referee.py --object target_box_a --zone 0.12 -0.15 0.0175 --demo
  python3 setup/92_referee.py --object target_box_a --zone 0.12 -0.15 0.0175 \
      --window 40            # observe an externally triggered run

Exit 0 = CONSISTENT (referee and server agree within --tol), 1 = INCONSISTENT
or run failure.  Every verdict is appended to the referee jsonl log.
"""
import argparse
import json
import math
import os
import subprocess
import sys
import threading
import time
import uuid

from flexcell_skills.common import sample_gz_pose

ROS_LOG = os.path.expanduser('~/.ros/flexcell')


def median(xs):
    s = sorted(xs)
    n = len(s)
    if n == 0:
        return None
    return s[n // 2] if n % 2 else 0.5 * (s[n // 2 - 1] + s[n // 2])


class BoxRecorder(threading.Thread):
    """5 Hz ground-truth sampler for one object, independent of the servers."""

    def __init__(self, object_name, hz=5.0):
        super().__init__(daemon=True)
        self.object_name = object_name
        self.period = 1.0 / hz
        self.samples = []          # (t, [x, y, z])
        self.stop_evt = threading.Event()
        self.err = None

    def run(self):
        while not self.stop_evt.is_set():
            t0 = time.monotonic()
            try:
                got, err = sample_gz_pose(self.object_name, timeout_s=4.0)
            except Exception as exc:  # noqa: BLE001
                self.err = 'recorder exception: %r' % exc
                break
            if got is not None:
                self.samples.append((time.monotonic(), got[0]))
            elif err and 'not seen in pose stream' in err:
                self.err = err
            time.sleep(max(0.0, self.period - (time.monotonic() - t0)))

    def stop(self):
        self.stop_evt.set()
        self.join(timeout=6.0)


def last_jsonl(path, pred):
    if not os.path.exists(path):
        return None
    found = None
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if pred(rec):
                found = rec
    return found


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--object', required=True)
    ap.add_argument('--zone', nargs=3, type=float, required=True,
                    metavar=('X', 'Y', 'Z'))
    ap.add_argument('--demo', action='store_true',
                    help='run the week1 demo as a subprocess')
    ap.add_argument('--scenario', default='')
    ap.add_argument('--window', type=float, default=45.0,
                    help='observe window when not running --demo')
    ap.add_argument('--tol', type=float, default=0.02,
                    help='referee-vs-server agreement tolerance (m)')
    args = ap.parse_args()

    rec = BoxRecorder(args.object)
    rec.start()
    time.sleep(2.0)   # settle: capture the at-rest position first

    demo_rc, demo_out = None, ''
    if args.demo:
        ws = os.environ.get('FLEXCELL_WS', os.getcwd())
        client = os.path.join(
            ws, 'src/flexcell/flexcell_skills/test/w1_client.py')
        scen = args.scenario or ('referee_%s' % uuid.uuid4().hex[:6])
        proc = subprocess.run(
            ['python3', client, '--action', 'demo', '--scenario', scen],
            capture_output=True, text=True, timeout=200)
        demo_rc = proc.returncode
        demo_out = proc.stdout[-2000:] + proc.stderr[-500:]
    else:
        time.sleep(args.window)

    rec.stop()

    verdict = {
        'tool': 'referee', 'ts': time.time(),
        'object': args.object,
        'zone': list(args.zone), 'tol_m': args.tol,
        'demo_rc': demo_rc, 'samples': len(rec.samples),
        'recorder_error': rec.err,
    }
    fail = ['recorder produced <8 samples' if len(rec.samples) < 8 else None,
            rec.err if rec.err else None]
    if args.demo:
        # judge the demo by the SERVER's structured record, not the client
        # process rc (the client has its own timeout/exit quirks); rc is
        # reported for information only.  The LAST record must be a success:
        # matching "any SUCCEEDED record" would let a failed run pass on a
        # stale earlier success (f4_referee_3 finding).
        demo_rec = last_jsonl(os.path.join(ROS_LOG, 'demo_runs.jsonl'),
                              lambda r: True)
        if demo_rec is None or str(demo_rec.get('outcome')) != '0':
            fail.append('last demo_runs.jsonl record is not SUCCEEDED (%s)'
                        % (demo_rec.get('outcome') if demo_rec else 'none'))

    checks = []
    if len(rec.samples) >= 8:
        z_start = median([p[2] for _, p in rec.samples[:5]])
        z_max = max(p[2] for _, p in rec.samples)
        final = [
            median([p[0] for _, p in rec.samples[-5:]]),
            median([p[1] for _, p in rec.samples[-5:]]),
            median([p[2] for _, p in rec.samples[-5:]])]
        ref_rise = z_max - z_start
        ref_zone_err = math.dist(final, args.zone)

        pick = last_jsonl(os.path.join(ROS_LOG, 'pick.jsonl'),
                          lambda r: r.get('object_name') == args.object
                          and 'box_rise_m' in r)
        place = last_jsonl(os.path.join(ROS_LOG, 'place.jsonl'),
                           lambda r: r.get('object_name') == args.object
                           and 'place_error_m' in r)
        # Referee rise = the box's max z from just before pick completion to
        # the end of the run (the carry plateau), minus the at-rest z.  This
        # is an INTEGRITY check, not a servo-timing check: the teleport-servo
        # engagement is a declared compromise with seconds-scale, erratic
        # catch-up (D4 in docs/P2_DECISION_MEMO.md), so a server rise BELOW
        # the eventual plateau is honest mechanics, not dishonesty.  What the
        # referee fails: the server claiming MORE rise than the physics ever
        # showed (ghost/fabricated class), or a rise below the pick's own
        # fake-grasp guard while still claiming success.
        ref_rise = z_max - z_start
        if pick is not None and pick.get('wall_ts'):
            pw = float(pick['wall_ts'])
            win = [p[2] for t, p in rec.samples if t >= pw - 2.0]
            if win:
                ref_rise = max(win) - z_start
        verdict.update(z_start=z_start, z_max=z_max, final=final,
                       referee_box_rise_m=ref_rise,
                       referee_zone_error_m=ref_zone_err)

        if pick is None:
            fail.append('no pick.jsonl record for %s' % args.object)
        else:
            srv_rise = float(pick['box_rise_m'])
            # overclaim: server reports a rise the physics never showed
            over = srv_rise - ref_rise
            # fake-grasp guard: a SUCCEEDED pick reports at least its own
            # box_follow_min (week1.yaml box_follow_min_m = 0.03)
            follow_min = 0.03
            if over > args.tol:
                fail.append('box_rise overclaim: server %.4f > referee '
                            'plateau %.4f + tol' % (srv_rise, ref_rise))
            elif 0 <= srv_rise < follow_min:
                fail.append('box_rise %.4f below fake-grasp guard %.2f '
                            'while claiming success' % (srv_rise, follow_min))
            checks.append(('box_rise(overclaim)', ref_rise, srv_rise,
                           max(0.0, over), over <= args.tol))
            verdict['rise_catchup_delta_m'] = max(0.0, ref_rise - srv_rise)
        if place is None:
            fail.append('no place.jsonl record for %s' % args.object)
        else:
            d = abs(ref_zone_err - float(place['place_error_m']))
            ok = d <= args.tol
            checks.append(('zone_error', ref_zone_err,
                           place['place_error_m'], d, ok))
            if not ok:
                fail.append('zone_error delta %.4f > tol' % d)

    verdict['checks'] = [
        {'name': n, 'referee': round(r, 4), 'server': round(s, 4),
         'delta': round(d, 4), 'consistent': ok} for n, r, s, d, ok in checks]
    fail = [f for f in fail if f]
    verdict['verdict'] = 'INCONSISTENT' if fail else 'CONSISTENT'
    verdict['failures'] = fail

    out = json.dumps(verdict, indent=2)
    print(out)
    if args.demo and demo_out:
        # pass the client transcript through so battery scripts that grep the
        # demo result fields keep working on the referee-wrapped transcript
        print('--- demo client output (tail) ---')
        print(demo_out)
    log = os.path.join(ROS_LOG, 'referee.jsonl')
    try:
        with open(log, 'a') as fh:
            fh.write(json.dumps(verdict) + '\n')
    except OSError as exc:  # noqa: BLE001
        print('referee log write failed: %s' % exc, file=sys.stderr)
    sys.exit(0 if not fail else 1)


if __name__ == '__main__':
    main()
