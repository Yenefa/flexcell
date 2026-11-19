#!/usr/bin/env bash
# Tear down every process this stack leaves behind, including the skill nodes.
# Without this, the next run inherits a live carry_server (duplicate carry_state
# publishers), a stuck task state ('another demo task is active') or a held
# admission lock -- all of which look like product failures but are leftovers.
# Measured 2026-11-19: back-to-back runs WITH this cleanup and WITHOUT it differ
# in outcome more than any parameter we tried.
set -u
pkill -9 -f sim_smoke.py 2>/dev/null
pkill -9 -f sim_window.py 2>/dev/null
pkill -9 -f 'gz sim' 2>/dev/null
pkill -9 -f move_group 2>/dev/null
pkill -9 -f ros2_control_node 2>/dev/null
# NOTE: the FSM executable is task_fsm_server. An earlier version of this list
# said "task_server", which matches nothing: a leftover FSM then became a SECOND
# run_pick_place action server, so a client could send its goal to one instance
# and read the result from another (CLIENT_RESULT_UNKNOWN after a few seconds).
for node in carry_server task_fsm_server pick_server place_server observe_server \
            verify_server move_to_pose_server run_demo_server \
            parameter_bridge robot_state_publisher; do
    pkill -9 -f "$node" 2>/dev/null
done
sleep 4
echo "remaining stack processes: $(pgrep -fc 'carry_server|task_server|move_group|gz sim' || true)"