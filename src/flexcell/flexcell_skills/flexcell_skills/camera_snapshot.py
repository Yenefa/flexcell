#!/usr/bin/env python3
"""Capture one frame from the workcell camera and write it as a PNG.

WHAT THIS IS
    A frame grabber. It subscribes to a sensor_msgs/Image topic, waits for a
    frame, REFUSES to accept a frame that is not internally consistent, and
    writes a PNG. Nothing here interprets the picture.

WHAT THIS IS NOT
    It is not perception. It does not say what is in the image, does not locate
    an object, and does not make the robot able to see. It produces a file plus
    a sidecar record of what was measured about that file, so a later judgement
    can be checked against ground truth instead of being trusted.

WHY IT REFUSES INSTEAD OF WRITING SOMETHING
    The failure this tool exists to prevent is the quiet one: no frame arrives,
    the writer produces a black PNG anyway, the run reports "captured", and a
    later analysis treats an empty image as evidence. So the rules are:

      * no frame before the deadline            -> exit 2, no file written
      * frame length inconsistent with geometry  -> exit 3, no file written
      * frame decodes to a single uniform value  -> exit 4, no file written
      * write fails                              -> exit 5, no file written

    "Uniform" is included because an all-zero buffer is exactly what a renderer
    that produced nothing hands you, and it is indistinguishable from a real
    black picture. A caller who genuinely wants a uniform frame must say so
    with --allow-uniform, and the sidecar records that they did.

    In every refusal path the tool exits NON-ZERO and writes NO image, so a
    caller that checks the exit code cannot mistake a refusal for a capture.
"""

import argparse
import hashlib
import json
import os
import sys
import time

# ------------------------------------------------------------------ exit codes
EXIT_OK = 0
EXIT_USAGE = 1
EXIT_NO_FRAME = 2
EXIT_BAD_FRAME = 3
EXIT_UNIFORM = 4
EXIT_WRITE_FAILED = 5
EXIT_INTERPRETER = 6
EXIT_STALE = 7
EXIT_UNPAIRED = 8

# Encodings this tool accepts. Anything else is refused rather than guessed:
# a mis-decoded buffer produces a plausible-looking wrong image.
SUPPORTED_ENCODINGS = {
    'rgb8': (3, 'RGB'),
    'bgr8': (3, 'BGR'),
    'rgba8': (4, 'RGBA'),
    'bgra8': (4, 'BGRA'),
    'mono8': (1, 'L'),
}


class FrameRefused(Exception):
    """A frame was received but cannot be trusted as evidence."""

    def __init__(self, code, reason, detail):
        super().__init__(reason + ': ' + detail)
        self.code = code
        self.reason = reason
        self.detail = detail


# --------------------------------------------------------------- pure checks
def expected_bytes(width, height, step, encoding):
    """Bytes a well-formed buffer must have, or a refusal.

    ROS images are allowed to pad rows: step (bytes per row) can exceed
    width * channels. The DATA LENGTH must still be exactly step * height.
    A truncated or over-long buffer is refused rather than sliced into shape,
    because slicing is what turns a broken frame into a plausible wrong one.
    """
    if type(width) is not int or type(height) is not int or type(step) is not int:
        raise FrameRefused(EXIT_BAD_FRAME, 'bad_geometry',
                           'width/height/step must be integers')
    if width <= 0 or height <= 0:
        raise FrameRefused(EXIT_BAD_FRAME, 'bad_geometry',
                           'width=%r height=%r' % (width, height))
    if encoding not in SUPPORTED_ENCODINGS:
        raise FrameRefused(EXIT_BAD_FRAME, 'unsupported_encoding',
                           '%r is not one of %s'
                           % (encoding, sorted(SUPPORTED_ENCODINGS)))
    channels = SUPPORTED_ENCODINGS[encoding][0]
    minimum = width * channels
    if step < minimum:
        raise FrameRefused(EXIT_BAD_FRAME, 'bad_step',
                           'step=%d is smaller than width*channels=%d'
                           % (step, minimum))
    return step * height


def check_buffer(width, height, step, encoding, data_len):
    """Validate geometry against the actual buffer length. Returns nothing."""
    want = expected_bytes(width, height, step, encoding)
    if data_len != want:
        raise FrameRefused(
            EXIT_BAD_FRAME, 'truncated_or_oversized',
            'expected %d bytes (%dx%d, step %d, %s) but the message carried %d'
            % (want, width, height, step, encoding, data_len))
    return want


def decode_to_array(width, height, step, encoding, data):
    """numpy view of the image, dropping row padding. Refuses on bad geometry."""
    import numpy as np
    check_buffer(width, height, step, encoding, len(data))
    channels = SUPPORTED_ENCODINGS[encoding][0]
    flat = np.frombuffer(data, dtype=np.uint8)
    rows = flat.reshape(height, step)
    pixels = rows[:, :width * channels]
    if channels == 1:
        return pixels.reshape(height, width)
    return pixels.reshape(height, width, channels)


def uniformity(width, height, step, encoding, data):
    """(is_uniform, min, max, mean) over the pixel bytes.

    Computed on the FULL buffer including padding: padding bytes come from the
    renderer too, so if they differ the buffer is not a flat fill and this must
    not be reported as uniform.
    """
    import numpy as np
    check_buffer(width, height, step, encoding, len(data))
    flat = np.frombuffer(data, dtype=np.uint8)
    low, high = int(flat.min()), int(flat.max())
    return (low == high), low, high, float(flat.mean())


def validate_frame(width, height, step, encoding, data, allow_uniform=False):
    """The complete acceptance rule for one frame. Returns a summary dict.

    Every refusal carries a machine-readable reason so a caller can branch on
    it, and the caller never has to parse an English sentence.
    """
    check_buffer(width, height, step, encoding, len(data))
    uniform, low, high, mean = uniformity(width, height, step, encoding, data)
    if uniform and not allow_uniform:
        raise FrameRefused(
            EXIT_UNIFORM, 'uniform_image',
            'every byte of the %dx%d %s frame is %d (mean %.1f); a renderer that '
            'produced nothing looks exactly like this, so the frame is refused '
            'rather than saved as evidence (use --allow-uniform to override)'
            % (width, height, encoding, low, mean))
    return dict(width=width, height=height, step=step, encoding=encoding,
                bytes=len(data), uniform=bool(uniform),
                min_byte=low, max_byte=high, mean_byte=round(mean, 4),
                sha256=hashlib.sha256(bytes(data)).hexdigest())


# ------------------------------------------------------------------ PNG write
def write_png(path, width, height, step, encoding, data):
    """Write the frame as PNG. Returns the file size in bytes.

    Pillow does the encoding: it is installed, it is what the harness reads
    back, and it removes any question of a hand-rolled PNG being subtly wrong.
    """
    from PIL import Image
    array = decode_to_array(width, height, step, encoding, data)
    # Pillow's mode must describe the array AFTER any channel reordering, and
    # a wrong mode is the classic way a correct buffer becomes a wrong image.
    if encoding == 'bgr8':
        array, mode = array[:, :, ::-1], 'RGB'
    elif encoding == 'bgra8':
        array, mode = array[:, :, [2, 1, 0, 3]], 'RGBA'
    elif encoding == 'rgb8':
        mode = 'RGB'
    elif encoding == 'rgba8':
        mode = 'RGBA'
    else:                                   # mono8
        mode = 'L'
    image = Image.fromarray(array, mode=mode)
    directory = os.path.dirname(os.path.abspath(path))
    if directory:
        os.makedirs(directory, exist_ok=True)
    # Write to a temporary name and rename: a half-written PNG must never be
    # left at the destination where a later step would pick it up.
    temporary = path + '.partial'
    image.save(temporary, format='PNG')
    os.replace(temporary, path)
    return os.path.getsize(path)


def sample_truth(objects, world='empty', timeout_s=8.0):
    """Ground-truth poses read immediately after the frame. Returns a record.

    WHY IN THIS PROCESS AND NOT IN THE PAIRING TOOL
        The pairing claim is "truth was measured at the same instant as this
        frame". Sampling here, microseconds after the frame lands, makes that
        claim about a gap the tool can state exactly. Sampling later in a
        different process would make the gap depend on how long the caller took
        to get there, and would quietly widen without anyone noticing.
    """
    import time as _time
    started = _time.time_ns()
    try:
        from flexcell_skills.common import sample_gz_pose
    except Exception as exc:                       # noqa: BLE001
        return dict(available=False, wall_ns=started, objects={},
                    source='GZ_GROUND_TRUTH',
                    error='ground-truth sampler unavailable: %s: %s'
                          % (type(exc).__name__, exc))
    poses, errors = {}, {}
    for name in objects:
        pose, error = sample_gz_pose(name, timeout_s=timeout_s, world=world)
        if pose is None:
            errors[name] = error
            continue
        poses[name] = [round(float(v), 6) for v in pose[0]]
    return dict(available=bool(poses), wall_ns=_time.time_ns(),
                source='GZ_GROUND_TRUTH', objects=poses, errors=errors)


def write_sidecar(path, record):
    """Write the JSON record next to the image, atomically."""
    temporary = path + '.partial'
    with open(temporary, 'w', encoding='utf-8') as stream:
        json.dump(record, stream, indent=2, sort_keys=True, allow_nan=False)
        stream.write('\n')
    os.replace(temporary, path)


# --------------------------------------------------------------------- ROS IO
def accept_message(message, topic, min_stamp_ns=0, allow_uniform=False):
    """Turn one sensor_msgs/Image into (record, payload) or raise FrameRefused.

    Kept out of the node callback so the acceptance rule can be exercised with
    real message objects and no live publisher - the node then does nothing but
    hand messages here and store the result.
    """
    stamp_ns = (int(message.header.stamp.sec) * 10 ** 9
                + int(message.header.stamp.nanosec))
    if stamp_ns < min_stamp_ns:
        raise FrameRefused(
            EXIT_STALE, 'frame_predates_request',
            'frame stamp %d predates the requested moment %d; a queued frame '
            'from before the event must not be labelled as a frame of it'
            % (stamp_ns, min_stamp_ns))
    summary = validate_frame(int(message.width), int(message.height),
                             int(message.step), str(message.encoding),
                             message.data, allow_uniform)
    record = dict(summary, stamp_ns=stamp_ns,
                  frame_id=str(message.header.frame_id), topic=topic)
    return record, bytes(message.data)


def capture(topic, timeout_s, min_stamp_ns=0, allow_uniform=False):
    """Block until one acceptable frame arrives, or raise FrameRefused.

    Returns (record, payload). A silent topic raises EXIT_NO_FRAME; a topic
    that publishes only unusable frames re-raises the LAST refusal, so the
    caller learns why the frames were rejected instead of being told "timeout".
    """
    import rclpy
    from rclpy.node import Node
    from rclpy.qos import QoSProfile, ReliabilityPolicy, HistoryPolicy
    from sensor_msgs.msg import Image

    state = {'result': None, 'payload': None, 'messages': 0,
             'refusals': [], 'last_error': None}

    class Grabber(Node):
        def __init__(self):
            super().__init__('flexcell_camera_snapshot')
            # BEST_EFFORT matches how the gz bridge publishes sensor data. A
            # RELIABLE subscription against a BEST_EFFORT publisher never
            # matches, and would look exactly like "the camera publishes
            # nothing" - the wrong diagnosis for the wrong reason.
            qos = QoSProfile(depth=5, history=HistoryPolicy.KEEP_LAST,
                             reliability=ReliabilityPolicy.BEST_EFFORT)
            self.create_subscription(Image, topic, self._on_image, qos)

        def _on_image(self, message):
            if state['result'] is not None:
                return
            state['messages'] += 1
            try:
                record, payload = accept_message(message, topic, min_stamp_ns,
                                                 allow_uniform)
            except FrameRefused as exc:
                state['refusals'].append(exc.reason)
                state['last_error'] = exc
                return
            state['result'], state['payload'] = record, payload

    rclpy.init()
    node = Grabber()
    deadline = time.monotonic() + float(timeout_s)
    try:
        while time.monotonic() < deadline and state['result'] is None:
            rclpy.spin_once(node, timeout_sec=0.1)
    finally:
        result, payload = state['result'], state['payload']
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

    if result is not None:
        return result, payload
    if state['last_error'] is not None:
        # Frames DID arrive and every one was refused. Reporting that as a
        # timeout would hide the actual cause and send the reader looking for
        # a camera that is in fact publishing.
        error = state['last_error']
        raise FrameRefused(
            error.code, error.reason,
            '%d frame(s) arrived but none was usable; last refusal: %s'
            % (state['messages'], error.detail))
    raise FrameRefused(
        EXIT_NO_FRAME, 'no_frame',
        'no %s frame arrived within %.1fs (subscribed, 0 messages). The camera '
        'is not publishing: check that the stack was launched with '
        'camera:=true and that the image bridge is running'
        % (topic, float(timeout_s)))


def main(argv=None):
    parser = argparse.ArgumentParser(
        description='Capture one camera frame to a PNG, or fail loudly.')
    parser.add_argument('--topic', default='/flexcell/camera/rgb')
    parser.add_argument('--out', required=True, help='PNG path to write')
    parser.add_argument('--timeout', type=float, default=20.0,
                        help='seconds to wait for a usable frame')
    parser.add_argument('--allow-uniform', action='store_true',
                        help='accept a frame whose every byte is identical')
    parser.add_argument('--sidecar', default=None,
                        help='JSON record path (default: <out>.json)')
    parser.add_argument('--label', default='',
                        help='free-text label recorded in the sidecar')
    parser.add_argument('--min-stamp-ns', type=int, default=0,
                        help='reject frames whose sim stamp predates this')
    parser.add_argument('--truth-objects', nargs='*', default=None,
                        help='object names to sample ground truth for, right '
                             'after the frame; recorded in the sidecar so the '
                             'pairing tool does not have to guess')
    parser.add_argument('--world', default='empty')
    args = parser.parse_args(argv)

    started = time.monotonic()
    try:
        frame, payload = capture(args.topic, args.timeout,
                                 min_stamp_ns=args.min_stamp_ns,
                                 allow_uniform=args.allow_uniform)
    except FrameRefused as exc:
        print('CAPTURE_REFUSED %s: %s' % (exc.reason, exc.detail),
              file=sys.stderr)
        print(json.dumps({'ok': False, 'reason': exc.reason,
                          'detail': exc.detail, 'exit_code': exc.code}))
        return exc.code
    except Exception as exc:                       # noqa: BLE001
        print('CAPTURE_FAILED %s: %s' % (type(exc).__name__, exc),
              file=sys.stderr)
        print(json.dumps({'ok': False, 'reason': 'interpreter_error',
                          'detail': '%s: %s' % (type(exc).__name__, exc),
                          'exit_code': EXIT_INTERPRETER}))
        return EXIT_INTERPRETER

    # Truth is sampled BEFORE the PNG is written, and a requested-but-missing
    # truth is recorded in the sidecar rather than dropped: the frame is real,
    # the pairing is not, and the exit code has to distinguish those.
    truth = None
    if args.truth_objects:
        truth = sample_truth(args.truth_objects, args.world)
        if not truth['available']:
            print('TRUTH_UNAVAILABLE %s'
                  % json.dumps(truth.get('errors', {})), file=sys.stderr)

    try:
        size = write_png(args.out, frame['width'], frame['height'],
                         frame['step'], frame['encoding'], payload)
    except Exception as exc:                       # noqa: BLE001
        print('CAPTURE_WRITE_FAILED %s: %s' % (type(exc).__name__, exc),
              file=sys.stderr)
        print(json.dumps({'ok': False, 'reason': 'write_failed',
                          'detail': str(exc), 'exit_code': EXIT_WRITE_FAILED}))
        return EXIT_WRITE_FAILED

    record = dict(frame, ok=True, label=args.label,
                  path=os.path.abspath(args.out), png_bytes=size,
                  elapsed_s=round(time.monotonic() - started, 3),
                  allow_uniform=bool(args.allow_uniform),
                  captured_wall_ns=time.time_ns())
    if truth is not None:
        record['truth'] = truth
    sidecar = args.sidecar or (args.out + '.json')
    try:
        write_sidecar(sidecar, record)
    except Exception as exc:                       # noqa: BLE001
        print('CAPTURE_SIDECAR_FAILED %s: %s' % (type(exc).__name__, exc),
              file=sys.stderr)
        print(json.dumps({'ok': False, 'reason': 'sidecar_failed',
                          'detail': str(exc), 'exit_code': EXIT_WRITE_FAILED}))
        return EXIT_WRITE_FAILED
    print(json.dumps(record))
    if truth is not None and not truth['available']:
        # The image exists and is valid; what is missing is the ground truth
        # that would let anyone check a visual claim against reality. Exit
        # non-zero so a caller cannot treat "captured" as "paired".
        return EXIT_UNPAIRED
    return EXIT_OK


if __name__ == '__main__':
    sys.exit(main())
