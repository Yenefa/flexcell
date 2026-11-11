#!/bin/bash
set -o pipefail
# PROBE v4: execute a REAL plan belonging to a DIFFERENT task.
#
# WHAT THE EARLIER ATTEMPTS TAUGHT (all three failed safely, which is itself a finding):
#  v1  a heredoc errored, no set -e, the swap never ran, the CORRECT plan executed, and the
#      probe looked like it passed. Fixed by verifying the modification.
#  v2  both stages were mapped to ONE pose; the executor refused for clearance, nothing moved.
#  v3  the hand-edited plan failed plan preparation with "declared destination occupied" - the
#      executor validates plan coherence, so a hand-mangled plan cannot even start.
# v4 therefore uses a plan the real planner produced, for a task that wants the OTHER bin.
# It is coherent, it is executable, and for THIS task it is wrong - which is exactly the
# condition the claim check has to survive.
W=/mnt/c/Users/fuker/Desktop/workspace/project-033-flexcell/wt-comp
OUT=/tmp/evobot-wrongplan4; rm -rf $OUT; mkdir -p $OUT; chmod 777 $OUT
TARGET=HO-0dcde4dc0f5a    # this task wants zone_2
DONOR=HO-128c6a231c34     # this task wants zone_1; its plan is real and coherent
PUB=$W/benchmark/held_out/recovery_public80/$TARGET.json
D=$OUT/$TARGET; mkdir -p $D; chmod 777 $D
echo "task under test: $TARGET (wants zone_2)   donor plan: $DONOR (targets zone_1)"
cp /tmp/evobot-batch4/$DONOR/plan.json "$D/plan.json" || exit 3
cd $W
python3 - "$D/plan.json" "$D/plan_original_in_donor.txt" <<PY || exit 3
import json, sys
p = json.load(open(sys.argv[1]))
print("  donor plan targets:", [(s["object_name"], [round(x,3) for x in s["place_pose"]]) for s in p["stages"]])
print("  declared initial  :", [(o["object_name"], [round(x,3) for x in o["position"]]) for o in p.get("initial_objects", [])])
PY
pkill -9 -f "[g]z sim" 2>/dev/null; pkill -9 -f "[r]os2 launch" 2>/dev/null
for i in $(seq 1 30); do pgrep -f "[g]z sim|[m]ove_group|[t]ask_fsm_server" >/dev/null 2>&1 || break; sleep 1; done
sleep 2
source /opt/ros/jazzy/setup.bash >/dev/null 2>&1
source /home/ros/agentic_workcell_ws/install/setup.bash >/dev/null 2>&1
source /home/ros/flexcell-p14-ws/install/setup.bash >/dev/null 2>&1
export GZ_PARTITION=evobot-wp4 RMW_IMPLEMENTATION=rmw_cyclonedds_cpp ROS_DOMAIN_ID=231 LIBGL_ALWAYS_SOFTWARE=1
export CYCLONEDDS_URI="file://$W/config/cyclonedds.xml"
export FLEXCELL_REPO=/home/ros/flexcell-p14 FLEXCELL_WS=/home/ros/flexcell-p14-ws FLEXCELL_INSTALL=/home/ros/flexcell-p14-ws/install
( cd /home/ros/flexcell-p14 && python3 - "$D" <<PY
import sys
sys.path.insert(0, "/home/ros/flexcell-p14/scripts")
import sim_profile
sim_profile.profile(sys.argv[1] + "/sim", "velocity_servo", False, "legacy", 0.0, None)
PY
)
ros2 launch flexcell_skills trusted_sim.launch.py world:=$D/sim/world.sdf params_file:=$D/sim/params.yaml camera:=false > "$D/stack.log" 2>&1 &
STACK=$!
up=0; for i in $(seq 1 90); do ros2 action list 2>/dev/null | grep -q run_composite && { up=1; break; }; kill -0 $STACK 2>/dev/null || break; sleep 1; done
if [ $up -ne 1 ]; then echo "INFRA_STACK_DOWN"; kill -9 $STACK 2>/dev/null; exit 2; fi
cd $W
python3 experiments/baselines/composite_client.py --plan "$D/plan.json" --timeout 400 > "$D/task.out" 2>&1
NAMES=$(python3 -c 'import json,sys;print(" ".join(o["name"] for o in json.load(open(sys.argv[1]))["objects"]))' "$PUB")
python3 benchmark/evaluators/capture_ground_truth.py "$D/ground_truth.json" $NAMES > "$D/gt.log" 2>&1
python3 benchmark/evaluators/observe_from_run.py "$D/sim" "$D/observation.json" $NAMES --ground-truth "$D/ground_truth.json" --zones '{"zone_1":[0.12,-0.15,0.0175],"zone_2":[0.25,0.05,0.0175]}' > "$D/obs.log" 2>&1
kill -INT $STACK 2>/dev/null; sleep 4; kill -9 $STACK 2>/dev/null
pkill -9 -f "[g]z sim" 2>/dev/null; pkill -9 -f "[r]os2 launch" 2>/dev/null
sudo -n python3 benchmark/evaluators/sealed_evaluate.py --public "$PUB" --observation "$D/observation.json" > "$D/verdict.json" 2>"$D/grade.err"
python3 experiments/baselines/wrongplan_report.py "$D"
echo WRONGPLAN4_DONE
