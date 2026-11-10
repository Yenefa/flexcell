"""The scene patch as applied to scripts/sim_profile.py (additive only).

Kept here so a reader can see exactly what was added without diffing the script.
Existing scenes are untouched; the default world hash is verified unchanged in
README section 2.
"""

SCENE_ENTRY = "constrained_approach"   # appended to SCENES

CEILING = {
    "name": "approach_ceiling",
    "static": "true",
    "pose": "0.22 0.0 0.155 0 0 0",       # 0.30 x 0.30 x 0.010 plate above target_box_a
    "size": "0.30 0.30 0.010",
}

# Known defect in this first version: the plate spans 0.30 m in x, which also
# obstructs target_box_b. Shrink to ~0.12 m or raise to z=0.20 before drawing any
# conclusion about MTC vs legacy on the FULL dual_object task.
