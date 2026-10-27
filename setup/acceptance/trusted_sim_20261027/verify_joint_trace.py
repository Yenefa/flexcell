#!/usr/bin/env python3
"""Check synchronous rigid-transform observations over every attached sample."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import zipfile


def rotate(q, v):
    x, y, z, w = q
    vx, vy, vz = v
    t = [2*(y*vz-z*vy), 2*(z*vx-x*vz), 2*(x*vy-y*vx)]
    return [vx+w*t[0]+y*t[2]-z*t[1], vy+w*t[1]+z*t[0]-x*t[2], vz+w*t[2]+x*t[1]-y*t[0]]


def multiply(a, b):
    x, y, z, w = a
    u, v, s, t = b
    return [w*u+x*t+y*s-z*v, w*v-x*s+y*t+z*u, w*s+x*v-y*u+z*t, w*t-x*u-y*v-z*s]


def verify(root):
    archive = root / 'joint-motion-traces.zip'
    manifest = json.loads((root / 'joint-motion-traces-manifest.json').read_text())
    assert archive.stat().st_size == manifest['bytes']
    assert hashlib.sha256(archive.read_bytes()).hexdigest() == manifest['sha256']
    report = dict(schema_version=1, status='SYNCHRONOUS_TRACE_VERIFIED', transition_samples_excluded=0, trials=[])
    with zipfile.ZipFile(archive) as bundle:
        assert bundle.testzip() is None
        window = json.loads(bundle.read('window.json'))
        assert window['status'] == 'FUNCTIONAL_WINDOW_PASS' and len(window['episodes']) == 2
        for index, episode in enumerate(window['episodes'], 1):
            prefix = 'trial-%02d/' % index
            result = json.loads(bundle.read(prefix + 'result.json'))
            assert result['status'] == 'PASS' and result['task']['object_at_place'] is True
            health = json.loads(bundle.read(prefix + 'health_after.stdout'))
            assert health['ok'] and health['hard_fail'] == [] and health['checks']['carry_engaged'] is False
            rows = [json.loads(line) for line in bundle.read(prefix + 'data/physics.jsonl').decode().splitlines()]
            name = episode['object']
            attached = [row for row in rows if row['objects'][name]['joint_component']]
            assert len(attached) > 100
            assert all(row['step_ns'] == 20_000_000 for row in attached)
            positions, rotations = [], []
            for row in attached:
                parent, child = row['parent_pose'], row['objects'][name]['pose']
                inverse = [-parent[3], -parent[4], -parent[5], parent[6]]
                positions.append(rotate(inverse, [child[i]-parent[i] for i in range(3)]))
                rotations.append(multiply(inverse, child[3:]))
            drift = max(math.dist(point, positions[0]) for point in positions)
            angles = []
            for q in rotations:
                dot = abs(sum(a*b for a, b in zip(q, rotations[0])))
                dot /= math.sqrt(sum(a*a for a in q) * sum(a*a for a in rotations[0]))
                angles.append(2*math.acos(min(1., dot)))
            assert drift < .005 and max(angles) < .05
            report['trials'].append(dict(object=name, attached_samples=len(attached),
                max_relative_position_drift_m=drift, max_relative_orientation_drift_rad=max(angles),
                final_position_error_m=result['task']['final_position_error_m']))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path)
    args = parser.parse_args()
    report = verify(Path(__file__).parent)
    if args.out:
        with args.out.open('x') as stream: json.dump(report, stream, indent=2); stream.write('\n')
    print(json.dumps(report, indent=2))
