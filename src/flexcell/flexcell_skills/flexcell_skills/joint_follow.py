"""Sampled simulation-physics follow monitor and bounded snapshot watchdog.

The detector consumes simultaneous parent/object Gazebo poses, not TF, a
planning-scene attachment, or the backend's own engagement acknowledgement.
It is a fail-closed sampled check, not continuous contact-grasp qualification.

A monitored session is now anchored on a *pre-attach* reference: the measured
parent/object transform while the body was still detached and the arm at rest
(`PrepositionLatch`). Binding must not move that transform, so the first
attached sample is recorded as an attach jump instead of silently becoming the
reference. Contact-freedom is NOT observable on this topic; it is enforced
offline from raw per-step contact data.
"""
import math
import threading
import time

PREPOSITION_SAMPLES = 6                    # 50 Hz endpoints spanning the full 0.1 s hold
PREPOSITION_WINDOW_NS = 100_000_000
PREPOSITION_SAMPLE_GAP_NS = 20_000_000
PREPOSITION_MAX_SPREAD_M = .001            # half the follow translation limit
PREPOSITION_MAX_SPREAD_RAD = .0015         # ~1/12 of the follow rotation limit
PREPOSITION_MAX_AGE_NS = 300_000_000
PREPOSITION_OBJECTS = ('target_box_a', 'target_box_b')


def _pose(value):
    if not isinstance(value, (list, tuple)) or len(value) != 7:
        raise ValueError('pose must have seven components')
    if any(isinstance(x, bool) or not isinstance(x, (int, float)) or not math.isfinite(x) for x in value):
        raise ValueError('pose contains nonfinite or nonnumeric components')
    q = value[3:]
    norm = math.sqrt(sum(x*x for x in q))
    if not .999 <= norm <= 1.001:
        raise ValueError('pose quaternion is not normalized')
    return list(value[:3]), [x / norm for x in q]


def _multiply(a, b):
    x, y, z, w = a
    u, v, s, t = b
    return [w*u+x*t+y*s-z*v, w*v-x*s+y*t+z*u,
            w*s+x*v-y*u+z*t, w*t-x*u-y*v-z*s]


def relative_pose(parent, child):
    p, q = _pose(parent)
    c, r = _pose(child)
    inv = [-q[0], -q[1], -q[2], q[3]]
    delta = [c[i] - p[i] for i in range(3)]
    rotated = _multiply(_multiply(inv, delta + [0.]), q)
    rotation = _multiply(inv, r)
    if not all(math.isfinite(x) for x in rotated + rotation):
        raise ValueError('relative transform is nonfinite')
    return rotated[:3], rotation


def rotation_angle(a, b):
    """Shortest angle between two unit quaternions, sign-insensitive."""
    return 2 * math.acos(min(1., abs(sum(x*y for x, y in zip(a, b)))))


def mean_transform(transforms):
    """Mean of a bounded hold; equivalent quaternion signs are interchangeable."""
    positions = [item[0] for item in transforms]
    quaternions = [item[1] for item in transforms]
    anchor = quaternions[0]
    aligned = [q if sum(a*b for a,b in zip(anchor,q)) >= 0 else [-v for v in q]
               for q in quaternions]
    mean = [math.fsum(p[i] for p in positions) / len(positions) for i in range(3)]
    q = [math.fsum(v[i] for v in aligned) / len(aligned) for i in range(4)]
    norm = math.sqrt(sum(x*x for x in q))
    if not .999 <= norm <= 1.001:
        raise ValueError('averaged pre-attach quaternion is not normalized')
    return mean + [x/norm for x in q]


def transform_spread(transforms):
    positions = [item[0] for item in transforms]
    quaternions = [item[1] for item in transforms]
    return (max(math.dist(a,b) for a in positions for b in positions),
            max(rotation_angle(a,b) for a in quaternions for b in quaternions))


def follow_failure_detail(reason, result=None, *, motion_may_be_active=False):
    """An unknown motion terminal must prevent reset/recovery/cleanup motion."""
    if not motion_may_be_active:
        state = 'motion was not in progress'
    elif result is None:
        state = 'MotionTerminalUnknown: no terminal motion result'
    elif (getattr(result, 'outcome', 3) == 3 or getattr(result, 'error_code', 33) == 33):
        state = 'MotionTerminalUnknown: executor reported unknown motion state'
    elif (getattr(result, 'outcome', 3) == 0 or not getattr(result, 'execution_started', True)
          or getattr(result, 'stop_confirmed', False)):
        state = 'motion terminal confirmed'
    elif getattr(result, 'outcome', 3) == 2 and getattr(result, 'error_code', 33) == 32:
        # MoveToPose returns CANCELED/ERR_CANCELED for a settled cancellation,
        # including already_completed. Its strict stop_confirmed flag also
        # requires a measurably cut-short trajectory; that is a separate fact.
        # Unsettled or unreadable execution is returned as STATE_UNKNOWN above.
        state = 'motion terminal confirmed'
    else:
        state = 'MotionTerminalUnknown: movement stop was not confirmed'
    return 'physical follow unconfirmed: %s; %s; carry held for reconciliation' % (reason, state)


def check_backend_parameter(client, request_type, expected):
    """Refuse a skill configured for a different carry backend before motion."""
    try:
        if not client.wait_for_service(timeout_sec=2.):
            return False, 'carry backend parameter service unavailable'
        request = request_type.Request()
        request.names = ['carry_backend']
        future = client.call_async(request)
        deadline = time.monotonic() + 2.
        while not future.done() and time.monotonic() < deadline:
            time.sleep(.02)
        if not future.done():
            client.remove_pending_request(future)
            return False, 'carry backend parameter reply timed out'
        result = future.result()
        if (result is None or len(result.values) != 1 or result.values[0].type != 4 or
                result.values[0].string_value != expected):
            return False, 'skill/carry backend configuration mismatch'
        return True, ''
    except Exception as exc:
        return False, 'carry backend parameter query failed: ' + str(exc)


class PrepositionLatch:
    """Buffer detached, at-rest transforms and hand out a pre-attach reference.

    The latch only sees parent/object poses, so it can require "still detached"
    and "the arm is not moving" but it cannot claim contact-freedom: that is
    measured offline from raw contact data, never inferred here.
    """
    def __init__(self, *, clock=time.monotonic_ns, samples=PREPOSITION_SAMPLES,
                 window_ns=PREPOSITION_WINDOW_NS, sample_gap_ns=PREPOSITION_SAMPLE_GAP_NS,
                 max_spread_m=PREPOSITION_MAX_SPREAD_M,
                 max_spread_rad=PREPOSITION_MAX_SPREAD_RAD, max_age_ns=PREPOSITION_MAX_AGE_NS):
        if samples < 2:
            raise ValueError('a preposition reference needs at least two samples')
        self.clock, self.samples, self.window_ns = clock, samples, window_ns
        self.sample_gap_ns, self.max_spread_m, self.max_spread_rad = sample_gap_ns, max_spread_m, max_spread_rad
        self.max_age_ns = max_age_ns
        self.cv = threading.Condition()
        self.buffer = {name: [] for name in PREPOSITION_OBJECTS}

    def feed(self, data):
        """Buffer one detached observation; malformed data leaves the buffer untouched."""
        with self.cv:
            try:
                if not isinstance(data, dict) or type(data.get('schema_version')) is not int \
                        or data['schema_version'] != 1:
                    return
                now, source, sim = self.clock(), data['monotonic_ns'], data['sim_ns']
                if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in (source, sim)):
                    return
                if source > now + 1_000_000 or now - source > self.max_age_ns:
                    return
                for name in PREPOSITION_OBJECTS:
                    obj = data['objects'][name]
                    if obj['joint_component'] is not False:
                        self.buffer[name].clear()  # an attachment ends the detached history
                        continue
                    entry = (sim, source, relative_pose(data['parent_pose'], obj['pose']),
                             _pose(data['parent_pose']), _pose(obj['pose']))
                    history = self.buffer[name]
                    history.append(entry)
                    del history[:-3 * self.samples]
                self.cv.notify_all()
            except (KeyError, TypeError, ValueError):
                return

    def _evaluate(self, object_id):
        history = self.buffer[object_id][-self.samples:]
        if len(history) < self.samples:
            return False, None, 'no detached pre-attach hold of %d samples' % self.samples
        sims = [entry[0] for entry in history]
        if any(b <= a for a, b in zip(sims, sims[1:])):
            return False, None, 'pre-attach hold did not advance monotonically'
        if any(b - a != self.sample_gap_ns for a, b in zip(sims, sims[1:])):
            return False, None, 'pre-attach hold is not an unbroken 50 Hz interval'
        if sims[-1] - sims[0] < self.window_ns:
            return False, None, 'pre-attach hold is shorter than declared'
        age = self.clock() - history[-1][1]
        if age > self.max_age_ns:
            return False, None, 'pre-attach hold is stale at engage time'
        transforms = [entry[2] for entry in history]
        spread_m, spread_rad = transform_spread(transforms)
        if not (math.isfinite(spread_m) and math.isfinite(spread_rad)):
            return False, None, 'pre-attach hold is nonfinite'
        if spread_m > self.max_spread_m or spread_rad > self.max_spread_rad:
            return False, None, ('pre-attach hold is not at rest: %.3g mm / %.3g urad'
                                 % (spread_m * 1e3, spread_rad * 1e6))
        world = {}
        for name, index in (('parent', 3), ('body', 4)):
            position, angle = transform_spread([entry[index] for entry in history])
            if position > self.max_spread_m or angle > self.max_spread_rad:
                return False, None, ('world-frame %s pre-attach hold is not at rest: %.3g mm / %.3g urad'
                                     % (name, position*1e3, angle*1e6))
            world[name] = dict(spread_translation_m=position, spread_rotation_rad=angle)
        try:
            reference = mean_transform(transforms)
        except ValueError as exc:
            return False, None, str(exc)
        return True, reference, dict(
            samples=len(history), window_ns=sims[-1] - sims[0], first_sim_ns=sims[0],
            last_sim_ns=sims[-1], age_ns=age, spread_m=spread_m, spread_rad=spread_rad,
            limits=dict(samples=self.samples, window_ns=self.window_ns, spread_m=self.max_spread_m,
                        spread_rad=self.max_spread_rad, age_ns=self.max_age_ns),
            world_at_rest=world, contact_freedom='NOT_OBSERVABLE_ON_POSE_TOPIC')

    def take(self, object_id, timeout=3.):
        """Wait for a declared pre-attach hold; returns (ok, reference, detail)."""
        if object_id not in PREPOSITION_OBJECTS:
            return False, None, 'unknown preposition object'
        deadline = time.monotonic() + timeout
        with self.cv:
            while True:
                ok, reference, detail = self._evaluate(object_id)
                if ok:
                    return True, reference, detail
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return False, None, detail
                self.cv.wait(min(.02, remaining))


class JointFollowMonitor:
    """Latch a fault until release; all supplied times are monotonic nanoseconds."""
    def __init__(self, *, clock=time.monotonic_ns, max_age_ns=500_000_000,
                 max_sim_gap_ns=80_000_000, max_translation_m=.002,
                 max_rotation_rad=math.pi / 180):
        self.clock, self.max_age_ns, self.max_sim_gap_ns = clock, max_age_ns, max_sim_gap_ns
        self.max_translation_m, self.max_rotation_rad = max_translation_m, max_rotation_rad
        self.cv = threading.Condition()
        self.armed = False
        self.releasing = False
        self.detach_observed = False
        self.fault = ''
        self.reference = None
        self.reference_source = ''
        self.preposition = None
        self.attach_jump = None
        self.object = self.session = ''
        self.started_ns = self.first_source_ns = self.first_sim_ns = 0
        self.last_source_ns = self.last_sim_ns = 0
        self.samples = self.max_gap_ns = 0
        self.max_translation = self.max_rotation = 0.

    def arm(self, object_id, session, reference=None, preposition=None):
        if (object_id not in ('target_box_a', 'target_box_b') or len(session) != 32 or
                any(c not in '0123456789abcdef' for c in session)):
            raise ValueError('invalid follow session')
        if reference is not None:
            _pose(reference)
            if not isinstance(preposition, dict):
                raise ValueError('a declared reference requires its pre-attach evidence')
        with self.cv:
            if self.armed:
                raise RuntimeError('follow monitor already armed')
            self.armed, self.releasing, self.fault = True, False, ''
            self.detach_observed = False
            self.object, self.session = object_id, session
            self.started_ns = self.clock()
            self.first_source_ns = self.first_sim_ns = 0
            self.last_source_ns = self.last_sim_ns = self.samples = self.max_gap_ns = 0
            self.reference = list(reference) if reference is not None else None
            self.reference_source = 'preposition' if reference is not None else ''
            self.preposition = dict(preposition) if preposition is not None else None
            self.attach_jump = None
            self.max_translation = self.max_rotation = 0.

    def _fail(self, reason):
        if not self.fault:
            self.fault = reason
        self.cv.notify_all()

    def reject(self, reason):
        with self.cv:
            if self.armed and not self.releasing:
                self._fail(reason)

    def feed(self, data):
        with self.cv:
            if not self.armed or (self.fault and not self.releasing):
                return
            # A release must not blind the sampler: the attached tail between the last
            # pre-release publish and the true detach is what the release-boundary gate
            # measures, so keep recording it while suppressing the fault it would raise.
            releasing = self.releasing
            try:
                if (not isinstance(data, dict) or type(data.get('schema_version')) is not int or
                        data['schema_version'] != 1):
                    raise ValueError('invalid physics trace schema')
                now = self.clock()
                source, sim = data['monotonic_ns'], data['sim_ns']
                if any(isinstance(x, bool) or not isinstance(x, int) or x < 0 for x in (source, sim)):
                    raise ValueError('invalid physics timestamp')
                if source < self.started_ns:
                    return  # A queued observation from the previous session is not a new sample.
                if source > now + 1_000_000 or now - source > self.max_age_ns:
                    raise ValueError('physics trace is stale or from a different clock')
                if self.last_source_ns and (source <= self.last_source_ns or sim <= self.last_sim_ns):
                    raise ValueError('physics timestamps did not advance')
                if self.reference is not None and self.last_sim_ns:
                    gap = sim - self.last_sim_ns
                    self.max_gap_ns = max(self.max_gap_ns, gap)
                    # A latched fault deliberately stopped follow sampling. Cleanup
                    # may still confirm a fresh detach without erasing that fault.
                    if gap > self.max_sim_gap_ns and not (releasing and self.fault):
                        raise ValueError('physics trace gap exceeds limit')
                obj = data['objects'][self.object]
                attached = obj['joint_component']
                if type(attached) is not bool:
                    raise ValueError('attachment component state is unavailable')
                relative = relative_pose(data['parent_pose'], obj['pose'])
                if not attached:
                    if self.first_sim_ns and not releasing:
                        raise ValueError('attachment component disappeared')
                    if releasing:
                        # The released boundary is covered and the session is complete.
                        self.detach_observed = True
                        self.armed = False
                        self.releasing = False
                        self.cv.notify_all()
                    return
                # Only an attached frame advances the session bounds: a detached frame must
                # not extend last_sim_ns past the sampled evidence it is compared with.
                self.last_source_ns, self.last_sim_ns = source, sim
                if self.reference is None:
                    self.reference = relative[0] + relative[1]
                    self.reference_source = 'first_attached'
                    self.first_source_ns, self.first_sim_ns = source, sim
                elif not self.first_sim_ns:
                    # Binding must not move the measured pre-attach transform.
                    self.attach_jump = (math.dist(relative[0], self.reference[:3]),
                                        rotation_angle(relative[1], self.reference[3:]))
                    self.first_source_ns, self.first_sim_ns = source, sim
                position, orientation = relative
                initial_pos, initial_rot = self.reference[:3], self.reference[3:]
                translation = math.dist(position, initial_pos)
                rotation = rotation_angle(orientation, initial_rot)
                self.max_translation = max(self.max_translation, translation)
                self.max_rotation = max(self.max_rotation, rotation)
                self.samples += 1
                if not releasing and (translation >= self.max_translation_m or
                                      rotation >= self.max_rotation_rad):
                    raise ValueError('measured relative pose exceeded follow limits')
                self.cv.notify_all()
            except (ValueError, KeyError, TypeError) as exc:
                self._fail(str(exc))

    def wait_ready(self, timeout=2.):
        deadline = time.monotonic() + timeout
        with self.cv:
            while self.armed and not self.fault and self.samples < 2:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    self._fail('no confirmed attached physics samples')
                    break
                self.cv.wait(remaining)
            return self._check_locked()

    def _check_locked(self):
        if not self.armed or self.releasing:
            return False, 'follow monitor is not active'
        if not self.fault and self.samples >= 2 and self.clock() - self.last_source_ns > self.max_age_ns:
            self._fail('physics trace stopped or became stale')
        if self.fault:
            return False, self.fault
        if self.samples < 2:
            return False, 'attached physics reference not ready'
        return True, ''

    def check(self):
        with self.cv:
            return self._check_locked()

    def _summary_locked(self):
        return dict(object=self.object, session=self.session, samples=self.samples,
            first_relative_pose=(self.reference[:3] + self.reference[3:]) if self.reference else None,
            reference_source=self.reference_source, preposition=self.preposition,
            attach_jump_translation_m=(self.attach_jump[0] if self.attach_jump else None),
            attach_jump_rotation_rad=(self.attach_jump[1] if self.attach_jump else None),
            first_sim_ns=self.first_sim_ns, last_sim_ns=self.last_sim_ns,
            first_source_ns=self.first_source_ns, last_source_ns=self.last_source_ns,
            max_sample_gap_ns=self.max_gap_ns,
            max_translation_m=self.max_translation, max_rotation_rad=self.max_rotation,
            translation_limit_m=self.max_translation_m, rotation_limit_rad=self.max_rotation_rad,
            active=self.armed, releasing=self.releasing, detach_observed=self.detach_observed,
            fault=self.fault)

    def summary(self):
        with self.cv:
            return self._summary_locked()

    def snapshot(self):
        """Return health and evidence from the same locked observation state."""
        with self.cv:
            ok, reason = self._check_locked()
            return ok, reason, self._summary_locked()

    def begin_release(self):
        with self.cv:
            if self.armed:
                self.releasing = True

    def wait_detached(self, timeout=.3):
        """Wait (bounded) until the trace shows the joint gone.

        A confirmed release only says the guard let go; the last attached publish can
        still arrive afterwards, and the release-boundary gate measures exactly that tail.
        """
        deadline = time.monotonic() + timeout
        with self.cv:
            while self.armed and not self.detach_observed:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break
                self.cv.wait(remaining)
            return self.detach_observed

    def end_release(self, confirmed):
        with self.cv:
            if not confirmed:
                # The caller says the release was not confirmed: keep that fault even if
                # the trace already showed the joint gone.
                self.releasing = False
                self._fail('physical release unconfirmed')
                self.armed = False
                return
            if not self.armed:
                return
            self.releasing = False
            self.armed = False


class SnapshotWatch:
    """Monitor read-only carry snapshots while a skill owns motion."""
    def __init__(self, client, request_type, object_id, session='', *, max_age=.8):
        self.client, self.request_type, self.object_id = client, request_type, object_id
        self.session, self.max_age = session, max_age
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.ready = threading.Event()
        self.fault = ''
        self.last_ok = 0.
        self.last_detail = ''
        self.thread = threading.Thread(target=self._run, name='joint-follow-snapshot', daemon=True)
        self.thread.start()

    def _fail(self, reason):
        with self.lock:
            if not self.fault:
                self.fault = reason
        self.ready.set()

    def _accept(self, result):
        with self.lock:
            valid = (result is not None and result.success and result.state.engaged and
                     result.state.object_id == self.object_id and result.session and
                     (not self.session or result.session == self.session))
            if valid and not self.fault:
                if not self.session: self.session = result.session
                self.last_ok, self.last_detail = time.monotonic(), result.detail
        if not valid:
            self._fail('carry follow snapshot rejected: ' + str(getattr(result, 'detail', 'missing reply')))
        return bool(valid) and not self.problem()

    def _run(self):
        try:
            if not self.client.wait_for_service(timeout_sec=2.):
                self._fail('carry snapshot service unavailable')
                return
            while not self.stop.is_set():
                future = self.client.call_async(self.request_type.Request())
                until = time.monotonic() + 1.8
                while not future.done() and not self.stop.wait(.02) and time.monotonic() < until:
                    pass
                if self.stop.is_set():
                    if not future.done(): self.client.remove_pending_request(future)
                    return
                if not future.done():
                    self.client.remove_pending_request(future)
                    self._fail('carry snapshot reply timed out')
                    return
                if not self._accept(future.result()):
                    return
                self.ready.set()
                self.stop.wait(.1)
        except Exception as exc:
            self._fail('carry snapshot exception: ' + str(exc))

    def start(self, timeout=3.):
        if not self.ready.wait(timeout):
            self._fail('first carry snapshot timed out')
        return not self.problem()

    def problem(self):
        with self.lock:
            if not self.fault and self.last_ok and time.monotonic() - self.last_ok > self.max_age:
                self.fault = 'carry snapshot became stale during motion'
            return self.fault

    def confirm_now(self, timeout=2.):
        if self.problem():
            return False
        try:
            future = self.client.call_async(self.request_type.Request())
            deadline = time.monotonic() + timeout
            while not future.done() and time.monotonic() < deadline:
                time.sleep(.02)
            if not future.done():
                self.client.remove_pending_request(future)
                self._fail('final carry follow snapshot timed out')
                return False
            return self._accept(future.result())
        except Exception as exc:
            self._fail('final carry follow snapshot exception: ' + str(exc))
            return False

    def summary(self):
        with self.lock:
            return dict(session=self.session, last_detail=self.last_detail, fault=self.fault)

    def close(self):
        self.stop.set()
        self.thread.join(timeout=3.)
        if self.thread.is_alive():
            self._fail('carry snapshot worker did not terminate')
        return not self.thread.is_alive()
