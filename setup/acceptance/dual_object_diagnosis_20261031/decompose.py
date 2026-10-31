#!/usr/bin/env python3
"""Decompose the joint backend's placement error from one 2 ms physics trace.

Reads ``<run>/physics_steps.jsonl`` and reports, per object: the release height
above the target, the lateral error *at* release, the lateral speed at release,
and where the box actually landed before the harness resets the world.

The first attached frame of a session is deliberately ignored: the joint is
created one step earlier than the constraint settles, so a naive "first vs last"
comparison reports a ~0.12 m drift that never happened.
"""
import argparse
import glob
import json
import math


def load(path):
    with open(path) as stream:
        return [json.loads(line) for line in stream if line.strip()]


def longest_attached(rows, name):
    runs, current = [], []
    for row in rows:
        if row['objects'][name]['joint_component'] is True:
            current.append(row)
        elif current:
            runs.append(current)
            current = []
    if current:
        runs.append(current)
    return max(runs, key=len) if runs else []


def velocity(window, name):
    first, last = window[0], window[-1]
    dt = (last['sim_ns'] - first['sim_ns']) / 1e9
    if dt <= 0:
        return [0., 0., 0.]
    return [(last['objects'][name]['pose'][i] - first['objects'][name]['pose'][i]) / dt for i in range(3)]


def landed(rows, last_ns, name, settle_frames=200):
    tail = [row for row in rows if row['sim_ns'] > last_ns]
    history = []
    for previous, current in zip(tail, tail[1:]):
        history.append(math.dist(previous['objects'][name]['pose'][:3],
                                 current['objects'][name]['pose'][:3]))
        if len(history) > settle_frames and max(history[-settle_frames:]) < 1e-6:
            return current['objects'][name]['pose'][:3]
    return tail[-1]['objects'][name]['pose'][:3] if tail else None


def analyse(run, expected):
    rows = load(run + '/physics_steps.jsonl')
    report = dict(run=run, steps=len(rows),
                  sim_span_s=[rows[0]['sim_ns'] / 1e9, rows[-1]['sim_ns'] / 1e9], objects={})
    for name, target in expected.items():
        span = longest_attached(rows, name)
        if not span:
            report['objects'][name] = dict(attached=False)
            continue
        last = span[-1]
        release = last['objects'][name]['pose'][:3]
        speed = velocity(span[-25:], name)
        where = landed(rows, last['sim_ns'], name)
        report['objects'][name] = dict(
            attached=True, attached_s=(last['sim_ns'] - span[0]['sim_ns']) / 1e9,
            attached_steps=len(span),
            release_s=last['sim_ns'] / 1e9,
            release_lateral_error_mm=[round((release[0] - target[0]) * 1e3, 4),
                                      round((release[1] - target[1]) * 1e3, 4)],
            release_height_mm=round((release[2] - target[2]) * 1e3, 4),
            release_lateral_speed_m_s=round(math.hypot(speed[0], speed[1]), 6),
            landed=where,
            landed_error_mm=None if where is None else [
                round((where[0] - target[0]) * 1e3, 4), round((where[1] - target[1]) * 1e3, 4),
                round((where[2] - target[2]) * 1e3, 4)],
            scatter_after_release_mm=None if where is None else
            round(math.dist(release, where) * 1e3, 4))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('run', help='run directory, or a glob that resolves to one')
    parser.add_argument('--out')
    parser.add_argument('--target', action='append', default=[],
                        help='name=x,y,z (repeatable); defaults to the two demo boxes')
    args = parser.parse_args()
    matches = glob.glob(args.run)
    if not matches:
        raise SystemExit('no run matched %r' % args.run)
    expected = {name: [float(v) for v in value.split(',')]
                for name, _, value in (item.partition('=') for item in args.target)}
    if not expected:
        expected = {'target_box_a': [.12, -.15, .0175], 'target_box_b': [.25, .05, .0175]}
    report = analyse(matches[0], expected)
    text = json.dumps(report, indent=2, allow_nan=False)
    if args.out:
        from pathlib import Path
        Path(args.out).write_text(text + '\n')
    print(text)


if __name__ == '__main__':
    main()
