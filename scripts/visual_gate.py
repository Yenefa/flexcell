#!/usr/bin/env python3
"""Refuse a run whose frames cannot be tied to truth measured beside them.

WHY A GATE ON TOP OF THE PAIRING REPORT
    evobot_visual_vs_truth.py answers one question per frame: which ground-truth
    sample was taken closest to this capture, and how far away was it. That is a
    report, and a report can be read generously. It says nothing about whether
    every captured frame got an answer at all, and nothing about whether the
    objects the run claims to have worked on appear in the truth that was
    measured. So a run can hand over a pairing file, be described as "frames
    paired with truth", and still have: an empty frame list, no truth samples,
    frames without a capture time, or truth that never mentions the object the
    task was about.

    This gate turns those into a refusal instead of a footnote:

      * frames_0          -> NO_FRAMES
      * no truth at all   -> NO_TRUTH_SAMPLES
      * no wall-clock stamp on a frame -> FRAME_WITHOUT_CAPTURE_STAMP
      * a frame no sample comes near   -> FRAME_UNPAIRED (the tool's own reason)
      * a pose that is not a number    -> POSE_NOT_FINITE
      * a declared object absent       -> OBJECT_MISSING_FROM_TRUTH

    Pass means a receipt was written; fail means nothing was written, so the
    presence of visual_receipt.json is itself the pass signal.

WHAT THIS GATE DOES NOT DO, AND WHY THAT IS STATED IN THE RECEIPT
    It does not open a single PNG. It cannot tell a red block from a blue one,
    it does not segment anything, and it makes no claim that the robot can see.
    The claim it does make is narrow and checkable: every frame the run calls a
    capture has a wall-clock time, truth was measured within --max-gap of that
    time, and every object declared for the run appears in that truth. That is
    the premise a later visual judgement needs; it is not the judgement.

WHY IT IMPORTS THE PAIRING TOOL (scripts and tests live in different places)
    If this gate grew its own copy of the pairing rules, two implementations of
    "is this sample close enough" would drift, and an acceptance argument would
    rest on which one happened to run. The tool is imported by path (it is an
    acceptance script, not a package), so its rules stay the only rules.
"""
import argparse
import importlib.util
import json
import math
import sys
import time
from pathlib import Path

EXIT_OK = 0
EXIT_REFUSED = 1
EXIT_USAGE = 2

#: Same default as evobot_visual_vs_truth.py, so the gate cannot quietly accept
#: a pairing the pairing tool itself would refuse.
DEFAULT_MAX_GAP_S = 1.0

ROOT = Path(__file__).resolve().parents[1]
FRAMES_REL = Path('data') / 'frames.jsonl'
TRUTH_REL = Path('data') / 'truth_samples.json'
OBJECTS_REL = Path('data') / 'objects.json'
RECEIPT_NAME = 'visual_receipt.json'

#: Reason codes. Frozen strings: a caller greps for them, so they are constants
#: rather than text assembled at the failure site.
NO_FRAMES = 'NO_FRAMES'
NO_TRUTH_SAMPLES = 'NO_TRUTH_SAMPLES'
FRAME_WITHOUT_CAPTURE_STAMP = 'FRAME_WITHOUT_CAPTURE_STAMP'
FRAME_UNPAIRED = 'FRAME_UNPAIRED'
POSE_NOT_FINITE = 'POSE_NOT_FINITE'
OBJECT_MISSING_FROM_TRUTH = 'OBJECT_MISSING_FROM_TRUTH'
NO_DECLARED_OBJECTS = 'NO_DECLARED_OBJECTS'
PAIRING_TOOL_NOT_FOUND = 'PAIRING_TOOL_NOT_FOUND'
MALFORMED_INPUT = 'MALFORMED_INPUT'


def script_candidates():
    """Where the pairing tool may live, in search order.

    WHY TWO: the acceptance card that owns the tool was moved INTO this
    repository, which is what lets the gate run in a plain checkout; the sibling
    `ci-public-window` checkout is the maintainer's older layout and is kept only
    as a fallback. Both are named in the refusal, so a missing tool is
    diagnosable without reading this file.
    """
    return (
        ROOT / 'setup' / 'acceptance' / 'evobot_visual_capture_20261111' /
        'scripts' / 'evobot_visual_vs_truth.py',
        ROOT.parent / 'ci-public-window' / 'scripts' / 'evobot_visual_vs_truth.py',
    )


def pairing_script(explicit=None):
    """The pairing tool to import, or None when there is none to import."""
    if explicit:
        return Path(explicit) if Path(explicit).is_file() else None
    for candidate in script_candidates():
        if candidate.is_file():
            return candidate
    return None


def load_pairing(path):
    """Import the pairing tool from a path; it is not an importable package."""
    path = Path(path)
    spec = importlib.util.spec_from_file_location(path.stem, path)
    if spec is None or spec.loader is None:
        raise ValueError('cannot load a module from %s' % path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[path.stem] = module
    spec.loader.exec_module(module)
    return module


def read_jsonl(path):
    """Every non-empty line of a JSONL file, as dicts.

    WHY A HALF-WRITTEN LINE IS AN ERROR: the gate's claim is a count ("N frames
    were checked"). If the manifest is truncated, N is unknown, and grading the
    lines that happened to parse would overstate coverage.
    """
    rows = []
    with Path(path).open(encoding='utf-8') as stream:
        for number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError as exc:
                raise ValueError('line %d is not JSON: %s' % (number, exc))
            if not isinstance(row, dict):
                raise ValueError('line %d is not a frame record' % number)
            rows.append(row)
    return rows


def read_truth(path):
    """Truth samples from a JSON file: a list, a single sample, or {'samples': []}.

    The three shapes are the ones the pairing tool already accepts, so a file
    written for it does not have to be rewritten for the gate.
    """
    blob = json.loads(Path(path).read_text(encoding='utf-8'))
    if isinstance(blob, dict) and 'samples' in blob:
        blob = blob['samples']
    if isinstance(blob, dict):
        blob = [blob]
    if not isinstance(blob, list):
        raise ValueError('truth file is neither a list of samples nor {"samples": [...]}')
    if any(not isinstance(sample, dict) for sample in blob):
        raise ValueError('every truth sample must be an object')
    return blob


def frame_records(rows):
    """Rows as pairing-tool frame records, with the image field spelled 'path'.

    WHY THIS ADAPTATION EXISTS: data/frames.jsonl names the image 'image'
    (scripts/record_sim_data.py), while the pairing contract names it 'path'. The
    spelling is translated; no value is invented. A row that names neither keeps
    naming neither, so the tool's own refusal is what the caller sees.
    """
    records = []
    for row in rows:
        record = dict(row)
        if 'path' not in record and isinstance(record.get('image'), str):
            record['path'] = record['image']
        records.append(record)
    return records


def frame_id(record, index):
    """A stable name for a frame in the failure list."""
    for key in ('label', 'frame', 'path', 'image'):
        value = record.get(key)
        if isinstance(value, str) and value:
            return '#%d %s' % (index + 1, value)
    return '#%d' % (index + 1)


def pose_is_usable(pose):
    """A measured pose: exactly three finite numbers. Anything else is not one."""
    if not isinstance(pose, (list, tuple)) or len(pose) != 3:
        return False
    for value in pose:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            return False
        if not math.isfinite(value):
            return False
    return True


def unusable_poses(objects):
    """Objects whose pose is not three finite numbers, with what was found.

    WHY THIS IS NOT LEFT TO THE PAIRING TOOL: that tool copies objects through
    unchanged, which is correct for a recorder of measurements. A gate that will
    be quoted as "frames and truth are contemporaneous" cannot accept NaN: it
    cannot be written as strict JSON, and every comparison against it is
    meaningless in the same direction.
    """
    return [dict(object=name, pose=repr(objects[name]))
            for name in sorted(objects) if not pose_is_usable(objects[name])]


def declared_objects(run, override):
    """Object names the run claims to have worked on.

    WHY A DECLARATION IS REQUIRED: without one, "the declared objects appear in
    the truth" is a check over an empty set, which passes for a run whose truth
    mentions nothing at all. A gate that can pass without looking at the object
    the task was about is not a gate.
    """
    if override:
        return sorted({str(name) for name in override if str(name)})
    path = Path(run) / OBJECTS_REL
    if not path.is_file():
        return []
    blob = json.loads(path.read_text(encoding='utf-8'))
    if isinstance(blob, dict):
        blob = blob.get('objects', [])
    if not isinstance(blob, list):
        raise ValueError('%s is neither a list of names nor {"objects": [...]}' % path)
    return sorted({str(name) for name in blob if str(name)})


def check_frames(records, samples, pairing, declared, max_gap_s):
    """Per-frame verdicts, in the order the frames appear in the manifest.

    Returns (pairs, failures). A frame is paired only when the pairing tool
    accepts it AND the object list and pose values survive this gate's own
    checks; the three are separate failures because they mean different things
    (no truth nearby / truth exists but is unusable / truth exists and does not
    mention this object).
    """
    pairs, failures = [], []
    for index, record in enumerate(records):
        name = frame_id(record, index)
        captured = record.get('captured_wall_ns')
        if isinstance(captured, bool) or not isinstance(captured, int):
            failures.append(dict(code=FRAME_WITHOUT_CAPTURE_STAMP, frame=name,
                                 detail='frame record has no integer '
                                        'captured_wall_ns (found %r); a simulation '
                                        'stamp is not a wall clock and cannot be '
                                        'paired with wall-time truth' % (captured,)))
            continue
        carried = pairing.truth_from_sidecar(record)
        one_pairing, reason = pairing.pair_one(record, carried or samples, max_gap_s)
        if one_pairing is None:
            failures.append(dict(code=FRAME_UNPAIRED, frame=name, detail=str(reason)))
            continue
        broken = unusable_poses(one_pairing['objects'])
        if broken:
            failures.append(dict(code=POSE_NOT_FINITE, frame=name,
                                 detail='; '.join('%s=%s' % (item['object'], item['pose'])
                                                  for item in broken)))
            continue
        missing = [object_name for object_name in declared
                   if object_name not in one_pairing['objects']]
        if missing:
            failures.append(dict(code=OBJECT_MISSING_FROM_TRUTH, frame=name,
                                 detail='declared object(s) not measured in the paired '
                                        'truth: %s; the truth has %s'
                                        % (', '.join(missing),
                                           ', '.join(sorted(one_pairing['objects'])) or 'nothing')))
            continue
        pairs.append(dict(frame=name,
                          captured_wall_ns=captured,
                          truth_wall_ns=one_pairing['truth_wall_ns'],
                          pairing_gap_s=one_pairing['pairing_gap_s'],
                          truth_source=one_pairing['truth_source'],
                          objects=sorted(one_pairing['objects'])))
    return pairs, failures


def build_receipt(run, pairs, declared, max_gap_s, counts):
    """The pass artefact. Self-describing, so a reader needs no other file.

    The scope sentence is the point of the file: a receipt that looked like a
    visual verdict would be over-read by the next person who clicked it.
    """
    gaps = [pair['pairing_gap_s'] for pair in pairs]
    seen = sorted({name for pair in pairs for name in pair['objects']})
    return dict(
        record_kind='FLEXCELL_VISUAL_GATE_RECEIPT',
        written_wall_ns=time.time_ns(),
        run=str(Path(run).resolve()),
        # All three counts are recorded because they answer different questions:
        # how many rows the manifest holds, how many of those the recorder itself
        # refused, and how many were actually graded.
        frames_in_manifest=counts['in_manifest'],
        frames_skipped_invalid=counts['skipped_invalid'],
        frames_seen=counts['graded'],
        frames_paired=len(pairs),
        # Equal to 1.0 by construction: a run with one unpaired frame produces
        # failure output instead of this file. Recorded so a reader does not have
        # to infer the rule from the code.
        pairing_rate=round(len(pairs) / counts['graded'], 6) if counts['graded'] else 0.0,
        max_gap_s=float(max_gap_s),
        max_pairing_gap_s=round(max(gaps), 6) if gaps else None,
        objects=declared,
        objects_seen=seen,
        truth_sources=sorted({pair['truth_source'] for pair in pairs}),
        visual_appearance_judged=False,
        scope=('Each entry means: ground-truth object poses were measured within '
               'max_gap_s of the moment this frame was captured, and every object '
               'declared for the run appears in that truth. This receipt does NOT '
               'mean the frame was interpreted: no pixel was inspected, nothing in '
               'it was recognised, and no judgement about visual appearance '
               '(colour, shape, count, visibility) or about whether the robot can '
               'see was made.'),
        limits=('Frames are checked only through their recorded capture time; the '
                'gate does not open the images, does not verify their sha256, and '
                'does not detect motion between captures. A pairing gap up to '
                'max_gap_s is accepted as "the same moment", which is an interval, '
                'not an instant.'),
        frame_evidence=pairs,
    )


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Refuse a run unless every frame can be tied to ground truth '
                    'measured at the same moment and every declared object appears '
                    'in that truth. Writes visual_receipt.json only on success.')
    parser.add_argument('run', help='run directory (holds data/frames.jsonl)')
    parser.add_argument('--frames', default=None,
                        help='frame manifest (default: <run>/data/frames.jsonl)')
    parser.add_argument('--truth', default=None,
                        help='truth samples (default: <run>/data/truth_samples.json); '
                             'a list, one object, or {"samples": [...]}')
    parser.add_argument('--objects', nargs='*', default=None,
                        help='object names the run claims; default: '
                             '<run>/data/objects.json')
    parser.add_argument('--max-gap', type=float, default=DEFAULT_MAX_GAP_S,
                        help='maximum |frame - truth| in seconds (default %.1f)'
                             % DEFAULT_MAX_GAP_S)
    parser.add_argument('--out', default=None,
                        help='receipt path (default: <run>/visual_receipt.json)')
    parser.add_argument('--pairing-script', default=None,
                        help='pin the pairing tool instead of searching for it')
    parser.add_argument('--force', action='store_true',
                        help='overwrite an existing receipt')
    args = parser.parse_args(argv)

    run = Path(args.run)
    if not run.is_dir():
        print('REFUSED: run directory not found: %s' % run, file=sys.stderr)
        return EXIT_USAGE
    if not (args.max_gap > 0):
        print('REFUSED: --max-gap must be a positive duration', file=sys.stderr)
        return EXIT_USAGE

    out = Path(args.out) if args.out else run / RECEIPT_NAME
    if out.exists() and not args.force:
        print('REFUSED: %s already exists; a receipt records what was checked, so '
              'overwriting it would erase that (use --force)' % out, file=sys.stderr)
        return EXIT_USAGE

    script = pairing_script(args.pairing_script)
    if script is None:
        # Not a skipped check: a gate that cannot apply its rules must not pass.
        print('REFUSED: %s; this gate imports the pairing rules instead of keeping '
              'its own copy' % PAIRING_TOOL_NOT_FOUND, file=sys.stderr)
        if args.pairing_script:
            print('  --pairing-script %s is not a file' % args.pairing_script,
                  file=sys.stderr)
        for candidate in script_candidates():
            print('  looked for %s' % candidate, file=sys.stderr)
        return EXIT_USAGE
    pairing = load_pairing(script)

    frames_path = Path(args.frames) if args.frames else run / FRAMES_REL
    truth_path = Path(args.truth) if args.truth else run / TRUTH_REL

    if not frames_path.is_file():
        print('REFUSED: %s: %s does not exist, so there is no frame to check'
              % (NO_FRAMES, frames_path), file=sys.stderr)
        return EXIT_REFUSED
    try:
        rows = read_jsonl(frames_path)
    except (OSError, ValueError) as exc:
        print('REFUSED: %s: %s: %s' % (MALFORMED_INPUT, frames_path, exc),
              file=sys.stderr)
        return EXIT_USAGE
    if not rows:
        print('REFUSED: %s: %s holds no frame records; an empty manifest cannot '
              'be evidence that frames were captured' % (NO_FRAMES, frames_path),
              file=sys.stderr)
        return EXIT_REFUSED
    # A row the recorder marked invalid is a capture it refused to stand behind
    # (missing/stale telemetry), so it is not offered as a frame - the same rule
    # the pairing tool applies to a sidecar with ok=false. It is counted in the
    # receipt rather than dropped, so a reader sees how many rows were skipped.
    # A row that says nothing about validity is graded: absence of a refusal is
    # not a refusal.
    records = [record for record in frame_records(rows)
               if record.get('valid') is not False]
    counts = dict(in_manifest=len(rows), skipped_invalid=len(rows) - len(records),
                  graded=len(records))
    if not records:
        print('REFUSED: %s: all %d row(s) in %s are marked valid=false; a '
              'manifest of refused captures is not evidence that frames were '
              'captured' % (NO_FRAMES, len(rows), frames_path), file=sys.stderr)
        return EXIT_REFUSED

    samples = []
    if truth_path.is_file():
        try:
            samples = read_truth(truth_path)
        except (OSError, ValueError) as exc:
            print('REFUSED: %s: %s: %s' % (MALFORMED_INPUT, truth_path, exc),
                  file=sys.stderr)
            return EXIT_USAGE
    # "Carries its own truth" is the pairing tool's rule, not a second copy of
    # it: truth_from_sidecar already refuses an unavailable or empty sample.
    if not samples and not any(pairing.truth_from_sidecar(record)
                               for record in records):
        # A paired frame is a claim about a measurement. With nothing measured
        # and nothing carried, there is nothing to claim it against.
        print('REFUSED: %s: no truth sample in %s and no frame record carries its '
              'own truth' % (NO_TRUTH_SAMPLES, truth_path), file=sys.stderr)
        return EXIT_REFUSED

    try:
        declared = declared_objects(run, args.objects)
    except (OSError, ValueError) as exc:
        print('REFUSED: %s: %s' % (MALFORMED_INPUT, exc), file=sys.stderr)
        return EXIT_USAGE
    if not declared:
        print('REFUSED: %s: no object names were declared, so "the declared objects '
              'appear in the truth" would be a check over nothing; pass --objects or '
              'write %s' % (NO_DECLARED_OBJECTS, run / OBJECTS_REL), file=sys.stderr)
        return EXIT_USAGE

    pairs, failures = check_frames(records, samples, pairing, declared, args.max_gap)
    if failures:
        for failure in failures:
            print('FAILED: %s frame=%s: %s'
                  % (failure['code'], failure.get('frame', '-'), failure['detail']))
        print('REFUSED: %d of %d frame(s) did not satisfy the gate; no receipt was '
              'written' % (len(failures), len(records)), file=sys.stderr)
        return EXIT_REFUSED

    receipt = build_receipt(run, pairs, declared, args.max_gap, counts)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(receipt, indent=2, sort_keys=True, allow_nan=False) + '\n',
                   encoding='utf-8')
    print(json.dumps({'ok': True, 'out': str(out),
                      'frames': receipt['frames_seen'],
                      'frames_paired': receipt['frames_paired'],
                      'pairing_rate': receipt['pairing_rate'],
                      'max_pairing_gap_s': receipt['max_pairing_gap_s'],
                      'objects': receipt['objects'],
                      'pairing_script': str(script)}))
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
