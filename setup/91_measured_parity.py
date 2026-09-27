#!/usr/bin/env python3
"""Measured-data parity across two demo runs (M2.3 audit P1-9).

The old "BYTE_PARITY" compared the servers' own `fsm_trace` strings - a
repeatability check on self-reported narration, not a behavioral comparison,
and on-disk it read PARITY: FAIL in every captured artifact anyway.  This
tool compares the MEASURED values two runs must agree on:

  - outcome + step structure (labels normalized: attempt counters are
    executor-leg-local and not comparable across runs - normalizing them
    HERE is the honest fix for the attempt-label instability the audit
    found; the frozen baseline files are never edited)
  - zone_a_error_m / zone_b_error_m within --zone-tol (physics varies a few
    mm between runs; semantics must not)

Usage:
  python3 setup/91_measured_parity.py \
      --baseline setup/acceptance/week15/delivery_20260926/66_run_record_happy.jsonl \
      --fresh <session>/run_record_happy.jsonl [--zone-tol 0.025]

Exit 0 = MEASURED_PARITY: PASS, 1 = FAIL.
"""
import argparse
import json
import math
import re
import sys

_ATTEMPT = re.compile(r'attempt=\d+')


def norm_label(s):
    return _ATTEMPT.sub('attempt=N', str(s))


def load_record(path):
    with open(path) as fh:
        for line in fh:
            line = line.strip()
            if line:
                return json.loads(line)
    raise SystemExit('no record line in %s' % path)


def finite(x):
    return isinstance(x, (int, float)) and math.isfinite(float(x))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--baseline', required=True)
    ap.add_argument('--fresh', required=True)
    ap.add_argument('--zone-tol', type=float, default=0.025)
    args = ap.parse_args()

    base = load_record(args.baseline)
    fresh = load_record(args.fresh)
    checks = []

    def add(name, ok, detail):
        checks.append((name, ok, detail))
        return ok

    add('outcome', str(base.get('outcome')) == str(fresh.get('outcome')),
        'baseline=%s fresh=%s' % (base.get('outcome'), fresh.get('outcome')))

    bs, fs = base.get('steps') or [], fresh.get('steps') or []
    add('step_count', len(bs) == len(fs), 'baseline=%d fresh=%d' % (len(bs), len(fs)))

    for i, (b, f) in enumerate(zip(bs, fs)):
        lb, lf = norm_label(b.get('state', '')), norm_label(f.get('state', ''))
        if lb != lf:
            add('step_%d_label' % i, False, '%r vs %r' % (lb, lf))
        if b.get('skill') != f.get('skill'):
            add('step_%d_skill' % i, False,
                '%r vs %r' % (b.get('skill'), f.get('skill')))
        if bool(b.get('ok')) != bool(f.get('ok')):
            add('step_%d_ok' % i, False,
                '%s vs %s' % (b.get('ok'), f.get('ok')))

    for key in ('zone_a_error_m', 'zone_b_error_m'):
        bv, fv = base.get(key), fresh.get(key)
        if not finite(bv) or not finite(fv):
            add(key, False, 'non-finite (baseline=%s fresh=%s)' % (bv, fv))
            continue
        d = abs(float(bv) - float(fv))
        add(key, d <= args.zone_tol,
            'baseline=%.4f fresh=%.4f delta=%.4f (tol %.3f)'
            % (bv, fv, d, args.zone_tol))

    failed = [c for c in checks if not c[1]]
    print('MEASURED_PARITY: %s' % ('FAIL' if failed else 'PASS'))
    for name, ok, detail in checks:
        print('  %s %s: %s' % ('PASS' if ok else 'FAIL', name, detail))
    sys.exit(0 if not failed else 1)


if __name__ == '__main__':
    main()
