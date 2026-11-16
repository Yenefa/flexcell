"""When the camera captured a frame, derived from the frame's own stamp.

WHY THIS IS NOT THE CALLBACK TIME: the image arrives whenever delivery finishes,
which is not when it was taken. Recording the callback time as the capture time is
wrong by exactly the delivery delay, and the error is invisible - it shows up as a
perfect zero-gap pairing against a world that had already moved.

WHY THE PHYSICS TRACE IS THE CLOCK REFERENCE: it records, for every step, both the
simulation stamp and the producer's monotonic clock. Those pairs are the only
measured relation between simulation time and a real clock in the run, so a frame's
simulation stamp is interpolated through them. A frame outside the traced range has
no measured relation and is reported UNKNOWN rather than extrapolated, because a
guess written into a manifest is indistinguishable from a measurement afterwards.

Deliberately free of ROS imports: this decision is testable without a graph or a
simulator.
"""
import json
from pathlib import Path


def monotonic_at(anchors, sim_ns):
    """Producer monotonic clock at a simulation stamp, linearly interpolated.

    Returns None rather than extrapolating: outside the traced range there is no
    measured relation, and a guess there would be indistinguishable from a
    measurement once written into the manifest.
    """
    if not anchors or not isinstance(sim_ns, int):
        return None
    lo = hi = None
    for anchor_sim, anchor_mono in anchors:
        if anchor_sim <= sim_ns:
            lo = (anchor_sim, anchor_mono)
        else:
            hi = (anchor_sim, anchor_mono)
            break
    if lo is None or hi is None:
        return None
    if hi[0] == lo[0]:
        return lo[1]
    fraction = (sim_ns - lo[0]) / (hi[0] - lo[0])
    return int(round(lo[1] + fraction * (hi[1] - lo[1])))


def capture_times(out, clock_offset_ns):
    """Give every frame the wall clock of the instant the camera captured it.

    WHY THIS IS NOT DONE IN THE CALLBACK: the image carries a simulation stamp
    taken at capture, but the callback runs whenever delivery finishes. Recording
    the callback time as the capture time is wrong by exactly the delivery delay,
    and that error is invisible - it reads as a perfect zero-gap pairing against a
    world that had already moved.

    The mapping is built from the physics trace, which records, for every step,
    both the simulation stamp and the producer's monotonic clock. Interpolating
    the frame's own simulation stamp through those anchors gives the monotonic
    instant the world was in that state; adding the measured monotonic-to-wall
    offset turns it into wall time. A frame whose stamp falls outside the traced
    range gets captured_wall_ns=None and a named reason instead of a guess.
    """
    frames_path = out / 'frames.jsonl'
    physics_path = out / 'physics.jsonl'
    summary = dict(schema_version=1, resolved=0, unknown=0, unknown_reasons={},
                   clock_offset_ns=clock_offset_ns,
                   note='captured_wall_ns = interpolated monotonic_ns + clock_offset_ns')
    if not frames_path.is_file():
        summary['status'] = 'NO_FRAME_MANIFEST'
        return summary
    anchors = []
    if physics_path.is_file():
        for line in physics_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except ValueError:
                continue
            sim_ns, mono_ns = row.get('sim_ns'), row.get('monotonic_ns')
            if isinstance(sim_ns, int) and isinstance(mono_ns, int):
                anchors.append((sim_ns, mono_ns))
    anchors.sort()
    rows, resolved, unknown = [], 0, {}
    for line in frames_path.read_text().splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        row.pop('captured_wall_ns', None)
        row['capture_time_source'] = 'UNKNOWN'
        sim_ns = row.get('sim_ns')
        wall = monotonic_at(anchors, sim_ns) if isinstance(sim_ns, int) else None
        if wall is None:
            row['captured_wall_ns'] = None
            reason = ('no physics trace to map a simulation stamp onto'
                      if not anchors else
                      'frame stamp lies outside the traced physics range')
            row['capture_time_reason'] = reason
            unknown[reason] = unknown.get(reason, 0) + 1
        else:
            row['captured_wall_ns'] = wall + clock_offset_ns
            row['capture_time_source'] = 'derived_from_physics_trace'
            row.pop('capture_time_reason', None)
            resolved += 1
        rows.append(row)
    if rows or frames_path.is_file():
        frames_path.write_text(''.join(json.dumps(row, allow_nan=False) + '\n'
                                       for row in rows))
    summary.update(resolved=resolved, unknown=sum(unknown.values()),
                   unknown_reasons=unknown)
    return summary


def monotonic_at(anchors, sim_ns):
    """Producer monotonic clock at a simulation stamp, linearly interpolated.

    Returns None rather than extrapolating: outside the traced range there is no
    measured relation, and a guess there would be indistinguishable from a
    measurement once written into the manifest.
    """
    if not anchors or not isinstance(sim_ns, int):
        return None
    lo = hi = None
    for anchor_sim, anchor_mono in anchors:
        if anchor_sim <= sim_ns:
            lo = (anchor_sim, anchor_mono)
        else:
            hi = (anchor_sim, anchor_mono)
            break
    if lo is None or hi is None:
        return None
    if hi[0] == lo[0]:
        return lo[1]
    fraction = (sim_ns - lo[0]) / (hi[0] - lo[0])
    return int(round(lo[1] + fraction * (hi[1] - lo[1])))

