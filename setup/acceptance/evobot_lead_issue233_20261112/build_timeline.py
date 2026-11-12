#!/usr/bin/env python3
# Issue #233: read-only pose/phase timeline. Inputs never written; output to a NEW dir.
# Guards, each from a failure actually seen here:
#  - duplicate snapshots (gz pose at 49 Hz, /observe on demand) must not be counted twice
#  - clock regression / out-of-order must be flagged, not smoothed
#  - boundaries are the LAST observed sample; no interpolation is manufactured
#  - same-window samples are co-occurrence only, never contact causality
import argparse, csv, json, math, os, sys
from collections import Counter

def fin(v):
    try: f = float(v)
    except (TypeError, ValueError): return None
    return f if math.isfinite(f) else None

def find_logs(root):
    """Both layouts in this tree: <run>/skills/*.jsonl and jsonl sitting directly in <run>/.

    The second form is what this session's own archiver produced, and missing it would make
    the tool report 'checked nothing' on runs that do have records. A checker that finds no
    input and exits clean is the defect this issue exists to prevent, so the caller treats an
    empty result as exit 2 rather than success.
    """
    hits = []
    for dp, _, names in os.walk(root):
        in_skills = os.path.basename(dp) == 'skills'
        for n in sorted(names):
            if not n.endswith('.jsonl'):
                continue
            hits.append(os.path.join(dp, n))
    return sorted(hits)

def load(paths):
    out = []
    for p in paths:
        try:
            fh = open(p, errors='replace')
        except OSError as e:
            out.append({'__src': p, '__err': str(e)}); continue
        for line in fh:
            line = line.strip()
            if not line: continue
            try: d = json.loads(line)
            except Exception:
                out.append({'__src': p, '__parse': True}); continue
            d['__src'] = os.path.basename(p)
            out.append(d)
        fh.close()
    return out

def build(recs, tol):
    rows, flags, seen, last = [], Counter(), Counter(), None
    for i, r in enumerate(recs):
        src = r.get('__src')
        if r.get('__parse'):
            flags['unparseable'] += 1
            rows.append({'idx': i, 'source': src, 'status': 'UNALIGNABLE', 'reason': 'not valid JSON'}); continue
        if r.get('__err'):
            flags['unreadable'] += 1
            rows.append({'idx': i, 'source': src, 'status': 'UNALIGNABLE', 'reason': 'file unreadable'}); continue
        phase = r.get('phase') or r.get('event')
        ts = fin(r.get('wall_ts'))
        if ts is None: ts = fin(r.get('t'))
        if ts is None: ts = fin(r.get('request_timestamp'))
        pos = r.get('position')
        if pos is None: pos = (r.get('reached_pose') or {}).get('position')
        ok = isinstance(pos, (list, tuple)) and len(pos) >= 3 and all(fin(v) is not None for v in pos[:3])
        if phase is None or ts is None or not ok:
            why = 'no phase' if phase is None else ('no finite ts' if ts is None else 'no finite pose')
            flags[why.replace(' ', '_')] += 1
            rows.append({'idx': i, 'source': src, 'phase': phase, 'status': 'UNALIGNABLE', 'reason': why}); continue
        sig = (phase, round(ts, 6), tuple(round(float(v), 6) for v in pos[:3]))
        seen[sig] += 1
        if seen[sig] > 1:
            flags['duplicate_snapshot'] += 1
            rows.append({'idx': i, 'source': src, 'phase': phase, 'status': 'DUPLICATE',
                         'reason': 'same phase+ts+pose as an earlier row'}); continue
        status, note = 'OK', ''
        if last is not None and ts < last - tol:
            status, note = 'UNALIGNABLE', 'clock backwards by %.3f s' % (last - ts)
            flags['clock_regression'] += 1
        elif last is not None and ts < last:
            note = 'out of order within tol'; flags['out_of_order_within_tol'] += 1
        rows.append({'idx': i, 'source': src, 'phase': phase, 'source_ts': ts,
                     'x': float(pos[0]), 'y': float(pos[1]), 'z': float(pos[2]),
                     'status': status, 'reason': note})
        if last is None or ts >= last: last = ts
    spans = []
    for ph in sorted({r.get('phase') for r in rows if r.get('phase')}):
        sel = [r for r in rows if r.get('phase') == ph and r.get('status') == 'OK']
        if not sel:
            spans.append({'phase': ph, 'n': 0, 'note': 'no alignable sample'}); continue
        tss = sorted(r['source_ts'] for r in sel)
        gaps = [b - a for a, b in zip(tss, tss[1:])]
        spans.append({'phase': ph, 'n': len(sel),
                      'first_sample_ts': tss[0], 'last_sample_ts': tss[-1],
                      'median_gap_s': gaps[len(gaps)//2] if gaps else None,
                      'max_gap_s': max(gaps) if gaps else None,
                      'boundary_method': 'last observed sample; not interpolated'})
    return rows, spans, dict(flags)

def main(argv):
    ap = argparse.ArgumentParser()
    ap.add_argument('--in', dest='src', required=True)
    ap.add_argument('--out', dest='out', required=True)
    ap.add_argument('--tol-s', type=float, default=0.05)
    a = ap.parse_args(argv)
    if os.path.abspath(a.out) == os.path.abspath(a.src):
        print('refusing to write into the input directory'); return 2
    logs = find_logs(a.src)
    if not logs:
        print('no *.jsonl under any skills/ dir - checked nothing, refusing to report clean'); return 2
    os.makedirs(a.out, exist_ok=False)
    recs = load(logs)
    rows, spans, flags = build(recs, a.tol_s)
    cols = ['idx','source','phase','source_ts','x','y','z','status','reason']
    with open(os.path.join(a.out,'timeline.csv'),'w',newline='') as fh:
        w = csv.DictWriter(fh, fieldnames=cols); w.writeheader()
        for r in rows: w.writerow({k: r.get(k) for k in cols})
    alignable = sum(1 for r in rows if r.get('status') == 'OK')
    json.dump({'inputs': logs, 'n_records': len(recs), 'n_alignable': alignable,
               'flags': flags, 'phases': spans,
               'method': 'phase spans use the last observed sample; no interpolation',
               'causality': 'same-window samples are co-occurrence only; this tool does not label any window as contact or as physical acceptance'},
              open(os.path.join(a.out,'timeline.json'),'w'), indent=1)
    print('records %d alignable %d flags %s' % (len(recs), alignable, flags))
    return 0

if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))