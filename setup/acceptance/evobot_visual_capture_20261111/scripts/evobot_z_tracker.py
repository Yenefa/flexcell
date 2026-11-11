#!/usr/bin/env python3
"""Record object z height over time, and emit the trajectory evaluate.py needs.

WHY THIS EXISTS
    evaluate.py v0.4.0's push clause requires trajectory.<object>.max_z_m and
    FAILS CLOSED without it. End-state geometry cannot tell a push from a
    grasp-carry-place: pick the object up, carry it the required distance, set
    it back down at the same height, and every displacement check passes while
    the task ("without picking it up") was violated.

WHY DENSE SAMPLING, AND WHY THE COVERAGE IS REPORTED
    max_z is only as trustworthy as the sampling that produced it. A sparse
    sampler does not merely lack precision - it fails in ONE direction: it can
    MISS a lift, so it can only ever under-report max_z, which biases toward
    judging a carry as a push. That is the direction that produces a FALSE PASS.

    So this tool does not just emit a number. It records the achieved rate, the
    number of samples, and the largest gap between them, and states plainly how
    much motion could fit in that gap. A reader can then decide whether the
    evidence is strong enough instead of assuming it is.

WHY IT READS THE LIVE POSE STREAM RATHER THAN THE PICTURES
    The capture path (camera_snapshot.py) takes one frame at a moment. A lift
    that begins and ends between two captures is invisible to it. The pose
    stream is continuous, so it is the right source for a trajectory; the
    frames remain the diagnostic artefact. Keeping them separate means neither
    has to pretend to be the other.
"""
import argparse
import json
import sys
import time
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_NO_TRUTH = 2
EXIT_SAMPLED_NOTHING = 3


def summarise(series, requested_hz):
    """Per-object z statistics, with the sampling limits stated in the record."""
    objects = {}
    for name, samples in series.items():
        if not samples:
            continue
        zs = [z for _wall, z in samples]
        walls = [wall for wall, _z in samples]
        # wall_ns is NANOSECONDS. Convert once, here, so every rate and gap
        # below is in seconds. Reporting the raw nanosecond delta as "seconds"
        # made achieved_hz come out 1e9 too small - and a test caught it,
        # which is the point of computing the rate rather than assuming it.
        gaps = [(walls[i + 1] - walls[i]) / 1e9 for i in range(len(walls) - 1)]
        widest = max(gaps) if gaps else 0.0
        span = (walls[-1] - walls[0]) / 1e9 if len(walls) > 1 else 0.0
        achieved = (len(walls) - 1) / span if span > 0 else 0.0
        objects[name] = dict(
            max_z_m=round(max(zs), 6),
            min_z_m=round(min(zs), 6),
            first_z_m=round(zs[0], 6),
            last_z_m=round(zs[-1], 6),
            sample_count=len(zs),
            span_s=round(span, 4),
            achieved_hz=round(achieved, 3),
            requested_hz=float(requested_hz),
            max_sample_gap_s=round(widest, 4),
            source='GZ_GROUND_TRUTH_SAMPLED',
            # The honest limitation, inside the artefact rather than only in a
            # report about it.
            limit=('max_z_m is the maximum over %d samples at ~%.1f Hz; a lift '
                   'that began and ended inside the widest %.3fs gap is not '
                   'represented. Sparse sampling can only UNDER-report max_z, '
                   'which biases toward judging a carry as a push.'
                   % (len(zs), achieved, widest)),
        )
    return objects


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Record object z over time and emit the trajectory clause '
                    'input for evaluate.py v0.4.0.')
    parser.add_argument('--objects', nargs='+', required=True)
    parser.add_argument('--duration', type=float, default=60.0)
    parser.add_argument('--hz', type=float, default=20.0)
    parser.add_argument('--world', default='empty')
    parser.add_argument('--final-state', default=None,
                        help='write {objects, trajectory} for the evaluator')
    parser.add_argument('--series', default=None,
                        help='write the full per-object sample series')
    parser.add_argument('--start-z', nargs='*', default=None,
                        help='name=z pairs of the RESTING height, used to report '
                             'lift above rest rather than above the first sample')
    args = parser.parse_args(argv)

    if args.duration <= 0 or args.hz <= 0:
        print('REFUSED: duration and hz must be positive', file=sys.stderr)
        return EXIT_USAGE

    try:
        from flexcell_skills.common import sample_gz_pose_age as _sampler
    except Exception:                             # noqa: BLE001
        try:
            from flexcell_skills.common import sample_gz_pose as _plain

            def _sampler(name, timeout_s=0.5, world='empty', max_age_s=1.0):
                pose, error = _plain(name, timeout_s=timeout_s, world=world,
                                     max_age_s=max_age_s)
                return pose, 0.0, error
        except Exception as exc:                  # noqa: BLE001
            print('NO_TRUTH_SOURCE: %s: %s' % (type(exc).__name__, exc),
                  file=sys.stderr)
            return EXIT_NO_TRUTH

    series = {name: [] for name in args.objects}
    ages = {name: [] for name in args.objects}
    latest = {}
    errors = {}
    period = 1.0 / args.hz
    started = time.time_ns()
    deadline = time.monotonic() + args.duration
    samples_taken = 0
    while time.monotonic() < deadline:
        tick = time.monotonic()
        for name in args.objects:
            # max_age_s=0.0 would force a blocking wait per object; a short
            # freshness window returns the current entry immediately when the
            # stream is flowing, which is what makes ~20 Hz possible.
            pose, age, error = _sampler(name, timeout_s=0.5, world=args.world,
                                        max_age_s=1.0)
            if pose is None:
                errors[name] = error
                continue
            wall = time.time_ns()
            latest[name] = [round(float(v), 6) for v in pose[0]]
            series[name].append((wall, float(pose[0][2])))
            ages[name].append(float(age))
            samples_taken += 1
        elapsed = time.monotonic() - tick
        if elapsed < period:
            time.sleep(period - elapsed)

    trajectory = summarise(series, args.hz)
    for name, stats in trajectory.items():
        if ages.get(name):
            stats['max_sample_age_s'] = round(max(ages[name]), 4)
    if not trajectory:
        print('SAMPLED_NOTHING: no object pose was read in %.1fs (%s)'
              % (args.duration, json.dumps(errors)), file=sys.stderr)
        return EXIT_SAMPLED_NOTHING

    rest = {}
    for item in (args.start_z or []):
        if '=' in item:
            key, value = item.split('=', 1)
            try:
                rest[key] = float(value)
            except ValueError:
                print('REFUSED: bad --start-z %r' % item, file=sys.stderr)
                return EXIT_USAGE
    for name, stats in trajectory.items():
        base = rest.get(name)
        if base is not None:
            stats['rest_height_m'] = round(base, 6)
            stats['max_lift_above_rest_m'] = round(stats['max_z_m'] - base, 6)

    report = dict(
        record_kind='EVOBOT_Z_TRAJECTORY',
        written_wall_ns=time.time_ns(),
        recorded_span_s=round((time.time_ns() - started) / 1e9, 3),
        requested_hz=float(args.hz),
        objects=trajectory,
        # Say WHICH source this trajectory came from. A frame-derived series is
        # sparse by construction and must not be mistaken for this one.
        trajectory_source='DENSE_POSE_STREAM',
        final_poses=latest,
        errors=errors,
        scope=('Each max_z_m is the maximum of GROUND-TRUTH z sampled at about '
               'the stated rate over the stated span. It is evidence about '
               'whether the object stayed on the table, not a claim that the '
               'image was interpreted.'),
    )

    if args.series:
        Path(args.series).write_text(
            json.dumps({name: [dict(wall_ns=w, z_m=z) for w, z in rows]
                        for name, rows in series.items()},
                       indent=2, allow_nan=False) + '\n', encoding='utf-8')
    if args.final_state:
        # Exactly the fragment evaluate.py reads: objects + trajectory.
        Path(args.final_state).write_text(
            json.dumps({'objects': latest, 'trajectory': trajectory},
                       indent=2, sort_keys=True, allow_nan=False) + '\n',
            encoding='utf-8')
    print(json.dumps({'ok': True, 'objects': sorted(trajectory),
                      'samples': samples_taken,
                      'max_z': {n: s['max_z_m'] for n, s in trajectory.items()},
                      'final_state': args.final_state}))
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
