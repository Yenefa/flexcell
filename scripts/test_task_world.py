"""Synthetic initializer checks; never count as robot task successes."""
import copy
import math
from pathlib import Path
import tempfile
import unittest
import xml.etree.ElementTree as ET

from task_world import LayoutError,materialize,verify_initial


WORLD = '''<sdf version="1.9"><world name="default"><gravity>0 0 -9.8</gravity>
<model name="a"><pose>0.22 0 0.0175 0 0 0</pose><link name="link">
<inertial><mass>0.05</mass></inertial><collision name="col"><geometry>
<box><size>0.035 0.035 0.035</size></box></geometry><surface><friction>
<ode><mu>0.5</mu></ode></friction></surface></collision></link></model></world></sdf>'''
OBJECTS = [dict(name='a',size=[.035]*3,initial_pose=[.23,.015,.0175,.2])]


class LayoutChecks(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.source = Path(self.tmp.name)/'source.sdf'
        self.out = Path(self.tmp.name)/'initialized.sdf'
        self.source.write_text(WORLD)

    def run_layout(self,objects=None):
        return materialize(self.source,self.out,objects if objects is not None else copy.deepcopy(OBJECTS))

    def test_declared_translation_and_yaw_are_instantiated_without_changing_physics(self):
        declaration = copy.deepcopy(OBJECTS)
        manifest = self.run_layout(declaration)
        self.assertEqual(declaration,OBJECTS)
        self.assertEqual(self.source.read_text(),WORLD)
        source = ET.parse(self.source); output = ET.parse(self.out)
        self.assertEqual([float(v) for v in output.find('world/model/pose').text.split()], [.23,.015,.0175,0.,0.,.2])
        for selector in ['world/gravity','world/model/link/inertial','world/model/link/collision']:
            self.assertEqual(ET.tostring(source.find(selector)),ET.tostring(output.find(selector)))
        self.assertFalse(manifest['reads_goal_fields'])
        self.assertFalse(manifest['live_state_mutation'])

    def test_existing_source_or_output_is_never_overwritten(self):
        with self.assertRaises(FileExistsError):materialize(self.source,self.source,OBJECTS)
        self.assertEqual(self.source.read_text(),WORLD)
        self.run_layout()
        before = self.out.read_bytes()
        with self.assertRaises(FileExistsError):self.run_layout()
        self.assertEqual(before,self.out.read_bytes())

    def test_missing_model_does_not_synthesize_an_unreviewed_model(self):
        objects = copy.deepcopy(OBJECTS);objects[0]['name']='missing'
        with self.assertRaises(LayoutError):self.run_layout(objects)
        self.assertFalse(self.out.exists())

    def test_duplicate_and_nonfinite_initial_conditions_are_refused(self):
        cases = [OBJECTS*2,[],[dict(OBJECTS[0],initial_pose=[True,0.,0.,0.])],
                 [dict(OBJECTS[0],initial_pose=[0.,float('nan'),0.,0.])]]
        for case in cases:
            with self.subTest(case=case),self.assertRaises(LayoutError):self.run_layout(case)
        self.assertFalse(self.out.exists())

    def test_geometry_change_is_refused(self):
        with self.assertRaises(LayoutError):self.run_layout([dict(OBJECTS[0],size=[.04]*3)])

    def test_relative_frame_and_static_object_are_refused(self):
        for text in [WORLD.replace('<pose>','<pose relative_to="other">'),
                     WORLD.replace('<pose>','<static>true</static><pose>')]:
            self.source.write_text(text)
            with self.assertRaises(LayoutError):self.run_layout()

    def test_missing_measured_object_or_wrong_world_refuses_dispatch(self):
        for observation in [{},{'a':[.22,0.,.0175,0.]},{'a':[float('nan'),0.,.0175,0.]}]:
            with self.subTest(observation=observation),self.assertRaises(LayoutError):
                verify_initial(observation,OBJECTS)

    def test_yaw_wrap_and_the_existing_one_mm_initial_guard(self):
        objects = [dict(OBJECTS[0],initial_pose=[.23,.015,.0175,math.pi])]
        report = verify_initial({'a':[.2305,.015,.0175,-math.pi]},objects)
        self.assertAlmostEqual(report['a']['position_error_m'],.0005)
        with self.assertRaises(LayoutError):verify_initial({'a':[.232,.015,.0175,math.pi]},objects)


if __name__=='__main__':unittest.main()
