"""Regression guards for the read-only 4DOF FK used by issue #121.

Pure-python only: no scipy, no ROS, no simulator. The chain constants mirror
the upstream open_manipulator_x.urdf joint origins/axes; the CLI re-parses the
real URDF at runtime.
"""
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT / "scripts"))

import fourdof_reachability as fk

CHAIN = [
    ((0.012, 0.0, 0.0), (0.0, 0.0, 1.0)),
    ((0.0, 0.0, 0.0595), (0.0, 1.0, 0.0)),
    ((0.024, 0.0, 0.128), (0.0, 1.0, 0.0)),
    ((0.124, 0.0, 0.0), (0.0, 1.0, 0.0)),
]
EE = (0.126, 0.0, 0.0)


def test_zero_joint_pose_matches_the_upstream_urdf():
    p = fk.ee_position((0, 0, 0, 0), CHAIN, EE)
    assert abs(p[0] - 0.286) < 1e-9
    assert abs(p[1]) < 1e-9
    assert abs(p[2] - 0.1875) < 1e-9
    assert fk.ee_up((0, 0, 0, 0), CHAIN, EE) == (0.0, 0.0, 1.0)


def test_pitch_is_the_sum_of_the_three_parallel_joints():
    q = (0.0, -0.5, 0.7, 0.3)
    assert abs(fk.pitch_deg(q) - math.degrees(0.5)) < 1e-9


def test_yaw_joint_does_not_change_the_attitude_tilt():
    # joint1 rotates about world Z, so the up-vector tilt is invariant to it.
    q0 = (0.0, 0.2, -0.3, 0.4)
    q1 = (1.2, 0.2, -0.3, 0.4)
    u0 = fk.ee_up(q0, CHAIN, EE)
    u1 = fk.ee_up(q1, CHAIN, EE)
    t0 = math.degrees(math.acos(max(-1, min(1, u0[2]))))
    t1 = math.degrees(math.acos(max(-1, min(1, u1[2]))))
    assert abs(t0 - t1) < 1e-9


def test_rotation_matrices_are_orthonormal():
    for axis in ((0, 0, 1), (0, 1, 0), (1, 0, 0)):
        r = fk.rotation(axis, 0.73)
        for i in range(3):
            for j in range(3):
                dot = sum(r[k][i] * r[k][j] for k in range(3))
                assert abs(dot - (1.0 if i == j else 0.0)) < 1e-12


def test_joint_limits_are_enforced():
    assert fk.joint_limits_ok((0, 0, 0, 0)) is True
    assert fk.joint_limits_ok((0, 1.6, 0, 0)) is False
    assert fk.joint_limits_ok((0, 0, 0, 2.0)) is False
    assert fk.joint_limits_ok((4.0, 0, 0, 0)) is False


def test_parse_chain_reads_a_minimal_urdf(tmp_path):
    urdf = tmp_path / "arm.urdf"
    urdf.write_text("""<robot name="arm">
      <joint name="joint1" type="revolute"><origin xyz="0.012 0 0"/><axis xyz="0 0 1"/>
        <parent link="link1"/><child link="link2"/></joint>
      <joint name="joint2" type="revolute"><origin xyz="0 0 0.0595"/><axis xyz="0 1 0"/>
        <parent link="link2"/><child link="link3"/></joint>
      <joint name="joint3" type="revolute"><origin xyz="0.024 0 0.128"/><axis xyz="0 1 0"/>
        <parent link="link3"/><child link="link4"/></joint>
      <joint name="joint4" type="revolute"><origin xyz="0.124 0 0"/><axis xyz="0 1 0"/>
        <parent link="link4"/><child link="link5"/></joint>
      <joint name="end_effector_joint" type="fixed"><origin xyz="0.126 0 0"/>
        <parent link="link5"/><child link="end_effector_link"/></joint>
    </robot>""")
    chain, ee = fk.parse_chain(str(urdf))
    assert chain == CHAIN
    assert ee == EE
