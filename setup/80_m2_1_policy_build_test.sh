#!/usr/bin/env bash
# 80_m2_1_policy_build_test.sh — M2.1 #4: sync, build, run policy + canonical tests
source /opt/ros/jazzy/setup.bash
cd /home/ros/agentic_workcell_ws

E=/mnt/f/flexcell-stage/setup/acceptance/week15/m2_1_decision_policy
mkdir -p "$E"

{
  echo "=== M2.1 #4 build + test | $(date -Is) ==="
  echo "--- sync src/flexcell from staging (F:) ---"
  cp -r /mnt/f/flexcell-stage/agentic_workcell_ws/src/flexcell/. src/flexcell/
  echo "--- colcon build ---"
  colcon build --symlink-install --packages-select flexcell_interfaces flexcell_skills 2>&1 | tail -6
  echo "BUILD_RC=$?"
} > "$E/80_build.out" 2>&1

source /opt/ros/jazzy/setup.bash
source install/setup.bash

{
  echo "=== decision policy unit tests | $(date -Is) ==="
  python3 src/flexcell/flexcell_skills/test/test_decision_policy.py 2>&1
  echo "POLICY_TEST_RC=$?"
  echo "=== canonical WorldState v2 tests (regression) | $(date -Is) ==="
  python3 src/flexcell/flexcell_skills/test/test_canonical_state.py 2>&1 | tail -5
  echo "CANONICAL_TEST_RC=$?"
  echo "=== task_fsm_server import smoke (syntax + new seam) ==="
  python3 -c "
import ast, sys
src = open('src/flexcell/flexcell_skills/flexcell_skills/task_fsm_server.py').read()
ast.parse(src)
import flexcell_skills.task_fsm_server as m
print('task_fsm_server imports OK; policy seam:', hasattr(m.TaskFsmServer, '_execute_demo'))
from flexcell_skills.decision_policy import FSMPolicy, DecisionPolicy
print('FSMPolicy conforms:', issubclass(FSMPolicy, DecisionPolicy))
"
  SMOKE_RC=$?
  echo "SMOKE_RC=$SMOKE_RC"
} > "$E/80_tests.out" 2>&1

echo "--- build tail ---"
tail -4 "$E/80_build.out"
echo "--- policy tests ---"
grep -E "^(Ran|OK|FAILED|POLICY_TEST_RC|CANONICAL_TEST_RC|SMOKE_RC|task_fsm_server)" "$E/80_tests.out"
