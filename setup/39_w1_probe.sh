#!/usr/bin/env bash
# Week-1 probe: gz python binding API surface + URDF gripper limits
source /opt/ros/jazzy/setup.bash
echo ===URDF-GRIPPER===
grep -B2 -A6 "gripper_left_joint" /home/ros/agentic_workcell_ws/src/open_manipulator/open_manipulator_description/urdf/open_manipulator_x/open_manipulator_x.urdf | head -24
find /home/ros/agentic_workcell_ws/src -maxdepth 2 -type d | head -15
echo ===URDF-FILES===
find /home/ros/agentic_workcell_ws/src -name "*.urdf" -o -name "*gripper*.xacro" 2>/dev/null | head -5
echo ===GZPY-TRANSPORT===
python3 <<'EOF'
import gz.transport13 as t
print('transport exports:', [a for a in dir(t) if not a.startswith('_')])
EOF
echo ===GZPY-MSGS===
python3 <<'EOF'
import pkgutil
import gz
mods = [m.name for m in pkgutil.iter_modules(gz.__path__)]
print('gz submodules:', mods)
for cand in ('msgs10', 'msgs', 'msgs8'):
    try:
        m = __import__('gz.' + cand, fromlist=['x'])
        names = [a for a in dir(m) if 'Pose' in a][:8]
        print(cand, 'OK', names)
    except Exception as exc:
        print(cand, 'FAIL', repr(exc)[:80])
EOF
