"""The release drop is a behaviour change: only declared fixtures, always instrumented."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[4] / 'scripts'))
import sim_profile


def test_every_declared_clearance_is_accepted_with_the_contact_trace(tmp_path):
    for clearance in sim_profile.RELEASE_CLEARANCES:
        params, _world = sim_profile.profile(
            tmp_path / ('c%03d' % int(clearance * 1000)), 'detachable_joint', False, 'mtc',
            0., .002, contact_trace=True, release_clearance_m=clearance)
        assert isinstance(params, Path)


def test_an_undeclared_clearance_is_refused(tmp_path):
    with pytest.raises(ValueError, match='declared fixtures'):
        sim_profile.profile(tmp_path / 'x', 'detachable_joint', False, 'mtc', 0., .002,
                            contact_trace=True, release_clearance_m=.02)


def test_a_clearance_without_the_contact_trace_is_refused(tmp_path):
    with pytest.raises(ValueError, match='declared fixtures'):
        sim_profile.profile(tmp_path / 'y', 'detachable_joint', False, 'mtc', 0., .002,
                            contact_trace=False, release_clearance_m=.05)
