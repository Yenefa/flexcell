#!/usr/bin/env bash
# Self-test for evobot_orphan_check.sh --judge. Feeds synthetic process lines so the result does
# not depend on what else happens to be running. Two earlier versions of this probe were
# confounded by the live batch and by exec -a not appearing in ps cmd; both were test bugs, and
# both are why the judge now takes its input on stdin.
set -u
S=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/ci-public-window/scripts
C=run1/instB
fail=0
t() { if [ "$1" = "$2" ]; then echo "  PASS $3"; else echo "  FAIL $3 (got $1 want $2)"; fail=$((fail+1)); fi; }

echo '=== 1: one node from the current instance only -> pass ==='
printf '  100 python3 /w/flexcell_skills/carry_server --params-file /evidence/run1/instB/sim/p.yaml\n' \
  | bash "$S/evobot_orphan_check.sh" --judge "$C" >/dev/null 2>&1; t $? 0 'single current node passes'

echo '=== 2: a node from an older instance -> fail ==='
printf '  100 python3 /w/flexcell_skills/carry_server --params-file /evidence/run1/instA/sim/p.yaml\n' \
  | bash "$S/evobot_orphan_check.sh" --judge "$C" >/dev/null 2>&1; t $? 1 'older instance node fails'

echo '=== 3: mixed, one stale among many current -> fail ==='
printf '  1 python3 /w/flexcell_skills/a --params-file /evidence/run1/instB/sim/p.yaml\n  2 python3 /w/flexcell_skills/b --params-file /evidence/run1/instB2/sim/p.yaml\n  3 python3 /w/flexcell_skills/c --params-file /evidence/run1/instB/sim/p.yaml\n' \
  | bash "$S/evobot_orphan_check.sh" --judge "$C" >/dev/null 2>&1; t $? 1 'one stale in three is caught'

echo '=== 4: no input -> pass ==='
printf '' | bash "$S/evobot_orphan_check.sh" --judge "$C" >/dev/null 2>&1; t $? 0 'empty input passes'

echo '=== 5: a node with no evidence path is not silently waved through -> fail ==='
printf '  7 python3 /w/flexcell_skills/x --ros-args -r __node:=x\n' \
  | bash "$S/evobot_orphan_check.sh" --judge "$C" >/dev/null 2>&1; t $? 1 'unattributable node fails closed'

echo '=== 6: pid is parsed, not blank (regression on the leading-space bug) ==='
out=$(printf '  4242 python3 /w/flexcell_skills/x --params-file /evidence/run1/instA/sim/p.yaml\n' \
  | bash "$S/evobot_orphan_check.sh" --judge "$C" 2>&1)
echo "$out" | grep -q 'pid=4242' && { echo '  PASS pid parsed as 4242'; } || { echo "  FAIL pid not parsed: $out"; fail=$((fail+1)); }

if [ "$fail" -eq 0 ]; then echo 'RESULT: PASS'; exit 0; else echo "RESULT: $fail FAILED"; exit 1; fi