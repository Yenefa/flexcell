#!/usr/bin/env bash
# Definitive: where does the DetachableJoint plugin get lost in xacro->urdf->sdf?
source /opt/ros/jazzy/setup.bash
X=/home/ros/agentic_workcell_ws/install/open_manipulator_description/share/open_manipulator_description/urdf/open_manipulator_x/open_manipulator_x.urdf.xacro
python3 - "$X" <<'EOF'
import sys
import xacro
doc = xacro.process_file(sys.argv[1], mappings={'use_sim': 'true'})
open('/tmp/rd.urdf', 'w').write(doc.toprettyxml(indent='  '))
print('urdf written')
EOF
echo "urdf DetachableJoint count: $(grep -c DetachableJoint /tmp/rd.urdf)"
gz sdf -p /tmp/rd.urdf > /tmp/rd.sdf 2>/tmp/rd.sdf.err
echo "sdf DetachableJoint count: $(grep -c DetachableJoint /tmp/rd.sdf)"
echo "sdf err: $(head -2 /tmp/rd.sdf.err)"
echo "=== plugin block in sdf ==="
grep -B2 -A8 DetachableJoint /tmp/rd.sdf | head -14
echo "CONV_DONE"
