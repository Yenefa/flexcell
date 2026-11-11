#!/usr/bin/env python3
"""Pair every captured frame with the ground truth measured at that instant.

WHY THIS EXISTS
    A picture is not evidence that the robot saw anything. The only way a later
    visual judgement can be checked is if, for every frame, there is an
    independent record of where the objects ACTUALLY were when that frame was
    taken. Then a claim like "the red block is in the left bin" can be scored
    against truth instead of trusted.

WHAT IT PAIRS, AND WHY THE PAIRING IS NOT TRIVIAL
    The frame carries a Gazebo simulation stamp; the ground truth is sampled
    from the gz Pose_V stream over wall time. The two clocks are not the same
    clock, so this tool does NOT pretend they are:

      * every frame gets the truth sample that was taken CLOSEST in wall time,
        together with that sample's age relative to the frame;
      * the age is recorded, not hidden. A pairing whose gap exceeds the
        caller's limit is written as unpaired with a named reason, because a
        truth sample from 2 s away describes a different world than the frame.

    The consequence is stated plainly in the output: a paired record means
    "truth was measured within N ms of this frame", never "this is exactly what
    is in the picture".

WHAT IT REFUSES TO DO
    * It never invents a pose for an object that was not measured.
    * It never pairs a frame with truth from after the fact without saying so.
    * It never overwrites an existing pairing record (--force required).
    * It exits non-zero when a frame has no acceptable truth: a pairing file
      full of nulls that still reports success is the failure mode this tool
      exists to prevent.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

EXIT_OK = 0
EXIT_USAGE = 1
EXIT_NO_FRAMES = 2
EXIT_UNPAIRED = 3
EXIT_TRUTH_UNAVAILABLE = 4

DEFAULT_MAX_GAP_S = 1.0


def load_sidecar(png_path):
    """The snapshot tool writes <png>.json next to the image; read it strictly."""
    sidecar = Path(str(png_path) + '.json')
    if not sidecar.is_file():
        return None, 'sidecar missing: ' + str(sidecar)
    try:
        record = json.loads(sidecar.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        return None, 'sidecar unreadable: %s: %s' % (type(exc).__name__, exc)
    if not isinstance(record, dict) or not record.get('ok'):
        return None, 'sidecar does not describe a successful capture'
    return record, None


def discover_frames(directory):
    """Every captured PNG under a directory, in a stable order."""
    return sorted(p for p in Path(directory).rglob('*.png')
                  if p.is_file() and not p.name.endswith('.partial'))


def truth_from_sidecar(frame_record):
    """Truth sampled by the snapshot tool right after the frame, if it did.

    Preferred over any external sample because its gap to the frame is the one
    the snapshot tool actually measured, not one reconstructed afterwards.
    """
    truth = frame_record.get('truth')
    if not isinstance(truth, dict) or not truth.get('available'):
        return None
    if not isinstance(truth.get('objects'), dict) or not truth['objects']:
        return None
    return [dict(wall_ns=truth.get('wall_ns'),
                 source=truth.get('source', 'GZ_GROUND_TRUTH'),
                 objects=truth['objects'])]


def pair_one(frame_record, truth_samples, max_gap_s=DEFAULT_MAX_GAP_S):
    """Attach the closest-in-wall-time truth sample to one frame.

    truth_samples: [{'wall_ns': int, 'objects': {name: [x,y,z]}, 'source': str}]

    Returns (pairing, None) or (None, reason). A pairing that would be a lie is
    refused here rather than annotated and passed on.
    """
    captured = frame_record.get('captured_wall_ns')
    if not isinstance(captured, int):
        return None, 'frame record has no captured_wall_ns'
    if not truth_samples:
        return None, 'no truth samples were taken'
    best, best_gap = None, None
    for sample in truth_samples:
        wall = sample.get('wall_ns')
        if not isinstance(wall, int):
            continue
        gap = abs(wall - captured) / 1e9
        if best_gap is None or gap < best_gap:
            best, best_gap = sample, gap
    if best is None:
        return None, 'no truth sample carried a usable wall_ns'
    if best_gap > max_gap_s:
        return None, ('closest truth sample is %.3fs away, beyond the %.3fs '
                      'limit; a pose from another moment does not describe this '
                      'frame' % (best_gap, max_gap_s))
    objects = best.get('objects') or {}
    if not objects:
        return None, 'closest truth sample contains no objects'
    return dict(
        frame=str(frame_record.get('path')),
        label=frame_record.get('label', ''),
        png_sha256=frame_record.get('sha256'),
        png_bytes=frame_record.get('png_bytes'),
        width=frame_record.get('width'),
        height=frame_record.get('height'),
        sim_stamp_ns=frame_record.get('stamp_ns'),
        captured_wall_ns=captured,
        truth_wall_ns=best['wall_ns'],
        pairing_gap_s=round(best_gap, 6),
        truth_source=best.get('source', 'UNKNOWN'),
        # Truth as measured, per object. Absent means absent: never filled in.
        objects={name: list(pose) for name, pose in objects.items()},
    ), None


def trajectory_from_pairs(pairs):
    """Per-object z over the captured frames, shaped for the evaluator.

    WHY THIS EXISTS
        evaluate.py v0.4.0 needs final_state['trajectory'][name]['max_z_m'] to
        tell a push from a grasp-carry-place: end-state geometry cannot, because
        lifting the object, carrying it the required distance and putting it
        back down at the same height passes every displacement check while
        violating the task. The clause FAILS CLOSED, so without a trajectory the
        task can never pass however correct the run was.

    WHY IT CARRIES ITS OWN LIMITS
        max_z here is the maximum over SAMPLED frames, not over continuous
        motion. A lift that began and ended between two captures would be
        invisible. So the record states the sample count and the largest gap
        between consecutive samples. A reader can then see how much motion could
        have hidden in the gaps instead of assuming none did - which is the
        difference between this and a number that merely looks reassuring.
    """
    ordered = sorted((p for p in pairs if isinstance(p.get('captured_wall_ns'), int)),
                     key=lambda p: p['captured_wall_ns'])
    series, gaps = {}, {}
    previous_wall = None
    for pair in ordered:
        wall = pair['captured_wall_ns']
        if previous_wall is not None:
            gaps.setdefault('_all', []).append((wall - previous_wall) / 1e9)
        previous_wall = wall
        for name, pose in (pair.get('objects') or {}).items():
            if not isinstance(pose, (list, tuple)) or len(pose) != 3:
                continue
            series.setdefault(name, []).append(float(pose[2]))
    all_gaps = gaps.get('_all', [])
    widest = round(max(all_gaps), 6) if all_gaps else None
    trajectory = {}
    for name, zs in series.items():
        if not zs:
            continue
        trajectory[name] = dict(
            max_z_m=round(max(zs), 6),
            min_z_m=round(min(zs), 6),
            first_z_m=round(zs[0], 6),
            last_z_m=round(zs[-1], 6),
            sample_count=len(zs),
            max_sample_gap_s=widest,
            source='GZ_GROUND_TRUTH_SAMPLED',
            # Stated in the artefact, not only in a report about it.
            limit=('max_z_m is the maximum over %d sampled frames; motion that '
                   'began and ended inside the widest %.3fs gap is not '
                   'represented' % (len(zs), widest or 0.0)))
    return trajectory


def build_report(pairs, unpaired, frames_seen, max_gap_s):
    """The pairing artefact. Self-describing, so a reader needs no other file."""
    return dict(
        record_kind='EVOBOT_VISUAL_TRUTH_PAIRING',
        written_wall_ns=time.time_ns(),
        frames_seen=int(frames_seen),
        frames_paired=len(pairs),
        frames_unpaired=len(unpaired),
        max_gap_s=float(max_gap_s),
        # The scope statement belongs IN the artefact, not only in a report
        # about it: a reader who finds this file alone must not over-read it.
        scope=('Each pair means: ground-truth object poses were measured within '
               'max_gap_s of the moment this frame was captured. It does NOT '
               'mean the frame has been interpreted, that anything in it was '
               'recognised, or that the robot can see.'),
        pairs=pairs,
        unpaired=unpaired,
        # Shape-compatible with evaluate.py v0.4.0's
        # final_state['trajectory'][name]['max_z_m']. The evaluator fails
        # closed without it, so this is evidence the grade depends on, not
        # decoration.
        trajectory=trajectory_from_pairs(pairs),
    )


def gather_truth(names, world='empty', timeout_s=8.0):
    """One ground-truth sample through the same sampler the skills use."""
    sys.path.insert(0, os.environ.get(
        'FLEXCELL_SKILLS_PATH',
        '/home/ros/flexcell-p14/src/flexcell/flexcell_skills'))
    from flexcell_skills.common import sample_gz_pose
    objects, errors = {}, {}
    for name in names:
        pose, error = sample_gz_pose(name, timeout_s=timeout_s, world=world)
        if pose is None:
            errors[name] = error
            continue
        objects[name] = [round(float(v), 6) for v in pose[0]]
    return dict(wall_ns=time.time_ns(), source='GZ_GROUND_TRUTH',
                objects=objects, errors=errors)


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Pair captured frames with ground truth measured at the '
                    'same moment.')
    parser.add_argument('--frames', required=True,
                        help='directory of captured PNGs (searched recursively)')
    parser.add_argument('--truth', default=None,
                        help='JSON file with one or more truth samples; if '
                             'omitted, one live sample is taken now')
    parser.add_argument('--objects', nargs='*', default=None,
                        help='object names for the live truth sample')
    parser.add_argument('--world', default='empty')
    parser.add_argument('--out', required=True, help='pairing JSON path')
    parser.add_argument('--max-gap', type=float, default=DEFAULT_MAX_GAP_S,
                        help='maximum |frame - truth| in seconds (default 1.0)')
    parser.add_argument('--force', action='store_true',
                        help='overwrite an existing pairing file')
    parser.add_argument('--allow-unpaired', action='store_true',
                        help='write the report even when some frames have no '
                             'truth (the report still exits non-zero)')
    args = parser.parse_args(argv)

    out = Path(args.out)
    if out.exists() and not args.force:
        print('REFUSED: %s already exists (use --force to overwrite)' % out,
              file=sys.stderr)
        return EXIT_USAGE

    frames = discover_frames(args.frames)
    if not frames:
        print('NO_FRAMES: no *.png under %s' % args.frames, file=sys.stderr)
        return EXIT_NO_FRAMES

    samples = []
    if args.truth:
        blob = json.loads(Path(args.truth).read_text(encoding='utf-8'))
        samples = blob['samples'] if isinstance(blob, dict) and 'samples' in blob else blob
        if isinstance(samples, dict):
            samples = [samples]
    elif args.objects:
        samples = [gather_truth(args.objects, args.world)]
        if not samples[0]['objects']:
            print('TRUTH_UNAVAILABLE: %s'
                  % json.dumps(samples[0].get('errors', {})), file=sys.stderr)
            return EXIT_TRUTH_UNAVAILABLE
    else:
        # Allowed only if every sidecar carries its own truth sample; checked
        # per frame below, and a frame without one is reported unpaired rather
        # than paired with nothing.
        carried = sum(1 for png in frames
                      if truth_from_sidecar(load_sidecar(png)[0] or {}))
        if not carried:
            print('REFUSED: no --truth, no --objects, and no sidecar carries a '
                  'truth sample; this tool will not pair frames with truth it '
                  'never measured', file=sys.stderr)
            return EXIT_USAGE

    pairs, unpaired = [], []
    for png in frames:
        record, error = load_sidecar(png)
        if record is None:
            unpaired.append({'frame': str(png), 'reason': error})
            continue
        # A sidecar that carries its own in-process truth sample is the
        # stronger evidence: use it in preference to an external file.
        own = truth_from_sidecar(record)
        pairing, reason = pair_one(record, own or samples, args.max_gap)
        if pairing is None:
            unpaired.append({'frame': str(png),
                             'label': record.get('label', ''),
                             'reason': reason})
        else:
            pairs.append(pairing)

    report = build_report(pairs, unpaired, len(frames), args.max_gap)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False)
                   + '\n', encoding='utf-8')

    # A second file, shaped exactly as the evaluator's final_state fragment, so
    # whoever grades does not have to re-derive the shape from this script.
    trajectory_path = Path(str(out) + '.trajectory.json')
    trajectory_path.write_text(
        json.dumps(report['trajectory'], indent=2, sort_keys=True,
                   allow_nan=False) + '\n', encoding='utf-8')

    print(json.dumps({'ok': not unpaired, 'frames': len(frames),
                      'paired': len(pairs), 'unpaired': len(unpaired),
                      'trajectory_objects': sorted(report['trajectory']),
                      'out': str(out),
                      'trajectory_out': str(trajectory_path)}))
    if unpaired and not args.allow_unpaired:
        print('UNPAIRED: %d of %d frames have no acceptable truth'
              % (len(unpaired), len(frames)), file=sys.stderr)
        return EXIT_UNPAIRED
    return EXIT_OK if not unpaired else EXIT_UNPAIRED


if __name__ == '__main__':
    sys.exit(main())
