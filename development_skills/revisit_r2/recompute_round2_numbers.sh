#!/usr/bin/env bash
# M9 -- recompute round-2's headline numbers from committed artifacts only.
set -u
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
ACC="$WT/setup/acceptance"

echo "=== 4/5 recovery arm: recompute terminal_passed from evidence_v2/verdict_t*.json ==="
python3 - <<'PY'
import json, os
R = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/setup/acceptance/evobot_push_recover_20261112/evidence_v2"
n = 0
for i in range(1, 6):
    v = json.load(open(os.path.join(R, "verdict_t%d.json" % i)))
    n += bool(v["terminal_passed"])
    print("  t%d terminal_passed=%s passed=%s failed=%s" % (
        i, v["terminal_passed"], v["passed"], ",".join(v["failed_clauses"]) or "-"))
print("  recomputed: %d/5   RESULT_V2.md claims 4/5   MATCH=%s" % (n, n == 4))
PY

echo
echo "=== 2/5 single-shot baseline: recompute with ALL THREE frozen gates ==="
python3 - <<'PY'
# NOTE: the committed repeats.tsv has NO zone-distance column, so the zone gate
# CANNOT be recomputed from the tsv alone. The zone distances below are transcribed
# from REPEAT_RESULTS.md, which is why this number is not fully artifact-recomputable.
# That gap is finding R2-e.
md = {1: (32.13, 0.9849, 67.9), 2: (137.81, 0.9998, 37.8), 3: (57.70, 0.9999, 42.3),
      4: (4.19, 0.8290, None), 5: (-1.74, -0.6633, None)}
ok = 0
for t, (d_mm, cos, zdist) in md.items():
    d = d_mm / 1000.0
    passed = (0.030 <= d <= 0.150) and cos >= 0.9 and (zdist is not None and zdist <= 60.0)
    ok += passed
    print("  trial %d  d=%8.2fmm cos=%8s zone=%s -> %s" % (
        t, d_mm, cos, zdist, "PASS" if passed else "FAIL"))
print("  recomputed: %d/5   RESULT_V2.md claims 2/5   MATCH=%s" % (ok, ok == 2))
print()
print("  With ONLY displacement+direction (no zone column) this yields 3/5, which is")
print("  what a first recompute produced. The 1-trial difference IS finding R2-e.")
PY

echo
echo "=== R2-a: does the committed tsv agree with the committed report? ==="
python3 - <<'PY'
P = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp/setup/acceptance/evobot_t08_saturation_diagnosis_20261112/evidence/repeats.tsv"
lines = [l for l in open(P) if l.strip()]
hdr = lines[0].split()
tsv = {}
for line in lines[1:]:
    r = dict(zip(hdr, line.split()))
    tsv[int(r["trial"])] = (float(r["displacement_mm"]), float(r["direction_cos"]))
md = {1: (32.13, 0.9849), 2: (137.81, 0.9998), 3: (57.70, 0.9999),
      4: (4.19, 0.8290), 5: (-1.74, -0.6633)}
print("  trial | tsv mm | report mm | delta")
for t in range(1, 6):
    print("   %d    | %7.2f | %9.2f | %+6.2f" % (t, tsv[t][0], md[t][0], tsv[t][0] - md[t][0]))
print()
print("  4 of 5 disagree; trial 5 has OPPOSITE SIGN (tsv unsigned +2.63 vs report -1.74).")
PY
