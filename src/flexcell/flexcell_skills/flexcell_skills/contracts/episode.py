"""Per-episode record + policy-input replay (M2.2, issue #7 / §4.4).

One episode = one task run, recorded at the POLICY-INPUT level: for every
decide() call the executor persists the exact inputs the decision layer saw
(canonical WorldState bytes, goal, constraints, history) plus the decision it
produced and the executor/verifier result that followed.  Gazebo physics is
NOT assumed bit-replayable; instead any policy can be re-run OFFLINE on the
recorded input sequences and its decisions compared against the recorded ones
- that is how Jev/LLM will be evaluated without touching the robot.

Contract notes (ADR-002 / ratified ①):
- `world_canonical` is the EXACT canonical envelope bytes from
  canonical_state.serialize_envelope (versioned, fair bytes to every policy),
  or None before the first observe.  Replay deserializes through
  deserialize_envelope, which refuses unknown schema versions.
- History is the policy's own input format (HistoryRecord fields only) -
  B1: the policy sees nothing else.
- The record is versioned (EpisodeSchemaVersion) and serialized in the same
  deterministic style as canonical_state (sort_keys, compact, UTF-8).

This module is pure python: no rclpy, no ROS msgs - offline testable.
"""

import json
import math
import os
import time

from flexcell_skills.canonical_state import SCHEMA_VERSION, deserialize_envelope

EPISODE_SCHEMA_VERSION = 1
EPISODE_SCHEMA_VERSION_KEY = "EpisodeSchemaVersion"


def goal_to_dict(goal):
    """TaskGoal -> plain dict (assignments keep plan order)."""
    return {
        "goal_id": goal.goal_id,
        "scenario_id": goal.scenario_id,
        "assignments": [list(a) for a in goal.assignments],
    }


def constraints_to_record(c):
    """Constraints -> plain dict (the policy's input view, B2/B3)."""
    return {
        "allowed_actions": sorted(c.allowed_actions),
        "recovery_budget": int(c.recovery_budget),
        "verify_tolerance_m": float(c.verify_tolerance_m),
        "motion_profile_id": c.motion_profile_id,
        "max_world_age_s": float(c.max_world_age_s),
    }


def history_to_dicts(history):
    """Iterable of HistoryRecord -> plain dicts (exactly what the policy saw)."""
    return [
        {
            "action": h.action,
            "target": h.target,
            "outcome": int(h.outcome),
            "error_code": int(h.error_code),
            "attempt": int(h.attempt),
            "world_revision": int(h.world_revision),
            "evidence_id": h.evidence_id,
        }
        for h in history
    ]


def decision_to_dict(d):
    out = {
        "action": d.action,
        "target": d.target,
        "confidence": round(float(d.confidence), 9),
        "reason_code": d.reason_code,
        "explanation": d.explanation,
    }
    if d.policy_trace is not None:
        out['policy_trace'] = d.policy_trace
    return out


def env_snapshot():
    """Delivery-acceptance lesson: every episode carries an environment
    fingerprint (load/uptime) so benchmark episodes stay distinguishable.
    Returns {} off-Linux."""
    env = {}
    try:
        with open("/proc/loadavg") as fh:
            env["load_1m"] = float(fh.read().split()[0])
        with open("/proc/uptime") as fh:
            env["uptime_s"] = float(fh.read().split()[0])
    except (OSError, ValueError, IndexError):
        pass
    return env


def _sanitize(obj):
    """JSON-safe: NaN/Inf -> None (deterministic; no allow_nan output)."""
    if isinstance(obj, float):
        return round(obj, 9) if math.isfinite(obj) else None
    if isinstance(obj, dict):
        return {k: _sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_sanitize(v) for v in obj]
    return obj


class EpisodeRecorder:
    """Accumulates one episode; the executor feeds it at each decision point."""

    def __init__(self, scenario_id, run_id, policy_name, policy_version, seed=0):
        self._scenario_id = scenario_id
        self._run_id = run_id
        self._policy = {"name": policy_name, "version": policy_version}
        self._seed = seed
        self._steps = []
        self._pending = None
        self._t_start = time.time()
        self._frozen = None

    def begin_step(self, world_canonical, goal, constraints, history):
        """Capture the EXACT policy input before the decide() call.

        world_canonical: canonical envelope bytes (str) or None (pre-observe).
        """
        self._pending = {
            "seq": len(self._steps) + 1,
            "policy_input": {
                "world_state_schema_version": SCHEMA_VERSION,
                "world_state_canonical": world_canonical,
                "goal": goal_to_dict(goal),
                "constraints": constraints_to_record(constraints),
                "history": history_to_dicts(history),
            },
            "policy_output": None,
            "decide_latency_ms": None,
            "executor_result": None,
        }

    def record_decision(self, decision, decide_latency_ms, clock=None):
        if self._pending is None:
            raise RuntimeError("record_decision before begin_step")
        self._pending["policy_output"] = decision_to_dict(decision)
        latency = float(decide_latency_ms)
        if not math.isfinite(latency) or latency < 0:
            raise ValueError("decision latency must be finite and nonnegative")
        self._pending["decide_latency_ms"] = latency
        self._pending["decide_latency_clock"] = clock

    def record_executor_result(self, outcome=None, error_code=None, detail="",
                               evidence_id="", post_condition=None):
        """Executor/verifier result following the decision.  outcome/error_code
        None = no skill dispatch happened for this decision (WAIT/ABORT)."""
        if self._pending is None:
            raise RuntimeError("record_executor_result before begin_step")
        self._pending["executor_result"] = {
            "outcome": int(outcome) if outcome is not None else None,
            "error_code": int(error_code) if error_code is not None else None,
            "detail": str(detail)[:200],
            "evidence_id": evidence_id,
            "post_condition": post_condition,
        }
        self._steps.append(self._pending)
        self._pending = None

    def drop_pending(self):
        """A step that never produced a result (canceled mid-flight)."""
        self._pending = None

    def to_dict(self, final_state=None, injection_schedule=None, protocol=None):
        # idempotent: the episode is frozen on the first finalize so the
        # stored bytes (and the end timestamp) are stable
        if self._frozen is not None:
            return self._frozen
        self._frozen = _sanitize({
            EPISODE_SCHEMA_VERSION_KEY: EPISODE_SCHEMA_VERSION,
            "scenario_id": self._scenario_id,
            "seed": self._seed,
            "run_id": self._run_id,
            "policy": self._policy,
            "benchmark_protocol": protocol,
            "runtime_fingerprint": os.environ.get('FLEXCELL_RUNTIME_FINGERPRINT'),
            "injection_schedule": injection_schedule or [],
            "initial_world_state": (
                self._steps[0]["policy_input"]["world_state_canonical"]
                if self._steps else None),
            "steps": self._steps,
            "final_state": final_state or {},
            "env": env_snapshot(),
            "timestamps": {
                "start": self._t_start,
                "end": time.time(),
            },
        })
        return self._frozen


def serialize_episode(record):
    """Deterministic bytes for a record dict (same style as canonical_state)."""
    return json.dumps(record, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False)


class EpisodeStore:
    """One JSON file per episode under a configurable directory."""

    def __init__(self, log_dir, node_logger=None):
        self._dir = os.path.expanduser(log_dir)
        self._log = node_logger

    def write(self, record):
        try:
            os.makedirs(self._dir, exist_ok=True)
            path = os.path.join(
                self._dir, "%s_%s.json" % (record["scenario_id"], record["run_id"]))
            tmp = path + ".tmp"
            with open(tmp, "w") as fh:
                fh.write(serialize_episode(record))
            os.replace(tmp, path)
            return path
        except OSError as exc:
            if self._log is not None:
                self._log.error("episode write failed: %s" % exc)
            return None


# ---------------------------------------------------------------- replay
def _goal_from_dict(d):
    from flexcell_skills.decision_policy import TaskGoal
    return TaskGoal(d["goal_id"], d["scenario_id"],
                    tuple((a[0], a[1]) for a in d["assignments"]))


def _constraints_from_dict(d):
    from flexcell_skills.decision_policy import Constraints
    return Constraints(
        frozenset(d["allowed_actions"]), int(d["recovery_budget"]),
        float(d["verify_tolerance_m"]), d["motion_profile_id"],
        float(d["max_world_age_s"]))


def _history_from_dicts(rows):
    from flexcell_skills.decision_policy import HistoryRecord
    return tuple(
        HistoryRecord(r["action"], r["target"], int(r["outcome"]),
                      int(r["error_code"]), int(r["attempt"]),
                      int(r["world_revision"]), r["evidence_id"])
        for r in rows)


def replay_episode(record, policy):
    """Re-run `policy` on the recorded policy inputs; compare with the
    recorded outputs.  Returns a list of {seq, ok, detail} - empty when the
    record has no steps."""
    replayed = []
    for step in record.get("steps", []):
        pi = step["policy_input"]
        world_text = pi["world_state_canonical"]
        if world_text is not None:
            # version dispatch: refuses unknown WorldStateSchemaVersion
            deserialize_envelope(world_text)
            world = json.loads(world_text)
        else:
            world = None
        goal = _goal_from_dict(pi["goal"])
        constraints = _constraints_from_dict(pi["constraints"])
        history = _history_from_dicts(pi["history"])
        decision = policy.decide(world, goal, constraints, history)
        got = decision_to_dict(decision)
        want = step["policy_output"]
        detail = ""
        ok = want is not None and got == want
        if not ok:
            detail = "recorded=%s replayed=%s" % (want, got)
        replayed.append({"seq": step["seq"], "ok": bool(ok), "detail": detail})
    return replayed
