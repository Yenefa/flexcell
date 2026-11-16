"""Two retained layouts and three initial states, for the #253 hold-out.

WHY
    The six hold-out slots existed as labels: the instances carried no layout or
    state variation, so the plan was three copies of each family and the exercise
    proved the lock turned rather than that anything generalised.

    A layout here is the workcell geometry: the zone coordinates the perception
    service publishes. A repair that fixes the object registry by rewriting the
    whole file can quietly hardcode one layout's coordinates; evaluating the
    frozen repair on a second layout is what catches that.

    The three states change which layout file is presented and the seed, not the
    defect: a state is an initial condition the repair must survive, not a new
    task.
"""

LAYOUTS = {
    "L1": {
        "zone_1_x": 0.12, "zone_1_y": -0.15, "zone_1_z": 0.0175,
        "zone_2_x": 0.25, "zone_2_y": 0.05, "zone_2_z": 0.0175,
    },
    "L2": {
        "zone_1_x": 0.16, "zone_1_y": -0.09, "zone_1_z": 0.0175,
        "zone_2_x": 0.31, "zone_2_y": 0.11, "zone_2_z": 0.0175,
    },
}

STATES = ("s1", "s2", "s3")

# The keys the configuration carries, in the order the substitution expects.
CONFIG_KEYS = ("zone_zone_1_x", "zone_zone_1_y", "zone_zone_1_z",
               "zone_zone_2_x", "zone_zone_2_y", "zone_zone_2_z")


def layout_values(name):
    if name not in LAYOUTS:
        raise ValueError("unknown layout %r (known: %s)" % (name, ", ".join(LAYOUTS)))
    return dict(LAYOUTS[name])


def apply_to_config(text, layout):
    """Rewrite the six zone coordinates, leaving everything else alone."""
    import re
    values = layout_values(layout)
    for key, field in zip(CONFIG_KEYS, ("zone_1_x", "zone_1_y", "zone_1_z",
                                        "zone_2_x", "zone_2_y", "zone_2_z")):
        text = re.sub(r"(?m)^(\s*%s:\s*).*$" % re.escape(key),
                      lambda m: m.group(1) + repr(values[field]), text)
    return text
