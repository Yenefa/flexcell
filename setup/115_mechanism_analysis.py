#!/usr/bin/env python3
"""Recompute bounded probe counts, ballistic fits and a scientific figure."""
import argparse
import json
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def read_rows(path):
    return [json.loads(line) for line in path.read_text().splitlines() if line]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--root', required=True, type=Path)
    args = ap.parse_args()
    root = args.root
    # Early overlapping focused/stagger runs are explicitly excluded.
    cohorts = ('dds_initial', 'dds_udp', 'dds_default_repeat', 'dds_mtu1400', 'dds_mtu1400_repeat')
    natural, injections = [], []
    for cohort in cohorts:
        for path in sorted((root / cohort).glob('*/summary.json')):
            data = json.loads(path.read_text())
            row = dict(cohort=cohort, case=path.parent.name, rmw=data['rmw'],
                fault=data['fault'], trials=len(data['rows']),
                first_missed=data['first_missed'], final_missed=data['final_missed'],
                scene_unavailable=data['scene_unavailable'],
                evidence_mismatches=sum(not r.get('evidence_matches', False) for r in data['rows']))
            events = read_rows(path.parent / 'server.jsonl')
            row['server_executions'] = sum(r['event'] == 'server_execute' for r in events)
            row['injected_drops'] = sum(r['event'] == 'injected_response_drop' for r in events)
            row['fault_reached'] = data['fault'] == 'none' or row['injected_drops'] > 0
            (natural if data['fault'] == 'none' else injections).append(row)
    totals = {rmw: dict(trials=sum(r['trials'] for r in natural if r['rmw']==rmw),
                        first_missed=sum(r['first_missed'] for r in natural if r['rmw']==rmw),
                        final_missed=sum(r['final_missed'] for r in natural if r['rmw']==rmw))
              for rmw in sorted(set(r['rmw'] for r in natural))}
    (root / 'dds_counts.json').write_text(json.dumps(dict(
        scope='Completed virtual goals only; startup failures and process timeouts are separate, not successes.',
        natural=natural, totals=totals, injected=injections), indent=2)+'\n')

    baseline = read_rows(root / 'servo_initial/trace.jsonl')
    velocity_control = read_rows(root / 'servo_velocity_control_retry/trace.jsonl')

    def window(rows, name):
        commands = [r for r in rows if r['kind']=='command' and r['name']==name]
        start = min(r['mono_ns'] for r in commands)
        # The probe requested a 3-second wall window; simulator timestamps drive the physics fit.
        poses = [r for r in rows if r['kind']=='pose' and r['name']==name
                 and start <= r['mono_ns'] < start + 3_000_000_000]
        return poses

    fits = []
    for name in ('probe_box_08', 'probe_box_09'):
        poses = window(baseline, name)
        segments, current = [], []
        for pose in poses:
            if current and pose['xyz'][2] - current[-1]['xyz'][2] > .005:
                segments.append(current)
                current = []
            current.append(pose)
        if current:
            segments.append(current)
        arcs = []
        for segment in segments:
            if len(segment) < 3:
                continue
            origin = segment[0]['sim_ns'] / 1e9
            t = np.array([p['sim_ns']/1e9-origin for p in segment])
            z = np.array([p['xyz'][2] for p in segment])
            velocity, intercept = np.polyfit(t, z + 4.9*t*t, 1)
            rmse = np.sqrt(np.mean((z-(intercept+velocity*t-4.9*t*t))**2))
            arcs.append(dict(sim_start_s=origin, velocity_at_start_m_s=float(velocity),
                             rmse_m=float(rmse), samples=len(segment)))
        slope, _ = np.polyfit([a['sim_start_s'] for a in arcs],
                             [a['velocity_at_start_m_s'] for a in arcs], 1)
        fits.append(dict(name=name, segments=arcs, velocity_slope_vs_sim_age_m_s2=float(slope),
                         largest_ballistic_fit_rmse_m=max(a['rmse_m'] for a in arcs)))
    (root / 'velocity_fit_recomputed.json').write_text(json.dumps(dict(
        method='Position-inferred velocity using simulator time; not direct velocity telemetry.',
        cases=fits), indent=2)+'\n')

    fig, axes = plt.subplots(2, 2, figsize=(11, 7), layout='constrained')
    comparisons = [(baseline, 'probe_box_01', 'Gravity + contacts, 10 Hz pose reset'),
                   (baseline, 'probe_box_05', 'Gravity off, same 10 Hz pose reset'),
                   (baseline, 'probe_box_09', 'Gravity on, contacts off, 10 Hz pose reset'),
                   (velocity_control, 'probe_box_01', 'Gravity + contacts + zero velocity each step')]
    for ax, (rows, name, title) in zip(axes.flat, comparisons):
        poses = window(rows, name)
        first = poses[0]['sim_ns']
        ax.plot([(p['sim_ns']-first)/1e9 for p in poses], [p['xyz'][2] for p in poses], lw=1)
        ax.axhline(.1175, color='green', ls='--', label='command z = 0.1175 m')
        ax.axhline(.0475, color='red', ls=':', label='pick threshold z = 0.0475 m')
        ax.set(title=title, xlabel='Simulator time since first sample (s)', ylabel='Measured z (m)')
        ax.grid(alpha=.2)
        if 'contacts off' not in title:
            ax.set_ylim(-.02, .14)
    axes[0, 0].legend(fontsize=8, loc='lower right')
    fig.suptitle('Isolated mechanism probes: same box and 5 ms physics step; no robot or TF')
    fig.savefig(root / 'servo_mechanism.png', dpi=180)
    fig.savefig(root / 'servo_mechanism.pdf')
    print(json.dumps(dict(dds=totals, ballistic=[{k:v for k,v in f.items() if k!='segments'} for f in fits])))


if __name__ == '__main__':
    main()
