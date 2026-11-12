#!/usr/bin/env bash
# Instrument a generated world for contact evidence.
#
# TWO things are required, and the first was invisible until the contact trace ran:
#   1. the Physics system must publish contact entity names -
#        <contacts_entity_names>true</contacts_entity_names>
#      Without it the ContactTrace plugin loads, finds collision_entity, and still reports
#      component_present:false / contacts:null on every step. sim_profile emits a SELF-CLOSING
#      Physics plugin, so this has to be rewritten, not appended.
#   2. the trace plugins themselves, whose class/output is configured by the environment
#      variable FLEXCELL_CONTACT_STEP_LOG (found in strings on the .so; it is not an SDF child).
#
# Declarations copied from an archived world that DID record contacts:
#   evobot_t08_contact_calibration_20261112/runs/H0000/t1/sim/world.sdf
set -u
W=$1
[ -f "$W" ] || { echo "no world at $W"; exit 2; }
python3 - "$W" <<'PY'
import re, sys
w = sys.argv[1]
src = open(w).read()
changed = []

# 1. physics must publish contact entity names
self_closing = '<plugin name="gz::sim::systems::Physics" filename="gz-sim-physics-system" />'
if self_closing in src:
    src = src.replace(self_closing,
        '<plugin name="gz::sim::systems::Physics" filename="gz-sim-physics-system">'
        '<contacts_entity_names>true</contacts_entity_names></plugin>', 1)
    changed.append('physics: contacts_entity_names=true')
elif '<contacts_entity_names>' not in src:
    print('WARNING: physics plugin neither self-closing nor carrying contacts_entity_names')

# 2. trace plugins, appended once
if 'flexcell::ContactTrace' not in src:
    plugins = ('<plugin name="flexcell::PhysicsTrace" filename="libflexcell_physics_trace.so" />'
               '<plugin name="flexcell::ContactTrace" filename="libflexcell_contact_trace.so">'
               '<watch><model>target_box_a</model><link>link</link><collision>col</collision></watch>'
               '<watch><model>target_box_b</model><link>link</link><collision>col</collision></watch>'
               '<watch><model>ground_plane</model><link>link</link><collision>collision</collision></watch>'
               '<flush_each_step>true</flush_each_step></plugin>')
    if '</world>' not in src:
        print('no </world> tag'); sys.exit(2)
    src = src.replace('</world>', plugins + '</world>', 1)
    changed.append('trace plugins appended')

open(w, 'w').write(src)
print('instrumented: ' + (', '.join(changed) if changed else 'already complete'))
PY