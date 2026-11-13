"""Existing skill clients share the extracted classes rather than duplicated models."""
from flexcell_capabilities import contact_geometry as geometry, contact_trace as trace
from flexcell_skills import contact_geometry as old_geometry, contact_trace as old_trace


def test_legacy_geometry_types_and_functions_keep_identity():
    for name in ('ARM', 'FINGERS', 'ContactGeometry', 'apply', 'clip', 'box_intersects'):
        assert getattr(old_geometry, name) is getattr(geometry, name)


def test_legacy_telemetry_types_and_functions_keep_identity():
    for name in ('JsonTail', 'NativeContact', 'patch_distance', 'fresh_joint_values'):
        assert getattr(old_trace, name) is getattr(trace, name)
