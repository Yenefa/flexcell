#!/usr/bin/env bash
# Week-1: (re)spawn the target box with a DetachableJoint system (magnetic-grasp anchor).
# Run inside WSL as user ros, with /opt/ros/jazzy sourced.
source /opt/ros/jazzy/setup.bash
E=/mnt/f/flexcell-stage/setup/acceptance/week1
mkdir -p "$E"

echo "=== remove existing target_box (best effort) $(date -Is) ==="
gz service -s /world/empty/remove --reqtype gz.msgs.Entity --reptype gz.msgs.Boolean \
  --timeout 1000 --req 'name: "target_box", type: 4' 2>&1
sleep 1

echo "=== spawn target_box @ (0.22, 0, 0.0175) (no plugin; DetachableJoint goes on the robot) ==="
gz service -s /world/empty/create --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean \
  --timeout 2000 \
  --req 'name: "target_box", allow_renaming: true, pose: {position: {x: 0.22, y: 0.0, z: 0.0175}}, sdf: "<sdf version='"'"'1.9'"'"'><model name='"'"'target_box'"'"'><link name='"'"'link'"'"'><inertial><mass>0.05</mass><inertia><ixx>1.0e-05</ixx><iyy>1.0e-05</iyy><izz>1.0e-05</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia></inertial><collision name='"'"'col'"'"'><geometry><box><size>0.035 0.035 0.035</size></box></geometry><surface><friction><ode><mu>1.0</mu><mu2>1.0</mu2></ode></friction></surface></collision><visual name='"'"'vis'"'"'><geometry><box><size>0.035 0.035 0.035</size></box></geometry><material><ambient>0.9 0.25 0.2 1</ambient><diffuse>0.9 0.25 0.2 1</diffuse></material></visual></link></model></sdf>"' 2>&1
sleep 2

echo "=== add DetachableJoint system to the ROBOT model (parent_link resolves inside robot) ==="
gz service -s /world/empty/entity/system/add --reqtype gz.msgs.EntityFactory --reptype gz.msgs.Boolean \
  --timeout 2000 \
  --req 'name: "open_manipulator_x", sdf: "<plugin filename='"'"'gz-sim-detachable-joint-system'"'"' name='"'"'gz::sim::systems::DetachableJoint'"'"'><parent_link>end_effector_link</parent_link><child_model>target_box</child_model><child_link>link</child_link><topic>/flexcell/target_box/attach</topic></plugin>"' 2>&1
sleep 2

echo "=== verify existence + pose ==="
gz model -m target_box -p 2>&1
echo "=== attach topic info (expect a subscriber now) ==="
timeout 5 gz topic -i -t /flexcell/target_box/attach 2>&1 | head -6
echo "SPAWN_DONE"
