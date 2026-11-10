#!/usr/bin/env python3
"""The world patch C13 would have applied (kept for the next window).

``worlds/`` is hash-frozen, so this patch is NOT applied to a judged run: it
exists so the next window can register a sanctioned constrained scenario and
recompute world_sha256 deliberately instead of silently.
"""
CEILING = """
    <model name="c13_ceiling">
      <static>true</static>
      <pose>0.12 -0.15 0.42 0 0 0</pose>
      <link name="link">
        <collision name="collision">
          <geometry><box><size>0.34 0.34 0.02</size></box></geometry>
        </collision>
        <visual name="visual">
          <geometry><box><size>0.34 0.34 0.02</size></box></geometry>
        </visual>
      </link>
    </model>
"""


def apply(world_text):
    """Insert the ceiling model before </world>."""
    idx = world_text.rfind("</world>")
    if idx < 0:
        raise ValueError("no </world> tag")
    return world_text[:idx] + CEILING + world_text[idx:]
