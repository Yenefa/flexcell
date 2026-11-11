#!/usr/bin/env bash
# N1 -- does a LABEL assert a provenance that nothing verifies?
#
# The round-2 defect: an artifact directory named "baseline_a_v2_gated_..." contained
# the ORACLE builder's output, reproduced 72/72 byte-identical by the gate auditor
# (setup/acceptance/evobot_t08_gate_audit_20261112/PROVENANCE_APRIME_VERIFICATION.md).
# Separately, three different modules are all called "A-prime" in this repo.
#
# The general shape: a LABEL asserts a producer that nothing verifies.
# The cheap detector: rebuild the artifact from the declared producer and compare hashes.
set -u
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
ARCH="$WT/../ci-public-window/evidence/baseline_a_v2_gated_20261111"
cd "$WT" || exit 2

echo "=== 1. which candidate producers actually READ the answer? ==="
echo "    (an 'oracle' is a builder that reads expected_goal: it cannot disagree with the answer)"
for f in experiments/baselines/baseline_a_composite.py \
         experiments/baselines/baseline_a_prime_rules.py \
         runtime/planner/rule_planner.py \
         runtime/planner/rule_planner_t01_t06.py; do
  [ -f "$f" ] || { echo "  MISSING  $f"; continue; }
  # code lines only: drop comments and docstring prose
  n=$(grep -n 'expected_goal' "$f" | grep -vE ':\s*#|:\s*[A-Z].*(reads|read|NOT|original|oracle)' | grep -E 'expected_goal' | grep -vE '^\s*[0-9]+:\s*(#|[A-Z][a-z]+ )' | wc -l)
  n=$(python3 - "$f" <<'PY'
import ast, sys
path = sys.argv[1]
tree = ast.parse(open(path, encoding="utf-8").read())
hits = 0
for node in ast.walk(tree):
    if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value == "expected_goal":
        hits += 1
    if isinstance(node, ast.Subscript):
        sl = node.slice
        if isinstance(sl, ast.Constant) and sl.value == "expected_goal":
            hits += 1
print(hits)
PY
)
  if [ "$n" -gt 0 ]; then
    echo "  ORACLE   $f   ($n code reference(s) to expected_goal)"
  else
    echo "  planner  $f   (0 code references to expected_goal)"
  fi
done

echo
echo "=== 2. rebuild the archived 'A-prime' plans from the ORACLE builder and hash-compare ==="
python3 - "$ARCH" <<'PY'
import hashlib, os, subprocess, sys
WT = "/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp"
ARCH = sys.argv[1]
if not os.path.isdir(ARCH):
    print("  SKIP: archive dir absent at %s" % ARCH); raise SystemExit(0)
tasks = sorted(d for d in os.listdir(ARCH) if os.path.isdir(os.path.join(ARCH, d)))
print("  archived instances: %d" % len(tasks))
same = diff = skipped = 0
for t in tasks:
    spec = WT + "/benchmark/tasks/train/%s.json" % t
    plan = os.path.join(ARCH, t, "plan.json")
    if not (os.path.exists(spec) and os.path.exists(plan)):
        skipped += 1; continue
    out = "/tmp/curator_rebuild_%s.json" % t
    r = subprocess.run([sys.executable, WT + "/experiments/baselines/build_composite_plan.py",
                        spec, out], capture_output=True, text=True)
    if r.returncode != 0:
        skipped += 1; continue
    h = lambda p: hashlib.sha256(open(p, "rb").read()).hexdigest()
    if h(out) == h(plan): same += 1
    else: diff += 1
print("  rebuilt from experiments/baselines/build_composite_plan.py:")
print("    byte-identical to archived 'A-prime': %d" % same)
print("    differing:                            %d" % diff)
print("    skipped:                              %d" % skipped)
if same and not diff:
    print()
    print("  FINDING: every archived 'A-prime' plan reproduces from the ORACLE builder,")
    print("           so the label names a producer that did not produce it.")
    print("           One hash comparison detects it. No simulator, no model call.")
PY
