"""Posture search keeps the existing constraints and never dispatches motion."""
import math
import unittest
from unittest.mock import Mock

import numpy as np
from flexcell_capabilities.contact_geometry import ContactGeometry


class ReachableContactTest(unittest.TestCase):
    def model(self):
        model=ContactGeometry.__new__(ContactGeometry)
        def register(center,protected,gripper,pitch):
            return dict(approach_joints=[0.]*4,tcp=[0.]*3,pitch_rad=pitch)
        model.register_finger=Mock(side_effect=register)
        model.frames=Mock(return_value={'end_effector_link':np.eye(4)})
        model.tcp_inverse=Mock(side_effect=lambda point,pitch,tcp,seed:[math.degrees(pitch),float(point[0]),0.,0.])
        model.guards=Mock(return_value=.002)
        return model

    def test_feasible_existing_pose_keeps_85_degrees(self):
        model=self.model();reg=model.register_reachable_finger([.22,0,.0175],[])
        self.assertAlmostEqual(math.degrees(reg['pitch_rad']),85.)
        self.assertEqual(model.register_finger.call_count,1)
        self.assertEqual(reg['rejected_pitches'],[])
        self.assertEqual(model.guards.call_count,10)

    def test_unreachable_pose_uses_first_fully_feasible_candidate(self):
        model=self.model();original=model.register_finger.side_effect
        def register(*args,**kwargs):
            if math.degrees(kwargs['pitch'])>79.01:raise ValueError('fixed-pitch target unreachable')
            return original(*args,**kwargs)
        model.register_finger.side_effect=register
        reg=model.register_reachable_finger([.235,.025,.0175],[])
        self.assertAlmostEqual(math.degrees(reg['pitch_rad']),79.)
        self.assertEqual(len(reg['rejected_pitches']),6)

    def test_later_stroke_collision_rejects_an_initially_valid_pose(self):
        model=self.model()
        def guard(q,protected,gripper):
            if q[0]>84.9 and q[1]<-.01:raise ValueError('protected collision')
            return .002
        model.guards.side_effect=guard
        reg=model.register_reachable_finger([.22,0,.0175],[])
        self.assertAlmostEqual(math.degrees(reg['pitch_rad']),84.)
        self.assertEqual(reg['rejected_pitches'][0]['reason'],'protected collision')

    def test_no_feasible_pose_fails_without_an_unchecked_default(self):
        model=self.model();model.register_finger.side_effect=ValueError('no legal surface')
        with self.assertRaisesRegex(ValueError,'no registered contact pitch'):
            model.register_reachable_finger([.4,0,.0175],[])
        model.tcp_inverse.assert_not_called()

    def test_cancellation_before_search_does_not_plan(self):
        model=self.model()
        with self.assertRaisesRegex(ValueError,'canceled'):
            model.register_reachable_finger([.22,0,.0175],[],abort_check=lambda:True)
        model.register_finger.assert_not_called()


if __name__=='__main__':unittest.main()
