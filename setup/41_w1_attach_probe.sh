#!/usr/bin/env bash
source /opt/ros/jazzy/setup.bash
echo "=== current models ==="
timeout 8 gz model --list 2>/dev/null | tail -8
echo "=== try remove target_box with type 2 ==="
gz service -s /world/empty/remove --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 1000 --req 'name: "target_box", type: 2' 2>&1
gz service -s /world/empty/remove --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean --timeout 1000 --req 'name: "target_box_1", type: 2' 2>&1
sleep 1
timeout 8 gz model --list 2>/dev/null | tail -6
echo "=== which libs mention EntityPlugin / system add ==="
grep -rl "EntityPlugin" /opt/ros/jazzy/opt/gz_sim_vendor/lib/*.so* 2>/dev/null | head -3
python3 -c "from gz.msgs10 import EntityPlugin; print('EntityPlugin importable')" 2>&1 | tail -1
echo "=== system/add retry with EntityPlugin (timeout 8s) ==="
gz service -s /world/empty/entity/system/add --reqtype gz.msgs.EntityPlugin --reptype gz.msgs.Boolean \
  --timeout 8000 \
  --req 'entity: {name: "open_manipulator_x"}, sdf_string: "<plugin filename='"'"'gz-sim-detachable-joint-system'"'"' name='"'"'gz::sim::systems::DetachableJoint'"'"'><parent_link>end_effector_link</parent_link><child_model>target_box</child_model><child_link>link</child_link><topic>/flexcell/target_box/attach</topic></plugin>"' 2>&1
sleep 2
echo "=== attach topic info ==="
timeout 5 gz topic -i -t /flexcell/target_box/attach 2>&1 | head -6
echo "=== gazebo log tail ==="
tail -4 /tmp/omx/gazebo.log | cat -v | tail -4
echo "PROBE_DONE"
