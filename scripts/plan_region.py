#!/usr/bin/env python3
"""Generate a read-only clear/restore plan from AprilTag capture files."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src/flexcell/flexcell_skills'))
from flexcell_skills.visual_region_plan import plan_region


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--observations', type=Path, required=True)
    parser.add_argument('--calibration', type=Path, required=True)
    parser.add_argument('--region', nargs=4, type=float, required=True,
                        metavar=('XMIN', 'XMAX', 'YMIN', 'YMAX'))
    parser.add_argument('--staging', nargs=2, type=float, action='append', default=[],
                        metavar=('X', 'Y'), help='candidate outside the region; may be repeated')
    parser.add_argument('--position-margin-m', type=float, default=.010)
    parser.add_argument('--out', type=Path, help='optional new plan file; never overwritten')
    args = parser.parse_args(argv)
    try:
        observations = args.observations.read_bytes()
        calibration = args.calibration.read_bytes()
        report = plan_region(json.loads(observations), json.loads(calibration),
                             args.region, args.staging, args.position_margin_m)
        report['input_sha256'] = dict(observations=hashlib.sha256(observations).hexdigest(),
                                      calibration=hashlib.sha256(calibration).hexdigest())
        rc = 0
    except (OSError, ValueError, KeyError, TypeError, OverflowError) as exc:
        report = dict(status='UNAVAILABLE', reason=str(exc), execution_ready=False,
                      motion_dispatched=False)
        rc = 1
    encoded = json.dumps(report, indent=2, allow_nan=False) + '\n'
    if args.out:
        try:
            with args.out.open('x') as stream:
                stream.write(encoded)
        except OSError as exc:
            parser.exit(2, str(exc) + '\n')
    print(encoded, end='')
    return rc


if __name__ == '__main__':
    raise SystemExit(main())
