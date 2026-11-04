#!/usr/bin/env python3
"""Capture the first N image frames and their upstream tag estimates, read-only.

Gazebo object poses and Observe are deliberately not inputs. This records
availability, not positioning accuracy; compare truth separately at rest.
"""
import argparse
import json
import math
from pathlib import Path
import sys
import time


def stamp(msg):
    return int(msg.header.stamp.sec) * 1_000_000_000 + int(msg.header.stamp.nanosec)


def header(msg):
    return {'stamp_ns': stamp(msg), 'frame_id': msg.header.frame_id}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--calibration', type=Path, required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--frames', type=int, default=5)
    parser.add_argument('--timeout', type=float, default=20.)
    parser.add_argument('--grace', type=float, default=2.)
    args, ros_args = parser.parse_known_args()
    if (not 1 <= args.frames <= 20 or not 0 < args.grace < args.timeout
            or not all(math.isfinite(v) for v in (args.grace, args.timeout))):
        parser.error('require 1..20 frames and 0 < grace < timeout')

    import cv2
    from cv_bridge import CvBridge
    import rclpy
    from rclpy.node import Node
    from rclpy.parameter import Parameter
    from sensor_msgs.msg import CameraInfo, Image
    from apriltag_msgs.msg import AprilTagDetectionArray
    from tf2_msgs.msg import TFMessage
    from flexcell_skills.vision_geometry import observations, validate_calibration

    calibration = json.loads(args.calibration.read_text())
    validate_calibration(calibration)
    args.out.mkdir(parents=True, exist_ok=False)
    rclpy.init(args=ros_args)

    class Capture(Node):
        def __init__(self):
            super().__init__('apriltag_capture', parameter_overrides=[
                Parameter('use_sim_time', value=True)])
            self.images, self.infos, self.detected, self.transforms = {}, {}, {}, {}
            self.last_image_received = None
            self.image_input = None
            self.inputs = [
                self.create_subscription(CameraInfo, '/flexcell/camera/rgb/camera_info',
                                         self.info, 10),
                self.create_subscription(AprilTagDetectionArray, '/flexcell_vision/detections',
                                         self.detections, 10),
                self.create_subscription(TFMessage, '/tf', self.tf, 10),
            ]

        def image(self, msg):
            key = stamp(msg)
            if len(self.images) >= args.frames or key in self.images:
                return
            age = (self.get_clock().now().nanoseconds - key) / 1e9
            error = ''
            if self.images and key < max(self.images):
                error = 'nonmonotonic_image_stamp'
            if age < -.05 or age > 1.:
                error = error or 'image_clock_mismatch_or_stale'
            self.images[key] = (msg, age, error)
            self.last_image_received = time.monotonic()

        def keep(self, mapping, key, value):
            mapping[key] = value
            while len(mapping) > 30:
                del mapping[next(iter(mapping))]

        def info(self, msg):
            self.keep(self.infos, stamp(msg), {**header(msg), 'width': msg.width,
                      'height': msg.height, 'p': list(msg.p), 'd': list(msg.d)})

        def detections(self, msg):
            self.keep(self.detected, stamp(msg), {**header(msg), 'tags': [
                {'id': d.id, 'hamming': d.hamming, 'margin': float(d.decision_margin)}
                for d in msg.detections]})

        def tf(self, msg):
            frames = {tag['frame'] for tag in calibration['tags']}
            for tf in msg.transforms:
                if tf.child_frame_id not in frames:
                    continue
                p, q = tf.transform.translation, tf.transform.rotation
                key = stamp(tf)
                group = self.transforms.setdefault(key, {})
                group[tf.child_frame_id] = {**header(tf),
                    'pose': [p.x, p.y, p.z, q.x, q.y, q.z, q.w]}
                while len(self.transforms) > 30:
                    del self.transforms[next(iter(self.transforms))]

    node = Capture()
    rows = []
    started = time.monotonic()
    try:
        while rclpy.ok() and time.monotonic() - started < args.timeout:
            rclpy.spin_once(node, timeout_sec=.05)
            # Discover metadata endpoints before subscribing to raw frames. This
            # avoids losing the first frame's CameraInfo during DDS discovery;
            # it does not wait for detections, valid tags or a successful pose.
            if node.image_input is None and all(s.get_publisher_count() for s in node.inputs):
                node.image_input = node.create_subscription(Image, '/flexcell/camera/rgb', node.image, 5)
            if (len(node.images) == args.frames and
                    time.monotonic() - node.last_image_received >= args.grace):
                break
        bridge = CvBridge()
        for index, (key, (msg, age, error)) in enumerate(node.images.items()):
            image = {**header(msg), 'width': msg.width, 'height': msg.height, 'error': error}
            row = observations(calibration, image, node.infos.get(key),
                               node.detected.get(key), node.transforms.get(key, {}))
            row['image_age_at_receive_s'] = age
            row['image'] = 'frame-%03d.png' % index
            row['camera_info'] = node.infos.get(key)
            pixels = bridge.imgmsg_to_cv2(msg, desired_encoding='bgr8')
            if not cv2.imwrite(str(args.out / row['image']), pixels):
                raise RuntimeError('image write failed: ' + row['image'])
            rows.append(row)
        complete = len(rows) == args.frames and all(
            obj['available'] for row in rows for obj in row['objects'].values())
        report = dict(source='VISION_APRILTAG', mode='READ_ONLY',
                      status='OBSERVATIONS_AVAILABLE' if complete else 'UNAVAILABLE',
                      accuracy_assessed=False, requested_frames=args.frames,
                      capture_started=node.image_input is not None,
                      start_condition='metadata_publishers_matched',
                      captured_frames=len(rows), frames=rows)
        (args.out / 'observations.json').write_text(json.dumps(report, indent=2, allow_nan=False) + '\n')
        print(json.dumps({k: v for k, v in report.items() if k != 'frames'}))
        return 0 if complete else 1
    finally:
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    sys.exit(main())
