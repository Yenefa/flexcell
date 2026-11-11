"""The snapshot tool must refuse rather than produce evidence it does not have.

WHY THESE TESTS ARE ABOUT REFUSAL
    A frame grabber that writes a PNG in every situation is worse than one that
    fails: a black 640x480 file looks like data. Every refusal path below is a
    situation where a naive implementation would have written a file and
    reported success, and where a later analysis would then have treated an
    empty image as evidence about the world.

    The exit codes are part of the contract, not implementation detail: a
    caller branches on them, and the report quotes them.
"""
import hashlib
import json
import os

import numpy as np
import pytest

from flexcell_skills import camera_snapshot as snap


def frame(width=4, height=3, channels=3, encoding='rgb8', step=None, fill=None):
    """A small valid buffer, optionally with padding or a fixed fill."""
    step = step if step is not None else width * channels
    data = bytearray(step * height)
    if fill is None:
        for index in range(len(data)):
            data[index] = (index * 7) % 251 + 1        # never 0, never uniform
    else:
        for index in range(len(data)):
            data[index] = fill
    return dict(width=width, height=height, step=step, encoding=encoding,
                data=bytes(data))


# ------------------------------------------------------------- exit codes
def test_exit_codes_are_distinct_and_non_zero_for_every_refusal():
    codes = {snap.EXIT_NO_FRAME, snap.EXIT_BAD_FRAME, snap.EXIT_UNIFORM,
             snap.EXIT_WRITE_FAILED, snap.EXIT_INTERPRETER, snap.EXIT_USAGE,
             snap.EXIT_STALE, snap.EXIT_UNPAIRED}
    assert 0 not in codes
    assert len(codes) == 8


def test_a_frame_without_requested_truth_is_not_reported_as_a_clean_capture():
    """An image is not a pair. Missing truth must be visible in the exit code.

    The frame is genuine, so it is still written and its sidecar still carries
    truth.available=False; what must not happen is exit 0, which a caller would
    read as "captured and paired".
    """
    assert snap.EXIT_UNPAIRED != snap.EXIT_OK
    assert snap.EXIT_UNPAIRED not in (snap.EXIT_NO_FRAME, snap.EXIT_BAD_FRAME,
                                      snap.EXIT_UNIFORM)


def fake_common(monkeypatch, sampler):
    """A stand-in flexcell_skills.common, so these tests need no ROS install.

    The real common.py imports flexcell_interfaces, which is a built ROS
    package. Injecting a module keeps the unit tests runnable on a bare
    interpreter - the thing being tested here is how sample_truth REACTS to a
    sampler, not that the sampler works (that is the live capture's job).
    """
    import sys
    import types
    module = types.ModuleType('flexcell_skills.common')
    module.sample_gz_pose = sampler
    monkeypatch.setitem(sys.modules, 'flexcell_skills.common', module)


def test_sample_truth_reports_unavailable_instead_of_raising(monkeypatch):
    fake_common(monkeypatch, lambda *a, **k: (None, 'pose stream is not flowing'))
    result = snap.sample_truth(['target_box_a'])
    assert result['available'] is False
    assert result['objects'] == {}
    assert 'pose stream is not flowing' in result['errors']['target_box_a']
    # The record still has a wall clock, so a caller can say WHEN it failed.
    assert isinstance(result['wall_ns'], int)


def test_a_missing_sampler_is_reported_not_raised(monkeypatch):
    import sys
    monkeypatch.setitem(sys.modules, 'flexcell_skills.common', None)
    result = snap.sample_truth(['target_box_a'])
    assert result['available'] is False
    assert 'ground-truth sampler unavailable' in result['error']


def test_sample_truth_keeps_only_objects_it_actually_measured(monkeypatch):
    fake_common(monkeypatch,
                lambda name, **k: ((([0.1, 0.2, 0.3], [0., 0., 0., 1.]), None)
                                   if name == 'target_box_a'
                                   else (None, 'not seen')))
    result = snap.sample_truth(['target_box_a', 'target_box_b'])
    assert result['available'] is True
    assert set(result['objects']) == {'target_box_a'}
    assert 'target_box_b' in result['errors']


# ------------------------------------------------------- buffer validation
def test_a_well_formed_frame_is_accepted():
    f = frame()
    summary = snap.validate_frame(f['width'], f['height'], f['step'],
                                  f['encoding'], f['data'])
    assert summary['bytes'] == len(f['data'])
    assert summary['uniform'] is False
    assert summary['sha256'] == hashlib.sha256(f['data']).hexdigest()


def test_truncated_buffer_is_refused_not_padded():
    """The classic silent corruption: fewer bytes than the geometry requires."""
    f = frame()
    with pytest.raises(snap.FrameRefused) as exc:
        snap.validate_frame(f['width'], f['height'], f['step'], f['encoding'],
                            f['data'][:-5])
    assert exc.value.code == snap.EXIT_BAD_FRAME
    assert exc.value.reason == 'truncated_or_oversized'


def test_oversized_buffer_is_refused_too():
    f = frame()
    with pytest.raises(snap.FrameRefused) as exc:
        snap.validate_frame(f['width'], f['height'], f['step'], f['encoding'],
                            f['data'] + b'\x00')
    assert exc.value.reason == 'truncated_or_oversized'


@pytest.mark.parametrize('width,height,step,encoding,reason', [
    (0, 3, 9, 'rgb8', 'bad_geometry'),
    (4, -1, 9, 'rgb8', 'bad_geometry'),
    (4, 3, 9, 'yuv422', 'unsupported_encoding'),
    (4, 3, 2, 'rgb8', 'bad_step'),          # step < width*channels
])
def test_impossible_geometry_is_refused_with_a_named_reason(width, height, step,
                                                            encoding, reason):
    with pytest.raises(snap.FrameRefused) as exc:
        snap.expected_bytes(width, height, step, encoding)
    assert exc.value.reason == reason


def test_row_padding_is_allowed_and_stripped():
    """ROS images may pad rows; step > width*channels is legal, not a defect."""
    f = frame(width=4, height=3, channels=3, step=16)
    summary = snap.validate_frame(f['width'], f['height'], f['step'],
                                  f['encoding'], f['data'])
    assert summary['step'] == 16
    array = snap.decode_to_array(f['width'], f['height'], f['step'],
                                 f['encoding'], f['data'])
    assert array.shape == (3, 4, 3)         # padding dropped


# ------------------------------------------------------------ uniform check
def test_an_all_zero_frame_is_refused():
    """A renderer that produced nothing hands you exactly this."""
    f = frame(fill=0)
    with pytest.raises(snap.FrameRefused) as exc:
        snap.validate_frame(f['width'], f['height'], f['step'], f['encoding'],
                            f['data'])
    assert exc.value.code == snap.EXIT_UNIFORM
    assert exc.value.reason == 'uniform_image'


def test_a_uniform_frame_can_be_accepted_explicitly_and_is_recorded():
    f = frame(fill=0)
    summary = snap.validate_frame(f['width'], f['height'], f['step'],
                                  f['encoding'], f['data'], allow_uniform=True)
    assert summary['uniform'] is True
    assert summary['min_byte'] == summary['max_byte'] == 0


def test_uniformity_counts_padding_bytes():
    """Padding comes from the renderer too: if it differs the frame is not flat."""
    f = frame(width=4, height=3, step=16)
    data = bytearray(f['data'])
    for row in range(3):
        data[row * 16 + 13] = 0            # one padding byte differs
    uniform, low, high, _mean = snap.uniformity(4, 3, 16, 'rgb8', bytes(data))
    assert uniform is False


# --------------------------------------------------------------- PNG writing
def test_png_is_written_and_reread_at_the_right_size(tmp_path):
    from PIL import Image
    f = frame(width=6, height=5)
    path = str(tmp_path / 'frame.png')
    size = snap.write_png(path, f['width'], f['height'], f['step'],
                          f['encoding'], f['data'])
    assert size == os.path.getsize(path) > 0
    with Image.open(path) as image:
        assert image.size == (6, 5)
        assert image.mode == 'RGB'


def test_bgr8_is_reordered_so_the_png_is_not_colour_swapped():
    """A BGR buffer written as RGB is a plausible-looking wrong image."""
    from PIL import Image
    import tempfile
    # One pixel, pure red in BGR order = (0, 0, 255)
    data = bytes([0, 0, 255])
    with tempfile.TemporaryDirectory() as directory:
        path = os.path.join(directory, 'bgr.png')
        snap.write_png(path, 1, 1, 3, 'bgr8', data)
        with Image.open(path) as image:
            assert image.convert('RGB').getpixel((0, 0)) == (255, 0, 0)


def test_no_partial_file_is_left_behind(tmp_path):
    f = frame()
    path = str(tmp_path / 'ok.png')
    snap.write_png(path, f['width'], f['height'], f['step'], f['encoding'],
                   f['data'])
    assert sorted(os.listdir(tmp_path)) == ['ok.png']


def test_sidecar_is_valid_json_with_no_nan(tmp_path):
    record = dict(width=6, height=5, mean_byte=1.5, direction_cos=None)
    path = str(tmp_path / 'side.json')
    snap.write_sidecar(path, record)
    text = open(path, encoding='utf-8').read()
    assert 'NaN' not in text
    assert json.loads(text) == record


# ------------------------------------------------------- the capture contract
def image_message(width=4, height=3, encoding='rgb8', step=None, fill=None,
                  stamp_ns=1_000_000_000, frame_id='flexcell_camera_link'):
    """A real sensor_msgs/Image, so accept_message is exercised for real."""
    from sensor_msgs.msg import Image
    channels = SUPPORTED_CHANNELS.get(encoding, 2)   # unknown encodings still need a buffer
    f = frame(width, height, channels, encoding, step, fill)
    message = Image()
    message.width, message.height = f['width'], f['height']
    message.step, message.encoding = f['step'], f['encoding']
    message.data = f['data']
    message.header.frame_id = frame_id
    message.header.stamp.sec = stamp_ns // 10 ** 9
    message.header.stamp.nanosec = stamp_ns % 10 ** 9
    return message


SUPPORTED_CHANNELS = {'rgb8': 3, 'bgr8': 3, 'rgba8': 4, 'bgra8': 4, 'mono8': 1}


def test_a_real_image_message_is_accepted_and_carries_its_stamp():
    record, payload = snap.accept_message(image_message(), '/flexcell/camera/rgb')
    assert record['width'] == 4 and record['height'] == 3
    assert record['stamp_ns'] == 1_000_000_000
    assert record['frame_id'] == 'flexcell_camera_link'
    assert payload == frame()['data']


def test_a_queued_frame_from_before_the_event_is_refused():
    """The timing lie: a pre-motion frame labelled as an after-stage frame."""
    message = image_message(stamp_ns=4_000_000_000)
    with pytest.raises(snap.FrameRefused) as exc:
        snap.accept_message(message, '/flexcell/camera/rgb',
                            min_stamp_ns=5_000_000_000)
    assert exc.value.code == snap.EXIT_STALE
    assert exc.value.reason == 'frame_predates_request'


def test_a_truncated_real_message_is_refused():
    message = image_message()
    message.data = message.data[:-3]
    with pytest.raises(snap.FrameRefused) as exc:
        snap.accept_message(message, '/flexcell/camera/rgb')
    assert exc.value.code == snap.EXIT_BAD_FRAME
    assert exc.value.reason == 'truncated_or_oversized'


def test_a_black_real_message_is_refused():
    message = image_message(fill=0)
    with pytest.raises(snap.FrameRefused) as exc:
        snap.accept_message(message, '/flexcell/camera/rgb')
    assert exc.value.code == snap.EXIT_UNIFORM


def test_a_malformed_message_carries_a_reason_not_a_traceback():
    """Every refusal is typed, so a caller never parses English."""
    message = image_message(encoding='yuv422', step=8)
    with pytest.raises(snap.FrameRefused) as exc:
        snap.accept_message(message, '/flexcell/camera/rgb')
    assert exc.value.reason == 'unsupported_encoding'
    assert exc.value.code == snap.EXIT_BAD_FRAME
