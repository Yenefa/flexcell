"""Engage/release pairing and 20 Hz sampling for the carry-offset probe.

Pure logic: the ROS node only feeds it snapshots and a clock. Keeping the rules
here means they can be tested without a simulator, and the node stays a thin
adapter that publishes nothing.

A snapshot is a plain dict:

    {"revision": 12,
     "source": "SIMULATION_GROUND_TRUTH",
     "objects": {"target_box_a": {"pose": ((x, y, z), (qx, qy, qz, qw)),
                                  "available": True,
                                  "pose_age_s": 0.02}},
     "robot": {"ee_pose": ((x, y, z), (qx, qy, qz, qw)),
               "ee_frame": "end_effector_link"}}

Rows follow the schema in issue #261, plus `object_quat_in_world` so the
transform can be recomputed from the row alone.
"""
from geometry import object_in_tcp

ENGAGE = 'engage'
GRASP = 'grasp'
CARRY = 'carry'
RELEASE = 'release'


class CarryOffsetRecorder:
    def __init__(self, object_name, rate_hz=20.0, max_age_s=0.5, settle_s=1.0):
        if rate_hz <= 0:
            raise ValueError('rate_hz must be positive')
        self.object_name = object_name
        self.period_ns = int(1e9 / rate_hz)
        self.max_age_s = max_age_s
        self.settle_ns = int(float(settle_s) * 1e9)
        self.rows = []
        self.skips = []
        self.engaged = False
        self.session = None
        self.backend = None
        self._snapshot = None
        self._last_sample_ns = None
        self._last_revision = None
        self._grasp_due_ns = None
        self._grasp_emitted = False

    # -- inputs ---------------------------------------------------------
    def on_world(self, snapshot):
        self._snapshot = snapshot

    def on_carry(self, engaged, object_id, now_ns, backend=None):
        """Record the transition, then emit one event row for it."""
        was = self.engaged
        self.engaged = bool(engaged)
        if backend:
            self.backend = backend
        if self.engaged and not was:
            self.session = object_id
            if object_id:
                # dual_object carries a different box; switch only when the id is
                # actually a tracked object (CarryState carries the object name)
                tracked = (self._snapshot or {}).get('objects') or {}
                if object_id in tracked:
                    self.object_name = object_id
            self._last_sample_ns = None
            self._last_revision = None
            self._grasp_due_ns = now_ns + self.settle_ns
            self._grasp_emitted = False
            if self._emit(ENGAGE, now_ns):
                # the engage row is the first sample of this session
                self._last_sample_ns = now_ns
        elif was and not self.engaged:
            self._emit(RELEASE, now_ns)
            self.session = None

    def tick(self, now_ns):
        """Sample at `rate_hz` while carrying, at most one row per revision."""
        if not self.engaged:
            return
        if (not self._grasp_emitted and self._grasp_due_ns is not None
                and now_ns >= self._grasp_due_ns):
            if self._emit(GRASP, now_ns):
                self._grasp_emitted = True
                self._last_sample_ns = now_ns
                self._last_revision = (self._snapshot or {}).get('revision')
                return
        if self._last_sample_ns is not None and now_ns - self._last_sample_ns < self.period_ns:
            return
        revision = (self._snapshot or {}).get('revision')
        if revision is not None and revision == self._last_revision:
            self._last_sample_ns = now_ns
            return
        if self._emit(CARRY, now_ns):
            self._last_sample_ns = now_ns
            self._last_revision = revision

    # -- output ---------------------------------------------------------
    def _ready(self):
        snapshot = self._snapshot
        if not snapshot:
            return None, 'no world snapshot'
        obj = (snapshot.get('objects') or {}).get(self.object_name)
        if not obj:
            return None, 'object %r absent' % self.object_name
        if not obj.get('available', True):
            return None, 'object %r unavailable' % self.object_name
        age = obj.get('pose_age_s')
        if age is not None and age > self.max_age_s:
            return None, 'object sample stale (%.3f s)' % age
        robot = snapshot.get('robot') or {}
        if not robot.get('ee_pose'):
            return None, 'end-effector pose missing'
        return (obj, robot), None

    def _emit(self, event, now_ns):
        ready, reason = self._ready()
        if ready is None:
            self.skips.append(dict(t_ns=now_ns, event=event, reason=reason))
            return False
        obj, robot = ready
        object_pose = obj['pose']
        ee_pose = robot['ee_pose']
        row = dict(
            t_ns=now_ns,
            event=event,
            object=self.object_name,
            world_revision=self._snapshot.get('revision'),
            source=self._snapshot.get('source'),
            object_in_world=list(object_pose[0]),
            object_quat_in_world=list(object_pose[1]),
            tcp_in_world=list(ee_pose[0]) + list(ee_pose[1]),
            tcp_frame=robot.get('ee_frame'),
            object_in_tcp=object_in_tcp(object_pose, ee_pose),
            carry_session=self.session,
            backend=self.backend,
        )
        self.rows.append(row)
        return True
