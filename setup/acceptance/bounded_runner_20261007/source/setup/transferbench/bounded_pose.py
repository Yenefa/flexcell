"""Isolated Gazebo pose update for the registered demo boxes."""
import argparse
import importlib.util
import json
import math
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--object', choices=('target_box_a', 'target_box_b'), required=True)
    parser.add_argument('--xyz', type=float, nargs=3, required=True)
    args = parser.parse_args()
    x, y, z = args.xyz
    if not all(math.isfinite(v) for v in args.xyz) or not (.16 <= x <= .28 and -.24 <= y <= .20 and z == .0175):
        raise ValueError('registered ground-plane placement outside bounds')
    spec = importlib.util.spec_from_file_location('pose_helper', Path(__file__).resolve().parents[1] / '96_s7_perturb.py')
    helper = importlib.util.module_from_spec(spec); spec.loader.exec_module(helper)
    ok = helper.gz_set_pose(args.object, args.xyz)
    print(json.dumps({'ok': ok is True, 'object': args.object, 'xyz': args.xyz}), flush=True)
    return 0 if ok is True else 2


if __name__ == '__main__':
    raise SystemExit(main())
