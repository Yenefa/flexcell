#!/usr/bin/env bash
# Inject the physics/contact trace plugins into a generated world.
# The declaration below is copied from an archived run that DID produce contact traces
# (evobot_t08_contact_calibration_20261112/runs/H0000/t1/sim/world.sdf), not invented.
set -u
W=$1
[ -f "$W" ] || { echo "no world at $W"; exit 2; }
if grep -q 'ContactTrace' "$W"; then echo 'already instrumented'; exit 0; fi
PLUGINS='<plugin name="flexcell::PhysicsTrace" filename="libflexcell_physics_trace.so" /><plugin name="flexcell::ContactTrace" filename="libflexcell_contact_trace.so"><watch><model>target_box_a</model><link>link</link><collision>col</collision></watch><watch><model>target_box_b</model><link>link</link><collision>col</collision></watch><watch><model>ground_plane</model><link>link</link><collision>collision</collision></watch><flush_each_step>true</flush_each_step></plugin>'
python3 - "$W" "$PLUGINS" <<'PY'
import sys
w, plugins = sys.argv[1], sys.argv[2]
src = open(w).read()
if '</world>' not in src:
    print('no </world> tag'); sys.exit(2)
src = src.replace('</world>', plugins + '</world>', 1)
open(w, 'w').write(src)
print('injected trace plugins')
PY