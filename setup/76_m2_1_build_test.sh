#!/usr/bin/env bash
# 76_m2_1_build_test.sh — M2.1: sync v2 sources (F: -> WSL), build, run canonical
# WorldState v2 contract tests. Evidence -> acceptance/week15/m2_1_worldstate_v2/
source /opt/ros/jazzy/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_worldstate_v2
mkdir -p "$E"

{
  echo "=== M2.1 build + test | $(date -Is) ==="
  echo "--- sync src/flexcell from staging (F:) ---"
  cp -r /mnt/f/flexcell-stage/agentic_workcell_ws/src/flexcell/. src/flexcell/
  echo "--- colcon build (flexcell_interfaces + flexcell_skills) ---"
  colcon build --symlink-install --packages-select flexcell_interfaces flexcell_skills 2>&1 | tail -6
  BUILD_RC=$?
  echo "BUILD_RC=$BUILD_RC"
} > "$E/76_build.out" 2>&1

source /opt/ros/jazzy/setup.bash
source install/setup.bash

{
  echo "=== canonical WorldState v2 contract tests | $(date -Is) ==="
  python3 src/flexcell/flexcell_skills/test/test_canonical_state.py 2>&1
  TEST_RC=$?
  echo "TEST_RC=$TEST_RC"
  echo "--- import smoke (new msgs + serializer) ---"
  python3 -c "
from flexcell_interfaces.msg import TaskContext, TaskConstraints, Assignment, HistoryEntry
from flexcell_interfaces.msg import WorldState
ws = WorldState()
print('schema_version field present:', hasattr(ws, 'schema_version'))
print('task field present:', hasattr(ws, 'task'))
from flexcell_skills.canonical_state import SCHEMA_VERSION, serialize_envelope
print('serializer OK, SCHEMA_VERSION =', SCHEMA_VERSION)
"
  SMOKE_RC=$?
  echo "SMOKE_RC=$SMOKE_RC"
} > "$E/76_tests.out" 2>&1

echo "--- build tail ---"
tail -6 "$E/76_build.out"
echo "--- test summary ---"
grep -E "^(Ran|OK|FAILED|TEST_RC|SMOKE_RC|schema_version|task field|serializer)" "$E/76_tests.out"
grep -c "OK" "$E/76_tests.out" > /dev/null
tail -3 "$E/76_tests.out"
