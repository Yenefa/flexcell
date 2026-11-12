#!/usr/bin/env bash
# Instrument a generated world for contact evidence.
#
# THREE things are required. The third was the one that mattered, and each was found by a
# different route - recorded here so the next person does not repeat the search:
#
#   1. FLEXCELL_CONTACT_STEP_LOG must be set in the environment. The trace plugin reads its
#      output path from that variable, not from an SDF child - found in strings on the .so.
#      Without it gz dies with 'new contact step log path required'.
#   2. the Physics system must publish contact entity names:
#        <contacts_entity_names>true</contacts_entity_names>
#      sim_profile emits a SELF-CLOSING Physics plugin, so this has to be rewritten.
#      This alone did NOT enable contact data (tested), but it is present in the archived world.
#   3. each watched link needs a contact SENSOR. The plugin probes the gz ContactSensorData
#      component; with no sensor that component never exists and every record reports
#      component_present:false / contacts:null. The archived world carries:
#        <sensor name='contact_probe' type='contact'><always_on>true</always_on>
#          <update_rate>500</update_rate><contact><collision>col</collision></contact></sensor>
#      inside the target model's link. THIS is the gate.
set -u
W=$1
[ -f "$W" ] || { echo "no world at $W"; exit 2; }
python3 - "$W" <<'PY'
import re, sys
w = sys.argv[1]
src = open(w).read()
changed = []

sc = '<plugin name="gz::sim::systems::Physics" filename="gz-sim-physics-system" />'
if sc in src:
    src = src.replace(sc,
        '<plugin name="gz::sim::systems::Physics" filename="gz-sim-physics-system">'
        '<contacts_entity_names>true</contacts_entity_names></plugin>', 1)
    changed.append('physics contacts_entity_names')

# contact sensor on every watched box model's link
SENSOR = ('<sensor name="contact_probe" type="contact"><always_on>true</always_on>',
          '<update_rate>500</update_rate><contact><collision>{col}</collision></contact></sensor>')
for model in ('target_box_a', 'target_box_b'):
    m = re.search(r'(<model name="%s">)(.*?)(</model>)' % re.escape(model), src, re.S)
    if not m:
        print('WARNING: model %s not found' % model); continue
    block = m.group(0)
    if 'type="contact"' in block:
        continue
    col = re.search(r'<collision name="([^"]+)"', block)
    colname = col.group(1) if col else 'collision'
    if '</link>' not in block:
        print('WARNING: no </link> in %s' % model); continue
    newblock = block.replace('</link>', SENSOR[0] + SENSOR[1].format(col=colname) + '</link>', 1)
    src = src.replace(block, newblock, 1)
    changed.append('contact sensor on %s (collision=%s)' % (model, colname))

if 'flexcell::ContactTrace' not in src:
    plugins = ('<plugin name="flexcell::PhysicsTrace" filename="libflexcell_physics_trace.so" />'
               '<plugin name="flexcell::ContactTrace" filename="libflexcell_contact_trace.so">'
               '<watch><model>target_box_a</model><link>link</link><collision>col</collision></watch>'
               '<watch><model>target_box_b</model><link>link</link><collision>col</collision></watch>'
               '<watch><model>ground_plane</model><link>link</link><collision>collision</collision></watch>'
               '<flush_each_step>true</flush_each_step></plugin>')
    src = src.replace('</world>', plugins + '</world>', 1)
    changed.append('trace plugins')

open(w, 'w').write(src)
print('instrumented: ' + (', '.join(changed) if changed else 'already complete'))
PY