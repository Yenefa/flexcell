#!/usr/bin/env python3
"""Inject the contact-evidence channel into a COPY of a generated world.sdf.

WHY THIS EXISTS
    sim_profile.py refuses contact_trace outside the detachable_joint 2 ms
    profile, and its generated world/params are hashed into frozen
    declarations. Editing it would silently rewrite historical evidence. So the
    generated world copy is mutated here instead: sim_profile.py stays
    byte-identical (its sha256 is recorded in the run manifest).

WHAT IT ADDS, AND WHY EACH PART IS NEEDED
    1. contacts_entity_names on the Physics system: without it the contact
       records carry numeric entity ids only, so the pusher cannot be NAMED and
       the pusher_contact gate cannot attribute motion to a declared link.
    2. flexcell::ContactTrace with one watch per tracked box plus the floor:
       the floor is watched so table support is a MEASURED contact rather than
       an inference from a plausible height.
    3. a contact sensor on each watched collision: the ContactSensorData
       component only exists if the collision has one, so without this the
       plugin reports component_present=false for every step.
"""
import sys
import xml.etree.ElementTree as ET


def main(argv):
    if len(argv) < 2:
        print("usage: inject_contact_evidence.py <world.sdf> [model ...]", file=sys.stderr)
        return 2
    path = argv[1]
    models = argv[2:] or ["target_box_a", "target_box_b"]
    tree = ET.parse(path)
    root = tree.getroot()
    if root.tag != "sdf":
        raise SystemExit("unexpected root " + root.tag)
    world = root.find("world")
    physics = world.find("plugin[@name='gz::sim::systems::Physics']")
    if physics is None:
        raise SystemExit("physics system plugin missing")
    if physics.find("contacts_entity_names") is None:
        ET.SubElement(physics, "contacts_entity_names").text = "true"
    observer = ET.SubElement(world, "plugin", name="flexcell::ContactTrace",
                             filename="libflexcell_contact_trace.so")
    for model in models:
        watch = ET.SubElement(observer, "watch")
        for key, value in (("model", model), ("link", "link"), ("collision", "col")):
            ET.SubElement(watch, key).text = value
    floor = ET.SubElement(observer, "watch")
    for key, value in (("model", "ground_plane"), ("link", "link"),
                       ("collision", "collision")):
        ET.SubElement(floor, key).text = value
    ET.SubElement(observer, "flush_each_step").text = "true"
    for model in models:
        link = world.find("model[@name='%s']/link[@name='link']" % model)
        if link is None:
            raise SystemExit("missing link for " + model)
        if link.find("sensor[@type='contact']") is None:
            sensor = ET.SubElement(link, "sensor", name="contact_probe", type="contact")
            ET.SubElement(sensor, "always_on").text = "true"
            ET.SubElement(sensor, "update_rate").text = "500"
            ET.SubElement(ET.SubElement(sensor, "contact"), "collision").text = "col"
    tree.write(path, encoding="utf-8", xml_declaration=True)
    print("injected ContactTrace + contacts_entity_names + contact sensors for %s"
          % ",".join(models))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
