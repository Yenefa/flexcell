#!/usr/bin/env bash
# Build flexcell_world.sdf v3 (Week-1.5): pre-placed object_A/object_B + zone
# markers. No gz plugins - the carry is a teleport servo (flexcell_skills/
# carry_server.py via /world/empty/set_pose).
# Positions measured against the Week-1 reachability envelope:
#   A (0.22, 0)      proven pick spot
#   B (0.20, -0.18)  planar 0.269, grasp-hover reach ~0.334 (inside ~0.35)
#   zone_1 (0.12, -0.15) proven place spot (battery err 5.6mm)
#   zone_2 (0.25, 0.05)  proven place spot (battery err 6.5mm)
set -e
SRC=/home/ros/agentic_workcell_ws/src/open_manipulator/open_manipulator_bringup/worlds/empty_world.sdf
DST=/mnt/f/flexcell-stage/worlds/flexcell_world.sdf
mkdir -p /mnt/f/flexcell-stage/worlds
python3 - "$SRC" "$DST" <<'EOF'
import sys
src, dst = sys.argv[1], sys.argv[2]
world = open(src).read()

def box(name, x, y, r, g, b):
    return '''
    <model name='%s'>
      <pose>%f %f 0.0175 0 0 0</pose>
      <link name='link'>
        <inertial>
          <mass>0.05</mass>
          <inertia><ixx>1.0e-05</ixx><iyy>1.0e-05</iyy><izz>1.0e-05</izz><ixy>0</ixy><ixz>0</ixz><iyz>0</iyz></inertia>
        </inertial>
        <collision name='col'>
          <geometry><box><size>0.035 0.035 0.035</size></box></geometry>
          <surface><friction><ode><mu>1.0</mu><mu2>1.0</mu2></ode></friction></surface>
        </collision>
        <visual name='vis'>
          <geometry><box><size>0.035 0.035 0.035</size></box></geometry>
          <material><ambient>%f %f %f 1</ambient><diffuse>%f %f %f 1</diffuse></material>
        </visual>
      </link>
    </model>
''' % (name, x, y, r, g, b, r, g, b)

def zone(name, x, y, r, g, b):
    return '''
    <model name='%s'>
      <pose>%f %f 0.001 0 0 0</pose>
      <static>true</static>
      <link name='link'>
        <visual name='vis'>
          <geometry><cylinder><radius>0.06</radius><length>0.002</length></cylinder></geometry>
          <material><ambient>%f %f %f 0.4</ambient><diffuse>%f %f %f 0.4</diffuse></material>
        </visual>
      </link>
    </model>
''' % (name, x, y, r, g, b, r, g, b)

extra = (
    box('target_box_a', 0.22, 0.0, 0.9, 0.25, 0.2)
    + box('target_box_b', 0.20, -0.18, 0.2, 0.35, 0.9)
    + zone('zone_1', 0.12, -0.15, 0.3, 0.9, 0.3)
    + zone('zone_2', 0.25, 0.05, 0.3, 0.3, 0.9)
)
assert '</world>' in world, 'unexpected world file structure'
world = world.replace('</world>', extra + '  </world>')
open(dst, 'w').write(world)
print('written', dst, len(world), 'bytes')
EOF
echo "WORLD_BUILD_DONE"
