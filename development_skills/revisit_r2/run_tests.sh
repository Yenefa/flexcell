#!/usr/bin/env bash
# M1 -- the four skill test suites. Produces the 42-passed number.
set -u
DS="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$DS" || exit 2
total=0
for d in ros2-interface-preflight simulation-process-lifecycle evidence-level-audit effect-verification; do
  out=$(python3 -m pytest "$d/tests" -q 2>&1 | tail -2)
  n=$(echo "$out" | grep -oE '^[0-9]+ passed' | grep -oE '^[0-9]+')
  printf '  %-30s %s\n' "$d" "$(echo "$out" | tail -1)"
  total=$((total + ${n:-0}))
done
echo "  TOTAL passed: $total   (registry claims 42)"
