#!/usr/bin/env bash
# Re-grade every archived Baseline A-v2 observation with the CURRENT evaluate.py.
# Reads archived verdicts only; writes nothing outside the scratch dir.
# Expected: graded=72 agree=72 disagree=0
set -u
WT=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
CI=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/evidence/baseline_a_v2_gated_20261111
OUT=${1:-/tmp/lead_regress}
cd "$WT" || exit 1
rm -rf "$OUT"; mkdir -p "$OUT"
printf '%-24s %-8s %-8s %-6s %s\n' instance archived re_graded agree arch_eval
n=0; same=0; diff=0
for d in "$CI"/*/; do
  name=$(basename "$d")
  obs="$d/observation.json"; arch="$d/verdict.json"; spec="benchmark/tasks/train/$name.json"
  [ -f "$obs" ] && [ -f "$arch" ] && [ -f "$spec" ] || continue
  python3 benchmark/evaluators/evaluate.py "$spec" "$obs" > "$OUT/$name.json" 2>"$OUT/$name.err" \
    || { echo "$name GRADE_ERROR"; continue; }
  a=$(python3 -c "import json;print(json.load(open('$arch')).get('passed'))" 2>/dev/null)
  b=$(python3 -c "import json;print(json.load(open('$OUT/$name.json')).get('passed'))" 2>/dev/null)
  av=$(python3 -c "import json;print(json.load(open('$arch')).get('evaluator_version','?'))" 2>/dev/null)
  n=$((n+1))
  if [ "$a" = "$b" ]; then same=$((same+1)); ag=YES; else diff=$((diff+1)); ag=NO; fi
  printf '%-24s %-8s %-8s %-6s %s\n' "$name" "$a" "$b" "$ag" "$av"
done
echo
echo "graded=$n  agree=$same  disagree=$diff"
[ "$diff" -eq 0 ] || exit 1