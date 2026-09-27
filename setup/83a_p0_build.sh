#!/usr/bin/env bash
# 83a_p0_build.sh — Step 0 (#20): sync patched staging into WSL, verify the
# dirty set is EXACTLY the 10 patched files, build, static attr scan, unit tests.
source /opt/ros/jazzy/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week2/m2_2_step0_ghost_fix
mkdir -p "$E"

echo "=== pre-sync git status (must be clean) ==="
git status --porcelain -- src/ | tee "$E/83a_prestatus.txt"
PRE_N=$(wc -l < "$E/83a_prestatus.txt")
echo "PRE_DIRTY=$PRE_N"

echo "=== sync src/flexcell from staging (F:) ==="
cp -r /mnt/f/flexcell-stage/agentic_workcell_ws/src/flexcell/. src/flexcell/

git status --porcelain -- src/ | tee "$E/83a_git_status.txt"
DIRTY_N=$(grep -c '^ M' "$E/83a_git_status.txt")
echo "DIRTY_COUNT=$DIRTY_N (expect 10)"
if [ "$PRE_N" != "0" ] || [ "$DIRTY_N" != "10" ]; then
  echo "SYNC CHECK FAILED (pre=$PRE_N dirty=$DIRTY_N) - inspect $E/83a_git_status.txt"
  exit 1
fi
echo "SYNC CHECK OK"

echo "=== colcon build ==="
{
  colcon build --symlink-install --packages-select flexcell_interfaces flexcell_skills 2>&1 | tail -5
  echo "BUILD_RC=${PIPESTATUS[0]}"
} | tee "$E/83a_build.out"

source install/setup.bash

echo "=== static no-undefined-attr scan ==="
python3 /mnt/f/flexcell-stage/setup/82_undefined_attr_check.py src/flexcell 2>&1 | tee "$E/83a_attr_scan.out"

echo "=== canonical WorldState tests (regression, expect 13) ==="
python3 src/flexcell/flexcell_skills/test/test_canonical_state.py 2>&1 | tail -3 | tee "$E/83a_canonical.out"

echo "=== decision policy tests (regression, expect 15) ==="
python3 src/flexcell/flexcell_skills/test/test_decision_policy.py 2>&1 | tail -3 | tee "$E/83a_policy.out"

echo "=== crash_detail unit check ==="
python3 - <<'PYEOF' 2>&1 | tee "$E/83a_crash_detail.out"
from flexcell_skills.common import crash_detail
try:
    raise ValueError('boom-marker')
except ValueError as exc:
    d = crash_detail(exc)
assert 'ValueError' in d and 'boom-marker' in d, d
print('crash_detail OK:', d[:120])
PYEOF

echo "=== 83a DONE ==="
