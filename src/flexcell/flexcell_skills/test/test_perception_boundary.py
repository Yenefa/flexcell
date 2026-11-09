"""P2-E: the ground-truth path and the camera path have a checkable boundary."""
import ast
import unittest
from pathlib import Path

from flexcell_skills import vision_geometry, visual_region_plan

PACKAGE = Path(__file__).resolve().parents[1] / "flexcell_skills"
CONTRACTS = PACKAGE / "contracts"

#: modules that must never touch an actuator or a simulator
PURE_PERCEPTION = ("vision_geometry.py", "visual_region_plan.py")

ACTUATOR_MARKERS = ("ActionClient", "create_publisher", "gz_publish",
                    "MoveIt", "ApplyPlanningScene", "GripperCommand")


def _source(name, base=None):
    return ((base or PACKAGE) / name).read_text(encoding="utf-8")


class TestPerceptionIsReadOnly(unittest.TestCase):

    def test_perception_modules_import_no_actuator_or_simulator_api(self):
        for name in PURE_PERCEPTION:
            with self.subTest(module=name):
                tree = ast.parse(_source(name))
                imported = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        imported.add((node.module or "").split(".")[-1])
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            imported.add(alias.name.split(".")[0])
                for forbidden in ("rclpy", "rclpy.action", "moveit", "gz"):
                    self.assertNotIn(forbidden, imported,
                                     "%s must not import %s" % (name, forbidden))

    def test_perception_modules_define_no_ros_entity(self):
        # an AST scan, not a text scan: a docstring may legitimately name an API
        for name in PURE_PERCEPTION:
            with self.subTest(module=name):
                tree = ast.parse(_source(name))
                called = {node.func.attr for node in ast.walk(tree)
                          if isinstance(node, ast.Call)
                          and isinstance(node.func, ast.Attribute)}
                for marker in ("create_publisher", "create_client",
                               "create_subscription", "send_goal_async"):
                    self.assertNotIn(marker, called)


class TestGroundTruthBoundary(unittest.TestCase):

    def test_observe_declares_its_source_explicitly(self):
        text = _source("observe_server.py")
        self.assertIn("declare_parameter('source', 'SIMULATION_GROUND_TRUTH')",
                      text)
        self.assertIn("ws.source = self._source", text)

    def test_a_composite_rejects_a_non_ground_truth_observation(self):
        text = _source("composite.py", CONTRACTS)
        self.assertIn("!= 'SIMULATION_GROUND_TRUTH'", text)

    def test_the_two_paths_are_documented_as_separate(self):
        text = _source("vision_geometry.py")
        self.assertIn("No simulator state or actuator interfaces", text)

    def test_camera_geometry_needs_a_complete_calibration(self):
        calibration = {"camera_sdf_pose": [0, 0, 1, 0, 0, 0],
                       "tag_size_m": 0.05, "camera_frame": "camera",
                       "tags": [{"id": 0, "object": "target_box_a",
                                 "frame": "tag_0", "tag_to_center": [0, 0, 0, 0, 0, 0, 1]}]}
        vision_geometry.validate_calibration(calibration)
        with self.assertRaises(ValueError):
            vision_geometry.validate_calibration(dict(calibration, tag_size_m=0))
        with self.assertRaises(ValueError):
            vision_geometry.validate_calibration(dict(calibration, tags=[]))

    def test_an_unmatched_frame_never_supplies_a_pose(self):
        calibration = {"camera_sdf_pose": [0, 0, 1, 0, 0, 0],
                       "tag_size_m": 0.05, "camera_frame": "camera",
                       "tags": [{"id": 0, "object": "target_box_a",
                                 "frame": "tag_0", "tag_to_center": [0, 0, 0, 0, 0, 0, 1]}]}
        image = {"stamp_ns": 10, "frame_id": "camera", "width": 640, "height": 480}
        result = vision_geometry.observations(calibration, image, None, None, {})
        self.assertEqual(result["source"], "VISION_APRILTAG")
        entry = result["objects"]["target_box_a"]
        self.assertFalse(entry["available"])
        self.assertEqual(entry["reason"], "camera_info_unmatched")


class TestCameraFrameConversion(unittest.TestCase):

    def test_optical_conversion_is_a_rigid_transform(self):
        pose = vision_geometry.optical_pose([1.0, 2.0, 3.0, 0.0, 0.0, 0.0])
        self.assertEqual(len(pose), 7)
        self.assertAlmostEqual(sum(v * v for v in pose[3:]), 1.0, places=9)

    def test_a_non_finite_extrinsic_is_refused(self):
        with self.assertRaises(ValueError):
            vision_geometry.optical_pose([0, 0, 0, 0, 0, float("nan")])
        with self.assertRaises(ValueError):
            vision_geometry.optical_pose([0, 0, 0])


if __name__ == "__main__":
    unittest.main()
