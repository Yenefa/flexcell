#!/usr/bin/env python3
"""Analyze one preregistered real-contact grasp probe run.

Run layout (as written by run_probe.py):

    <run-dir>/protocol.json        preregistered protocol and acceptance criteria
    <run-dir>/box_a-01/meta.json   trial identity, hashes and process exit
    <run-dir>/box_a-01/steps.jsonl one JSON object per physics step

protocol.json is authoritative for the trial list and for every pass criterion.
This analyzer never supplies a threshold of its own and never moves one: a
protocol whose declared reference window differs from the frozen 50 ms, or whose
acceptance block is missing, is rejected. Malformed, missing, non-finite,
duplicated, out-of-order or hash-tampered input stops the analysis with exit
code 2 instead of being silently dropped.

Exit codes: 0 = overall PASS, 1 = analysis complete but overall FAIL,
2 = invalid input / cannot produce a trustworthy analysis.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = 1
KIND = "GRASP_CONTACT_PROBE_ANALYSIS"
PHASES = ("settle", "close", "lift", "hold")
# Preregistered and frozen: the reference pose is the mean over the last 50 ms of
# the close phase.
REF_WINDOW_S = 0.05
QUAT_NORM_MIN, QUAT_NORM_MAX = 0.98, 1.02
LIKE_50_MS = re.compile(r"(\d+(?:\.\d+)?)\s*(ms|毫秒)")

# Heuristic classification only. These numbers are NOT pass criteria and are never
# used to turn a FAIL into a PASS; they only label why a trial failed.
NO_CONTACT_FRACTION = 0.05
PENETRATION_GROUND_FRACTION = 0.5
JITTER_OSCILLATION_RATIO = 0.7
JITTER_MIN_PATH_MM = 5.0
SOLVER_JUMP_MM = 50.0
SOLVER_REL_LIMIT_M = 5.0
SOLVER_QD_LIMIT = 50.0

LIMITATIONS = (
    "仅两种尺寸/质量组合（35 mm-50 g、50 mm-120 g）与单一摩擦系数，未扫描尺寸-质量-摩擦"
    "参数空间；对其它几何、质量或摩擦组合的抓取能力没有任何证据。",
    "无视觉、无位姿误差、无传感器噪声注入：物体与基座位姿是仿真真值，夹持位姿完全由预注册"
    "几何决定；不能证明存在感知误差、标定偏差或物体位姿不确定性时的可行性。",
    "单一物理引擎（DART）与单一 1 ms 步长：接触刚度、摩擦锥离散化和穿透恢复都与步长、"
    "求解器耦合，结论不能迁移到其它引擎、其它步长或实时控制频率，也不能外推到真实硬件。",
)

INTERPRETATION = (
    "本报告只在 protocol.json 的预注册判据内给出 PASS/FAIL。PASS 表示该固定场景、固定"
    "参数下全部 trial 的基座系相对漂移低于阈值且未判为掉落；它不表示抓取成功率、"
    "不表示可部署性、不表示真实接触优于磁吸替代，也不表示物体在更重、更滑或更小的"
    "夹持余量下仍能被持住。"
)


class AnalysisError(Exception):
    """Invalid or untrustworthy input; mapped to exit code 2, never to a verdict."""


def require(condition: Any, message: str) -> None:
    if not condition:
        raise AnalysisError(message)


# --------------------------------------------------------------------------- #
# Primitive validation: every number that reaches a metric has been checked.
# --------------------------------------------------------------------------- #
def as_number(value: Any, where: str) -> float:
    require(not isinstance(value, bool) and isinstance(value, (int, float)),
            where + ": expected a number")
    number = float(value)
    require(math.isfinite(number), where + ": non-finite number")
    return number


def as_int(value: Any, where: str) -> int:
    require(not isinstance(value, bool) and isinstance(value, int),
            where + ": expected an integer")
    return value


def as_vector(value: Any, length: int, where: str) -> list[float]:
    require(isinstance(value, list) and len(value) == length,
            where + ": expected %d numbers" % length)
    return [as_number(item, "%s[%d]" % (where, index)) for index, item in enumerate(value)]


def as_quaternion(value: Any, where: str) -> tuple[float, float, float, float]:
    quaternion = as_vector(value, 4, where)
    norm = math.sqrt(sum(component * component for component in quaternion))
    require(QUAT_NORM_MIN <= norm <= QUAT_NORM_MAX,
            "%s: quaternion norm %.6f outside [%.2f, %.2f]"
            % (where, norm, QUAT_NORM_MIN, QUAT_NORM_MAX))
    return tuple(quaternion)  # type: ignore[return-value]


def as_pose(value: Any, where: str):
    require(isinstance(value, dict), where + ": missing pose object")
    position = as_vector(value.get("p"), 3, where + ".p")
    quaternion = as_quaternion(value.get("q"), where + ".q")
    return tuple(position), quaternion  # type: ignore[return-value]


def optional_string(value: Any, where: str) -> str | None:
    if value is None:
        return None
    require(isinstance(value, str) and value, where + ": expected a non-empty string")
    return value


# --------------------------------------------------------------------------- #
# Quaternion helpers (no third-party dependency).
# --------------------------------------------------------------------------- #
def quat_conjugate(q: Iterable[float]) -> tuple[float, float, float, float]:
    x, y, z, w = q
    return (-x, -y, -z, w)


def quat_multiply(a: Iterable[float], b: Iterable[float]) -> tuple[float, float, float, float]:
    ax, ay, az, aw = a
    bx, by, bz, bw = b
    return (
        aw * bx + ax * bw + ay * bz - az * by,
        aw * by - ax * bz + ay * bw + az * bx,
        aw * bz + ax * by - ay * bx + az * bw,
        aw * bw - ax * bx - ay * by - az * bz,
    )


def quat_angle_deg(a: Iterable[float], b: Iterable[float]) -> float:
    delta = quat_multiply(quat_conjugate(a), b)
    vector = math.sqrt(delta[0] ** 2 + delta[1] ** 2 + delta[2] ** 2)
    return math.degrees(2.0 * math.atan2(vector, abs(delta[3])))


def quat_mean(quaternions: list[tuple[float, float, float, float]]):
    """Chordal mean after hemisphere alignment; rejects cancelling antipodes."""
    require(quaternions, "quat_mean: no samples")
    reference = quaternions[0]
    total = [0.0, 0.0, 0.0, 0.0]
    for quaternion in quaternions:
        sign = 1.0 if sum(x * y for x, y in zip(reference, quaternion)) >= 0.0 else -1.0
        for axis in range(4):
            total[axis] += sign * quaternion[axis]
    norm = math.sqrt(sum(component * component for component in total))
    require(norm > 1e-6, "quat_mean: samples cancel (antipodal quaternions)")
    return tuple(component / norm for component in total)


def rotate_vector(vector: Iterable[float], q: Iterable[float]):
    """Rotate a 3-vector by a (unit) quaternion."""
    x, y, z = vector
    qx, qy, qz, qw = q
    tx = 2.0 * (qy * z - qz * y)
    ty = 2.0 * (qz * x - qx * z)
    tz = 2.0 * (qx * y - qy * x)
    return (
        x + qw * tx + (qy * tz - qz * ty),
        y + qw * ty + (qz * tx - qx * tz),
        z + qw * tz + (qx * ty - qy * tx),
    )


def distance(a: Iterable[float], b: Iterable[float]) -> float:
    return math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)))


# --------------------------------------------------------------------------- #
# Input records.
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class Joint:
    q: float
    qd: float
    f: float


@dataclass(frozen=True)
class Sample:
    iter: int
    t: float
    phase: str
    obj_p: tuple[float, float, float]
    obj_q: tuple[float, float, float, float]
    base_p: tuple[float, float, float]
    base_q: tuple[float, float, float, float]
    rel_p: tuple[float, float, float]
    rel_q: tuple[float, float, float, float]
    joints: dict[str, Joint]
    contacts: dict[str, int]
    gap_target: float | None
    lift_target: float | None
    pad_force_n: tuple[float, float] | None


@dataclass(frozen=True)
class ObjectSpec:
    name: str
    size_m: float | None
    mass_kg: float | None
    mu: float | None
    trials: int | None


@dataclass(frozen=True)
class Protocol:
    protocol_id: str
    sha256: str
    stage: str | None
    drift_max_mm: float
    drift_rot_max_deg: float | None
    drop_z_mm: float
    drop_norm_mm: float
    required_trials: int
    objects: dict[str, ObjectSpec]
    expected_trials: dict[str, int | None]
    declared_trials: tuple[str, ...] | None
    max_initial_jitter_m: float | None
    lift_contact_min: float | None
    lift_ground_max: float | None
    step_s: float | None
    engine: str | None
    resolved_keys: dict[str, str]
    raw: dict[str, Any]


@dataclass
class Trial:
    name: str
    directory: Path
    meta: dict[str, Any]
    samples: list[Sample]
    steps_sha256: str
    meta_sha256: str


# --------------------------------------------------------------------------- #
# protocol.json (acceptance block first, then a criteria block, then top level).
# --------------------------------------------------------------------------- #
CRITERION_ALIASES = {
    "drift_translation_mm_max": ("drift_translation_mm_max", "drift_translation_max_mm",
                                 "max_drift_translation_mm"),
    "drift_rotation_deg_max": ("drift_rotation_deg_max", "drift_rotation_max_deg"),
    "drop_relative_z_mm": ("drop_relative_z_mm", "drop_base_z_mm", "drop_z_mm"),
    "drop_abs_drift_mm": ("drop_abs_drift_mm", "drop_rel_norm_mm", "drop_rel_norm_threshold_mm"),
    "required_trials": ("trials_required_pass", "required_trials", "total_trials"),
    "max_initial_jitter_m": ("max_initial_jitter_m",),
    # Optional, and only enforced when declared: a drift-only PASS would accept an
    # object that was welded to the gripper and never touched a pad.
    "min_pad_contact_fraction_lift": ("min_pad_contact_fraction_lift",
                                      "min_both_pad_contact_fraction_lift"),
    "max_obj_ground_fraction_lift": ("max_obj_ground_fraction_lift",
                                     "max_ground_fraction_lift"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _blocks(raw: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    acceptance = raw.get("acceptance") if isinstance(raw.get("acceptance"), dict) else {}
    criteria = raw.get("criteria") if isinstance(raw.get("criteria"), dict) else {}
    return acceptance, criteria


def _resolve(raw: dict[str, Any], acceptance: dict[str, Any], criteria: dict[str, Any],
             label: str):
    for block_label, block in (("acceptance", acceptance), ("criteria", criteria), ("protocol", raw)):
        for alias in CRITERION_ALIASES[label]:
            if alias in block:
                return block[alias], "%s.%s" % (block_label, alias)
    return None, None


def _spec(name: str, props: dict[str, Any], where: str) -> ObjectSpec:
    require(isinstance(name, str) and name, where + ": object name must be a non-empty string")

    def optional_number(key: str) -> float | None:
        value = props.get(key)
        if value is None:
            return None
        number = as_number(value, "%s.%s" % (where, key))
        require(number > 0.0, "%s.%s: must be positive" % (where, key))
        return number

    trials = props.get("trials")
    if trials is not None:
        trials = as_int(trials, where + ".trials")
        require(trials >= 1, where + ".trials: must be positive")
    return ObjectSpec(name, optional_number("size_m"), optional_number("mass_kg"),
                      optional_number("mu"), trials)


def load_protocol(run_dir: Path) -> Protocol:
    path = run_dir / "protocol.json"
    require(path.is_file(), "%s: missing protocol.json (criteria must be preregistered)" % path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AnalysisError("%s: unreadable JSON: %s" % (path, error)) from error
    require(isinstance(raw, dict), "%s: expected a JSON object" % path)

    acceptance, criteria = _blocks(raw)
    resolved: dict[str, str] = {}

    def take(label: str) -> Any:
        value, source = _resolve(raw, acceptance, criteria, label)
        if source is not None:
            resolved[label] = source
        return value

    drift_max = take("drift_translation_mm_max")
    require(drift_max is not None,
            "protocol: drift_translation_mm_max is required in acceptance or criteria; "
            "analyze.py does not supply its own thresholds")
    drift_max = as_number(drift_max, "protocol.drift_translation_mm_max")
    require(drift_max > 0.0, "protocol: drift_translation_mm_max must be positive")

    rotation = take("drift_rotation_deg_max")
    if rotation is not None:
        rotation = as_number(rotation, "protocol.drift_rotation_deg_max")
        require(rotation > 0.0, "protocol: drift_rotation_deg_max must be positive")

    drop_z = take("drop_relative_z_mm")
    drop_norm = take("drop_abs_drift_mm")
    require(drop_z is not None, "protocol: drop_relative_z_mm is required")
    require(drop_norm is not None, "protocol: drop_abs_drift_mm is required")
    drop_z = abs(as_number(drop_z, "protocol.drop_relative_z_mm"))
    drop_norm = as_number(drop_norm, "protocol.drop_abs_drift_mm")
    require(drop_z > 0.0 and drop_norm > 0.0, "protocol: drop thresholds must be non-zero")

    jitter_limit = take("max_initial_jitter_m")
    if jitter_limit is not None:
        jitter_limit = as_number(jitter_limit, "protocol.max_initial_jitter_m")
        require(jitter_limit > 0.0, "protocol: max_initial_jitter_m must be positive")

    lift_contact = take("min_pad_contact_fraction_lift")
    if lift_contact is not None:
        lift_contact = as_number(lift_contact, "protocol.min_pad_contact_fraction_lift")
        require(0.0 <= lift_contact <= 1.0,
                "protocol: min_pad_contact_fraction_lift must be inside [0, 1]")
    lift_ground = take("max_obj_ground_fraction_lift")
    if lift_ground is not None:
        lift_ground = as_number(lift_ground, "protocol.max_obj_ground_fraction_lift")
        require(0.0 <= lift_ground <= 1.0,
                "protocol: max_obj_ground_fraction_lift must be inside [0, 1]")

    stage = raw.get("stage")
    if stage is not None:
        require(isinstance(stage, str), "protocol.stage: expected a string")
        require(stage == "acceptance",
                "protocol stage %r is exploratory; only the acceptance stage has "
                "preregistered pass criteria, so no verdict can be issued" % stage)

    physics = raw.get("physics") if isinstance(raw.get("physics"), dict) else {}
    step_s = physics.get("step_s", raw.get("step_s"))
    if step_s is not None:
        resolved["step_s"] = "physics.step_s" if "step_s" in physics else "protocol.step_s"
        step_s = as_number(step_s, "protocol.physics.step_s")
        require(step_s > 0.0, "protocol: step_s must be positive")
    engine = physics.get("engine")
    if engine is not None:
        require(isinstance(engine, str) and engine, "protocol.physics.engine: expected a string")

    if "ref_window_s" in raw:
        window = as_number(raw["ref_window_s"], "protocol.ref_window_s")
        require(abs(window - REF_WINDOW_S) < 1e-12,
                "protocol.ref_window_s %.6f differs from the preregistered %.3f s window"
                % (window, REF_WINDOW_S))
        resolved["ref_window_s"] = "protocol.ref_window_s"
    reference_text = acceptance.get("reference", raw.get("reference"))
    if isinstance(reference_text, str):
        match = LIKE_50_MS.search(reference_text)
        require(match is None or abs(float(match.group(1)) - REF_WINDOW_S * 1000.0) < 1e-9,
                "protocol acceptance.reference declares %s %s, which differs from the "
                "preregistered %.0f ms reference window"
                % (match.group(1), match.group(2), REF_WINDOW_S * 1000.0))
        resolved["reference"] = "acceptance.reference"

    # Objects: an explicit object_specs map wins over a bare name list.
    ordered: list[str] = []
    fields: dict[str, dict[str, Any]] = {}

    def add_entry(entry: Any, where: str) -> None:
        if isinstance(entry, str):
            props: dict[str, Any] = {"name": entry}
        elif isinstance(entry, dict):
            props = entry
        else:
            raise AnalysisError(where + ": expected an object name or object map")
        name = props.get("name")
        require(isinstance(name, str) and name, where + ".name: expected a non-empty string")
        if name not in fields:
            ordered.append(name)
            fields[name] = {}
        fields[name].update({key: value for key, value in props.items() if key != "name"})

    source = raw.get("objects", acceptance.get("objects", criteria.get("objects")))
    require(source is not None, "protocol: no object declaration (objects or acceptance.objects)")
    if isinstance(source, dict):
        for name, props in source.items():
            merged = dict(props) if isinstance(props, dict) else {}
            merged["name"] = name
            add_entry(merged, "protocol.objects." + str(name))
    elif isinstance(source, list):
        for index, entry in enumerate(source):
            add_entry(entry, "protocol.objects[%d]" % index)
    else:
        raise AnalysisError("protocol: object declaration must be a list or a map")

    extra_specs = raw.get("object_specs", acceptance.get("object_specs"))
    if extra_specs is not None:
        require(isinstance(extra_specs, dict), "protocol.object_specs: expected a map")
        for name, props in extra_specs.items():
            require(isinstance(props, dict), "protocol.object_specs.%s: expected a map" % name)
            if name not in fields:
                ordered.append(name)
                fields[name] = {}
            fields[name].update(props)
        resolved["object_specs"] = "protocol.object_specs"

    objects: dict[str, ObjectSpec] = {}
    for name in ordered:
        where = "protocol.objects." + name
        spec = _spec(name, fields[name], where)
        require(name not in objects, where + ": duplicate object name")
        objects[name] = spec

    trials_per_object = raw.get("trials_per_object", acceptance.get("trials_per_object"))
    if trials_per_object is not None:
        trials_per_object = as_int(trials_per_object, "protocol.trials_per_object")
        require(trials_per_object >= 1, "protocol.trials_per_object: must be positive")

    declared: tuple[str, ...] | None = None
    if raw.get("trials") is not None:
        declared_list = raw["trials"]
        require(isinstance(declared_list, list) and declared_list, "protocol.trials: expected a non-empty list")
        names = []
        for index, entry in enumerate(declared_list):
            name = optional_string(entry, "protocol.trials[%d]" % index)
            require(name is not None, "protocol.trials[%d]: empty name" % index)
            require(name not in names, "protocol.trials: duplicate trial name " + name)
            names.append(name)
        declared = tuple(names)
        resolved["trials"] = "protocol.trials"

    expected_trials: dict[str, int | None] = {}
    for name, spec in objects.items():
        if spec.trials is not None:
            expected_trials[name] = spec.trials
        elif trials_per_object is not None:
            expected_trials[name] = trials_per_object
        elif declared is not None:
            expected_trials[name] = sum(1 for trial in declared if trial.startswith(name + "-"))
        else:
            expected_trials[name] = None

    required = take("required_trials")
    if required is None:
        if declared is not None:
            required = len(declared)
        elif all(value is not None for value in expected_trials.values()):
            required = sum(value for value in expected_trials.values() if value is not None)
        require(required is not None, "protocol: missing trials_required_pass")
    required = as_int(required, "protocol.trials_required_pass")
    require(required >= 1, "protocol: trials_required_pass must be positive")
    if declared is not None:
        require(required == len(declared),
                "protocol: trials_required_pass %d differs from %d declared trials"
                % (required, len(declared)))
    if all(value is not None for value in expected_trials.values()):
        require(required == sum(value for value in expected_trials.values() if value is not None),
                "protocol: trials_required_pass %d differs from the per-object sum %d"
                % (required, sum(value for value in expected_trials.values() if value is not None)))

    protocol_id = raw.get("protocol_id") or raw.get("run_id") or raw.get("kind")
    require(isinstance(protocol_id, str) and protocol_id, "protocol: missing protocol_id/run_id")

    return Protocol(
        protocol_id=protocol_id,
        sha256=sha256(path),
        stage=stage,
        drift_max_mm=drift_max,
        drift_rot_max_deg=rotation,
        drop_z_mm=drop_z,
        drop_norm_mm=drop_norm,
        required_trials=required,
        objects=objects,
        expected_trials=expected_trials,
        declared_trials=declared,
        max_initial_jitter_m=jitter_limit,
        lift_contact_min=lift_contact,
        lift_ground_max=lift_ground,
        step_s=step_s,
        engine=engine,
        resolved_keys=resolved,
        raw=raw,
    )


# --------------------------------------------------------------------------- #
# steps.jsonl / meta.json
# --------------------------------------------------------------------------- #
def parse_sample(raw: Any, where: str) -> Sample:
    require(isinstance(raw, dict), where + ": expected a JSON object")
    iteration = as_int(raw.get("iter"), where + ".iter")
    require(iteration >= 0, where + ".iter: negative")
    t = as_number(raw.get("t"), where + ".t")
    require(t >= 0.0, where + ".t: negative simulation time")
    phase = raw.get("phase")
    require(phase in PHASES, where + ".phase: %r is not one of %r" % (phase, PHASES))

    obj_p, obj_q = as_pose(raw.get("obj"), where + ".obj")
    base_p, base_q = as_pose(raw.get("base"), where + ".base")
    rel_p, rel_q = as_pose(raw.get("rel"), where + ".rel")

    joints_raw = raw.get("joints")
    require(isinstance(joints_raw, dict), where + ".joints: missing")
    joints: dict[str, Joint] = {}
    for name in ("left", "right", "lift"):
        entry = joints_raw.get(name)
        require(isinstance(entry, dict), "%s.joints.%s: missing" % (where, name))
        joints[name] = Joint(
            q=as_number(entry.get("q"), "%s.joints.%s.q" % (where, name)),
            qd=as_number(entry.get("qd"), "%s.joints.%s.qd" % (where, name)),
            f=as_number(entry.get("f"), "%s.joints.%s.f" % (where, name)),
        )

    contacts_raw = raw.get("contacts")
    require(isinstance(contacts_raw, dict), where + ".contacts: missing")
    contacts: dict[str, int] = {}
    for name in ("left_pad", "right_pad", "obj_ground"):
        value = as_int(contacts_raw.get(name), "%s.contacts.%s" % (where, name))
        # -1 is the plugin's "collision or contact sensor missing" sentinel. It is
        # not "no contact": inferring zero would fabricate evidence.
        require(value >= 0,
                "%s.contacts.%s: %d means contact availability is unknown "
                "(missing collision or sensor); refusing to infer zero" % (where, name, value))
        contacts[name] = value

    pad_force = None
    if "left_pad_force" in contacts_raw or "right_pad_force" in contacts_raw:
        pad_force = (
            as_number(contacts_raw.get("left_pad_force"), where + ".contacts.left_pad_force"),
            as_number(contacts_raw.get("right_pad_force"), where + ".contacts.right_pad_force"),
        )
        require(pad_force[0] >= 0.0 and pad_force[1] >= 0.0,
                where + ".contacts.*_pad_force: negative magnitude")

    gap_target = raw.get("gap_target")
    lift_target = raw.get("lift_target")
    return Sample(
        iter=iteration,
        t=t,
        phase=phase,  # type: ignore[arg-type]
        obj_p=obj_p,
        obj_q=obj_q,
        base_p=base_p,
        base_q=base_q,
        rel_p=rel_p,
        rel_q=rel_q,
        joints=joints,
        contacts=contacts,
        gap_target=None if gap_target is None else as_number(gap_target, where + ".gap_target"),
        lift_target=None if lift_target is None else as_number(lift_target, where + ".lift_target"),
        pad_force_n=pad_force,
    )


def check_rel_frame(sample: Sample, where: str) -> None:
    """rel must be the object pose expressed in the base frame, not world frame.

    A world-frame or swapped rel would make every drift metric meaningless while
    still looking like a number, so the identity is verified from obj and base.
    """
    offset = distance(
        rotate_vector(tuple(o - b for o, b in zip(sample.obj_p, sample.base_p)),
                      quat_conjugate(sample.base_q)),
        sample.rel_p,
    )
    require(offset <= 5e-4,
            "%s: rel.p is not obj expressed in the base frame (offset %.3f mm)"
            % (where, offset * 1000.0))
    angle = quat_angle_deg(sample.rel_q, quat_multiply(quat_conjugate(sample.base_q), sample.obj_q))
    require(angle <= 0.05,
            "%s: rel.q is not obj expressed in the base frame (%.4f deg off)" % (where, angle))


def load_trial(directory: Path) -> Trial:
    meta_path = directory / "meta.json"
    steps_path = directory / "steps.jsonl"
    require(meta_path.is_file(), "%s: missing meta.json" % directory)
    require(steps_path.is_file(), "%s: missing steps.jsonl" % directory)
    try:
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise AnalysisError("%s: unreadable JSON: %s" % (meta_path, error)) from error
    require(isinstance(meta, dict), "%s: expected a JSON object" % meta_path)

    raw_lines = steps_path.read_text(encoding="utf-8").splitlines()
    require(raw_lines, "%s: empty step log" % steps_path)
    samples: list[Sample] = []
    previous_iter = -1
    previous_t = -1.0
    for number, line in enumerate(raw_lines, start=1):
        if not line.strip():
            raise AnalysisError("%s:%d: blank line in step log" % (steps_path, number))
        try:
            raw = json.loads(line)
        except ValueError as error:
            raise AnalysisError("%s:%d: unreadable JSON: %s" % (steps_path, number, error)) from error
        where = "%s:%d" % (steps_path.name, number)
        sample = parse_sample(raw, where)
        check_rel_frame(sample, where)
        require(sample.iter > previous_iter,
                "%s: iter %d does not increase (previous %d)"
                % (where, sample.iter, previous_iter))
        require(sample.t > previous_t,
                "%s: t %.9f is not strictly increasing (previous %.9f)"
                % (where, sample.t, previous_t))
        samples.append(sample)
        previous_iter = sample.iter
        previous_t = sample.t

    require(len(samples) >= 10,
            "%s: only %d samples; a phase-level metric cannot be computed" % (steps_path, len(samples)))
    check_phases(samples, steps_path.name)
    return Trial(directory.name, directory, meta, samples, sha256(steps_path), sha256(meta_path))


def check_phases(samples: list[Sample], where: str) -> None:
    rank = {phase: index for index, phase in enumerate(PHASES)}
    previous = -1
    seen: set[str] = set()
    for sample in samples:
        current = rank[sample.phase]
        require(current >= previous,
                "%s: phase regressed to %r at t=%.3f" % (where, sample.phase, sample.t))
        previous = current
        seen.add(sample.phase)
    require(samples[0].phase == "settle",
            "%s: first sample is %r, not 'settle'" % (where, samples[0].phase))
    missing = [phase for phase in PHASES if phase not in seen]
    require(not missing, "%s: missing phase(s) %s" % (where, ", ".join(missing)))


# --------------------------------------------------------------------------- #
# Metrics.
# --------------------------------------------------------------------------- #
def _phase(samples: list[Sample], phase: str) -> list[Sample]:
    return [sample for sample in samples if sample.phase == phase]


def _fraction(samples: list[Sample], predicate) -> float:
    if not samples:
        return 0.0
    return sum(1 for sample in samples if predicate(sample)) / len(samples)


def _max_with_time(pairs: Iterable[tuple[float, float]]) -> tuple[float, float | None]:
    best_value = -1.0
    best_time = None
    for value, time in pairs:
        if value > best_value:
            best_value, best_time = value, time
    return best_value, best_time


def _force_stats(samples: list[Sample], names: tuple[str, ...]) -> dict[str, float]:
    values = [abs(sample.joints[name].f) for sample in samples for name in names]
    if not values:
        return {"max_abs_n": 0.0, "mean_abs_n": 0.0, "samples": 0}
    return {"max_abs_n": max(values), "mean_abs_n": math.fsum(values) / len(values),
            "samples": len(values)}


def parse_jitter(value: Any, where: str) -> tuple[float | None, float | None]:
    """Initial pose jitter as a scalar distance in metres, or as {x,y,yaw_deg}."""
    if value is None:
        return None, None
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        jitter = as_number(value, where)
        require(jitter >= 0.0, where + ": negative")
        return jitter, None
    if isinstance(value, dict):
        x = value.get("x", value.get("x_m", 0.0))
        y = value.get("y", value.get("y_m", 0.0))
        x = as_number(x, where + ".x")
        y = as_number(y, where + ".y")
        yaw = value.get("yaw_deg")
        if yaw is not None:
            yaw = as_number(yaw, where + ".yaw_deg")
        return math.hypot(x, y), yaw
    raise AnalysisError(where + ": expected a number or a map with x/y/yaw_deg")


def analyze_trial(trial: Trial, protocol: Protocol) -> dict[str, Any]:
    meta = trial.meta
    where = trial.name + "/meta.json"
    object_name = meta.get("object_name")
    require(isinstance(object_name, str) and object_name,
            where + ": object_name must be a non-empty string")
    spec = protocol.objects.get(object_name)
    require(spec is not None,
            "%s: object_name %r is not declared in the protocol" % (where, object_name))
    size = as_number(meta.get("size_m"), where + ".size_m")
    mass = as_number(meta.get("mass_kg"), where + ".mass_kg")
    mu = as_number(meta.get("mu"), where + ".mu")
    require(size > 0.0 and mass > 0.0 and mu > 0.0,
            where + ": size_m, mass_kg and mu must be positive")

    identity_checked = all(value is not None for value in (spec.size_m, spec.mass_kg, spec.mu))
    if identity_checked:
        for label, actual, declared in (("size_m", size, spec.size_m),
                                        ("mass_kg", mass, spec.mass_kg),
                                        ("mu", mu, spec.mu)):
            require(math.isclose(actual, declared, rel_tol=1e-6, abs_tol=1e-12),
                    "%s: %s=%r differs from the preregistered %r; this trial is not the "
                    "declared experiment" % (where, label, actual, declared))

    exit_code = meta.get("exit_code")
    if exit_code is not None:
        require(exit_code == 0,
                "%s: the trial process exited with %r; a broken trial cannot yield a verdict"
                % (where, exit_code))
    declared_steps_hash = meta.get("steps_sha256")
    if declared_steps_hash is not None:
        require(isinstance(declared_steps_hash, str) and declared_steps_hash,
                where + ".steps_sha256: expected a string")
        require(declared_steps_hash == trial.steps_sha256,
                "%s: steps.jsonl sha256 %s does not match the trial receipt %s"
                % (where, trial.steps_sha256, declared_steps_hash))
    declared_world_hash = meta.get("world_sha256")
    if declared_world_hash is not None:
        world_path = trial.directory / "world.sdf"
        require(world_path.is_file(),
                "%s: declares world_sha256 but %s is missing" % (where, world_path))
        require(sha256(world_path) == declared_world_hash,
                "%s: world.sdf sha256 differs from the trial receipt" % where)

    jitter_m, jitter_yaw_deg = parse_jitter(meta.get("jitter"), where + ".jitter")
    if jitter_m is not None and protocol.max_initial_jitter_m is not None:
        require(jitter_m <= protocol.max_initial_jitter_m,
                "%s: initial jitter %.6f m exceeds the preregistered %.6f m"
                % (where, jitter_m, protocol.max_initial_jitter_m))

    samples = trial.samples
    close = _phase(samples, "close")
    lift = _phase(samples, "lift")
    hold = _phase(samples, "hold")

    # ref: mean over the last 50 ms of close (preregistered, frozen).
    close_end = close[-1].t
    reference_samples = [sample for sample in close if sample.t >= close_end - REF_WINDOW_S - 1e-12]
    require(len(reference_samples) >= 5,
            "%s: only %d close samples inside the last %.0f ms; ref unwindowable"
            % (where, len(reference_samples), REF_WINDOW_S * 1000))
    ref_p = tuple(
        math.fsum(sample.rel_p[axis] for sample in reference_samples) / len(reference_samples)
        for axis in range(3)
    )
    ref_q = quat_mean([sample.rel_q for sample in reference_samples])
    ref_translation_spread_mm = max(distance(sample.rel_p, ref_p) for sample in reference_samples) * 1000.0
    ref_rotation_spread_deg = max(quat_angle_deg(sample.rel_q, ref_q) for sample in reference_samples)

    after_close = [sample for sample in samples if sample.t > close_end + 1e-12]
    require(after_close, "%s: no samples after the close phase" % where)

    drift_translation_mm, drift_translation_at = _max_with_time(
        (distance(sample.rel_p, ref_p) * 1000.0, sample.t) for sample in after_close)
    drift_rotation_deg, drift_rotation_at = _max_with_time(
        (quat_angle_deg(sample.rel_q, ref_q), sample.t) for sample in after_close)

    # drop: object descends more than the declared z limit relative to the base,
    # or moves more than the declared norm limit away from the reference pose.
    decline_mm, decline_at = _max_with_time(
        ((ref_p[2] - sample.rel_p[2]) * 1000.0, sample.t) for sample in after_close)
    z_triggered = decline_mm > protocol.drop_z_mm
    z_trigger_at = None
    if z_triggered:
        z_trigger_at = next(sample.t for sample in after_close
                            if (ref_p[2] - sample.rel_p[2]) * 1000.0 > protocol.drop_z_mm)
    norm_triggered = drift_translation_mm > protocol.drop_norm_mm
    norm_trigger_at = None
    if norm_triggered:
        norm_trigger_at = next(sample.t for sample in after_close
                               if distance(sample.rel_p, ref_p) * 1000.0 > protocol.drop_norm_mm)
    drop = z_triggered or norm_triggered

    left = lambda sample: sample.contacts["left_pad"] > 0
    right = lambda sample: sample.contacts["right_pad"] > 0
    both = lambda sample: sample.contacts["left_pad"] > 0 and sample.contacts["right_pad"] > 0
    ground = lambda sample: sample.contacts["obj_ground"] > 0
    pad_fraction = {
        phase_name: {
            "left": _fraction(_phase(samples, phase_name), left),
            "right": _fraction(_phase(samples, phase_name), right),
            "both": _fraction(_phase(samples, phase_name), both),
        }
        for phase_name in ("close", "lift", "hold")
    }
    ground_fraction = {phase_name: _fraction(_phase(samples, phase_name), ground)
                       for phase_name in PHASES}
    touching = [sample for sample in samples if ground(sample)]
    ground_last_t = touching[-1].t if touching else None
    ground_lost_t = None
    ground_still_touching_at_end = False
    if touching:
        after = [sample.t for sample in samples if sample.t > ground_last_t]
        if after:
            ground_lost_t = after[0]
        else:
            ground_still_touching_at_end = True

    forces = {
        "close": _force_stats(close, ("left", "right")),
        "lift": _force_stats(lift, ("left", "right")),
        "lift_joint_lift": _force_stats(lift, ("lift",)),
    }
    max_abs_qd = max(abs(sample.joints[name].qd) for sample in samples for name in ("left", "right", "lift"))
    max_abs_joint_force = max(abs(sample.joints[name].f) for sample in samples for name in ("left", "right"))

    measured_pad_force = None
    pad_forces = [magnitude for sample in close + lift if sample.pad_force_n
                  for magnitude in sample.pad_force_n]
    if pad_forces:
        measured_pad_force = {
            "max_abs_n": max(pad_forces),
            "mean_abs_n": math.fsum(pad_forces) / len(pad_forces),
            "samples": len(pad_forces),
            "weight_ratio_max": max(pad_forces) / (mass * 9.8),
            "note": "extra signal logged by the plugin; not part of the preregistered metric set",
        }

    deltas_mm = [distance(current.rel_p, previous.rel_p) * 1000.0
                 for previous, current in zip(after_close, after_close[1:])]
    path_mm = math.fsum(deltas_mm)
    net_mm = distance(after_close[-1].rel_p, after_close[0].rel_p) * 1000.0
    oscillation_ratio = 0.0 if path_mm <= 1e-9 else max(0.0, 1.0 - net_mm / path_mm)
    max_frame_jump_mm = max(deltas_mm) if deltas_mm else 0.0
    max_rel_norm_m = max(math.sqrt(sum(component * component for component in sample.rel_p))
                         for sample in samples)
    solver_divergence = (max_frame_jump_mm > SOLVER_JUMP_MM
                         or max_rel_norm_m > SOLVER_REL_LIMIT_M
                         or max_abs_qd > SOLVER_QD_LIMIT)

    steps = [current.t - previous.t for previous, current in zip(samples, samples[1:])]
    dt = {"min_s": min(steps), "median_s": sorted(steps)[len(steps) // 2],
          "max_s": max(steps), "frames": len(samples)}
    if protocol.step_s is not None:
        require(dt["max_s"] <= protocol.step_s * 1.5,
                "%s: maximum step %.6f s exceeds 1.5 x declared %.6f s (missing physics frame)"
                % (where, dt["max_s"], protocol.step_s))

    pass_translation = drift_translation_mm < protocol.drift_max_mm
    pass_rotation = (True if protocol.drift_rot_max_deg is None
                     else drift_rotation_deg < protocol.drift_rot_max_deg)
    pass_contact = True
    if protocol.lift_contact_min is not None:
        pass_contact = pass_contact and pad_fraction["lift"]["both"] >= protocol.lift_contact_min
    if protocol.lift_ground_max is not None:
        pass_contact = pass_contact and ground_fraction["lift"] <= protocol.lift_ground_max
    passed = bool(pass_translation and pass_rotation and pass_contact and not drop)

    rel_frame_offset_mm = max(
        distance(
            rotate_vector(tuple(o - b for o, b in zip(sample.obj_p, sample.base_p)),
                          quat_conjugate(sample.base_q)),
            sample.rel_p,
        ) for sample in samples) * 1000.0

    return {
        "trial": trial.name,
        "object": object_name,
        "meta": {
            "size_m": size, "mass_kg": mass, "mu": mu,
            "jitter_m": jitter_m, "jitter_yaw_deg": jitter_yaw_deg,
            "identity_checked": identity_checked,
            "identity_source": "protocol_and_meta" if identity_checked else "meta_only",
            "raw": meta,
        },
        "samples": len(samples),
        "sim_duration_s": samples[-1].t - samples[0].t,
        "first_t": samples[0].t,
        "last_t": samples[-1].t,
        "phase_counts": {phase: len(_phase(samples, phase)) for phase in PHASES},
        "dt": dt,
        "integrity": {"rel_frame_offset_mm": rel_frame_offset_mm},
        "files": {"steps_sha256": trial.steps_sha256, "meta_sha256": trial.meta_sha256},
        "ref": {
            "window_s": REF_WINDOW_S,
            "t_start": reference_samples[0].t,
            "t_end": reference_samples[-1].t,
            "samples": len(reference_samples),
            "position_m": list(ref_p),
            "quaternion": list(ref_q),
            "translation_spread_mm": ref_translation_spread_mm,
            "rotation_spread_deg": ref_rotation_spread_deg,
        },
        "drift": {
            "translation_mm": drift_translation_mm,
            "translation_at_s": drift_translation_at,
            "rotation_deg": drift_rotation_deg,
            "rotation_at_s": drift_rotation_at,
            "window_start_s": close_end,
            "translation_limit_mm": protocol.drift_max_mm,
            "rotation_limit_deg": protocol.drift_rot_max_deg,
            "translation_within_limit": pass_translation,
            "rotation_within_limit": pass_rotation,
        },
        "contact_evidence": {
            "requires_pad_contact_in_lift": protocol.lift_contact_min,
            "lift_both_pad_fraction": pad_fraction["lift"]["both"],
            "max_obj_ground_fraction_lift": protocol.lift_ground_max,
            "lift_obj_ground_fraction": ground_fraction["lift"],
            "within_limit": pass_contact,
        },
        "drop": {
            "base_z_decline_mm": decline_mm,
            "base_z_limit_mm": protocol.drop_z_mm,
            "base_z_triggered": z_triggered,
            "base_z_trigger_t": z_trigger_at,
            "rel_norm_deviation_mm": drift_translation_mm,
            "rel_norm_limit_mm": protocol.drop_norm_mm,
            "rel_norm_triggered": norm_triggered,
            "rel_norm_trigger_t": norm_trigger_at,
            "drop": drop,
        },
        "contacts": {
            "pad_fraction": pad_fraction,
            "obj_ground_fraction": ground_fraction,
            "obj_ground_last_t": ground_last_t,
            "obj_ground_lost_t": ground_lost_t,
            "obj_ground_still_touching_at_end": ground_still_touching_at_end,
        },
        "forces": forces,
        "max_abs_qd_rad_s": max_abs_qd,
        "max_abs_finger_command_n": max_abs_joint_force,
        "measured_pad_force": measured_pad_force,
        "heuristics": {
            "oscillation_ratio": oscillation_ratio,
            "max_frame_rel_jump_mm": max_frame_jump_mm,
            "max_rel_norm_m": max_rel_norm_m,
            "solver_divergence": solver_divergence,
        },
        "pass": passed,
        "failure_modes": [] if passed else classify_failure(
            drop=drop,
            pad_fraction=pad_fraction,
            ground_fraction=ground_fraction,
            lift_target=next((sample.lift_target for sample in reversed(samples)
                              if sample.lift_target is not None), None),
            oscillation_ratio=oscillation_ratio,
            path_mm=path_mm,
            solver_divergence=solver_divergence,
        ),
    }


def classify_failure(*, drop: bool, pad_fraction: dict[str, dict[str, float]],
                     ground_fraction: dict[str, float], lift_target: float | None,
                     oscillation_ratio: float, path_mm: float,
                     solver_divergence: bool) -> list[str]:
    """Label why a trial failed. Heuristics; never influences PASS/FAIL."""
    modes: list[str] = []
    if solver_divergence:
        modes.append("solver-divergence")
    lift = pad_fraction["lift"]
    if max(lift["left"], lift["right"]) < NO_CONTACT_FRACTION:
        modes.append("no-contact")
    if drop:
        modes.append("drop")
    if (ground_fraction["hold"] > PENETRATION_GROUND_FRACTION
            and lift_target is not None and lift_target > 0.05
            and lift["both"] > 0.5):
        modes.append("penetration")
    if oscillation_ratio > JITTER_OSCILLATION_RATIO and path_mm > JITTER_MIN_PATH_MM:
        modes.append("jitter")
    if not modes:
        modes.append("slip")
    return modes


# --------------------------------------------------------------------------- #
# Run-level analysis.
# --------------------------------------------------------------------------- #
TRIAL_PATTERN = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)-(\d+)$")


def discover_trials(run_dir: Path, protocol: Protocol) -> list[Path]:
    require(run_dir.is_dir(), "%s: run directory does not exist" % run_dir)
    candidates: list[tuple[str, int, Path]] = []
    for entry in sorted(run_dir.iterdir()):
        match = TRIAL_PATTERN.match(entry.name)
        if match and entry.is_dir():
            candidates.append((match.group(1), int(match.group(2)), entry))
    if protocol.declared_trials is not None:
        missing = [name for name in protocol.declared_trials if not (run_dir / name).is_dir()]
        require(not missing,
                "%s: declared trial director%s missing: %s"
                % (run_dir, "y is" if len(missing) == 1 else "ies are", ", ".join(missing)))
        extra = sorted({entry.name for _, _, entry in candidates} - set(protocol.declared_trials))
        require(not extra,
                "%s: trial directories not in the preregistered trial list: %s"
                % (run_dir, ", ".join(extra)))
        return [run_dir / name for name in protocol.declared_trials]
    require(candidates, "%s: no trial-* directories found" % run_dir)
    prefixes: dict[str, list[int]] = {}
    for prefix, number, _ in candidates:
        prefixes.setdefault(prefix, []).append(number)
    for prefix, numbers in prefixes.items():
        numbers = sorted(numbers)
        require(numbers == list(range(1, len(numbers) + 1)),
                "%s: trial numbering for %r has gaps: found %s"
                % (run_dir, prefix, numbers))
    ordered = sorted((prefix, number, entry) for prefix, number, entry in candidates)
    return [entry for _, _, entry in ordered]


def analyze_run(run_dir: Path) -> dict[str, Any]:
    protocol = load_protocol(run_dir)
    trial_dirs = discover_trials(run_dir, protocol)
    trials = [analyze_trial(load_trial(path), protocol) for path in trial_dirs]

    by_object: dict[str, list[dict[str, Any]]] = {name: [] for name in protocol.objects}
    for trial in trials:
        by_object[trial["object"]].append(trial)
    for name, spec in protocol.objects.items():
        expected = protocol.expected_trials.get(name)
        found = len(by_object[name])
        if expected is not None:
            require(found == expected,
                    "run: object %s has %d trials, protocol declares %d "
                    "(missing trial directory)" % (name, found, expected))
    require(len(trials) == protocol.required_trials,
            "run: found %d trials, protocol requires %d"
            % (len(trials), protocol.required_trials))

    failed = [trial for trial in trials if not trial["pass"]]
    failure_modes: dict[str, list[str]] = {}
    for trial in failed:
        for mode in trial["failure_modes"]:
            failure_modes.setdefault(mode, []).append(trial["trial"])
    overall_pass = not failed and len(trials) == protocol.required_trials

    objects = []
    for name, spec in protocol.objects.items():
        rows = by_object[name]
        objects.append({
            "name": name,
            "size_m": spec.size_m,
            "mass_kg": spec.mass_kg,
            "mu": spec.mu,
            "declared_trials": protocol.expected_trials.get(name),
            "found_trials": len(rows),
            "passed": sum(1 for row in rows if row["pass"]),
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": KIND,
        "protocol_id": protocol.protocol_id,
        "protocol_sha256": protocol.sha256,
        "stage": protocol.stage,
        "engine": protocol.engine,
        "run_dir": str(run_dir),
        "ref_window_s": REF_WINDOW_S,
        "criteria": {
            "drift_translation_max_mm": protocol.drift_max_mm,
            "drift_rotation_max_deg": protocol.drift_rot_max_deg,
            "drop_base_z_mm": protocol.drop_z_mm,
            "drop_rel_norm_mm": protocol.drop_norm_mm,
            "required_trials": protocol.required_trials,
            "max_initial_jitter_m": protocol.max_initial_jitter_m,
            "min_pad_contact_fraction_lift": protocol.lift_contact_min,
            "max_obj_ground_fraction_lift": protocol.lift_ground_max,
            "step_s": protocol.step_s,
            "pass_rule": "per trial: drift_translation_mm < limit, not drop, "
                         "and the optional contact-evidence criteria when declared; "
                         "overall: required_trials / required_trials pass",
            "resolved_keys": protocol.resolved_keys,
        },
        "objects": objects,
        "trials": trials,
        "verdict": "PASS" if overall_pass else "FAIL",
        "passed_trials": sum(1 for trial in trials if trial["pass"]),
        "failed_trials": [trial["trial"] for trial in failed],
        "failure_modes": failure_modes,
        "limitations": list(LIMITATIONS),
        "interpretation": INTERPRETATION,
    }


# --------------------------------------------------------------------------- #
# Reports.
# --------------------------------------------------------------------------- #
def _number_text(value: float | None, digits: int = 3) -> str:
    return "—" if value is None else ("%.*f" % (digits, value))


def _percent(value: float) -> str:
    return "%.0f%%" % (value * 100.0)


def render_markdown(summary: dict[str, Any]) -> str:
    criteria = summary["criteria"]
    lines: list[str] = []
    lines.append("# 真实接触抓取探针：预注册分析报告")
    lines.append("")
    lines.append("- run: %s" % summary["run_dir"])
    lines.append("- 协议: %s (protocol.json sha256 %s)"
                 % (summary["protocol_id"], summary["protocol_sha256"]))
    if summary.get("engine"):
        lines.append("- 物理引擎（协议声明，未在运行时校验）: %s" % summary["engine"])
    lines.append("- 判据来源: protocol.json；本报告不改动任何阈值，ref 固定在 close 最后 50 ms。")
    lines.append("")
    lines.append("## 预注册判据")
    lines.append("")
    lines.append("| 判据 | 值 |")
    lines.append("| --- | --- |")
    lines.append("| 单 trial 平移漂移 | < %s mm |" % _number_text(criteria["drift_translation_max_mm"]))
    lines.append("| 单 trial 旋转漂移 | %s |"
                 % ("未预注册（仅报告）" if criteria["drift_rotation_max_deg"] is None
                    else "< %s °" % _number_text(criteria["drift_rotation_max_deg"])))
    lines.append("| drop（基座系 z 下降） | > %s mm |" % _number_text(criteria["drop_base_z_mm"]))
    lines.append("| drop（ref 归一化偏差） | > %s mm |" % _number_text(criteria["drop_rel_norm_mm"]))
    lines.append("| lift 双侧 pad 接触下限 | %s |"
                 % ("未预注册（仅报告）" if criteria["min_pad_contact_fraction_lift"] is None
                    else ">= %s%%" % _number_text(criteria["min_pad_contact_fraction_lift"] * 100.0, 0)))
    lines.append("| lift 阶段 box 对地接触上限 | %s |"
                 % ("未预注册（仅报告）" if criteria["max_obj_ground_fraction_lift"] is None
                    else "<= %s%%" % _number_text(criteria["max_obj_ground_fraction_lift"] * 100.0, 0)))
    lines.append("| 总体判据 | %d/%d 全部通过 |"
                 % (criteria["required_trials"], criteria["required_trials"]))
    lines.append("")
    lines.append("## 运行与完整性")
    lines.append("")
    lines.append("| 项目 | 值 |")
    lines.append("| --- | --- |")
    lines.append("| stage | %s |" % (summary["stage"] or "未声明"))
    lines.append("| trial 数 | %d（预注册要求 %d） |"
                 % (len(summary["trials"]), criteria["required_trials"]))
    widths = ["%s×%d" % (item["name"], item["found_trials"]) for item in summary["objects"]]
    lines.append("| 对象 | %s |" % "、".join(widths))
    dt_med = sorted(trial["dt"]["median_s"] for trial in summary["trials"])
    lines.append("| 采样 | 每 trial %d-%d 帧，中位步长 %.6f s |"
                 % (min(trial["samples"] for trial in summary["trials"]),
                    max(trial["samples"] for trial in summary["trials"]), dt_med[len(dt_med) // 2]))
    lines.append("| 时间戳 | 全部严格递增（分析器拒绝乱序/重复 iter） |")
    identities = {trial["meta"]["identity_source"] for trial in summary["trials"]}
    if identities == {"protocol_and_meta"}:
        identity_text = "protocol+meta（尺寸/质量/摩擦逐 trial 交叉校验）"
    else:
        identity_text = ("meta_only（协议未声明 object_specs：尺寸/质量/摩擦只来自 meta，"
                         "无法交叉校验）")
    lines.append("| 对象身份校验 | %s |" % identity_text)
    lines.append("")
    lines.append("## 每 trial 指标")
    lines.append("")
    lines.append("| trial | 对象 | 采样 | 时长/s | drift_t/mm | drift_r/° | drop | lift 双侧接触 "
                 "| hold 对地 | 对地消失 t/s | f_close max/mean N | f_lift max/mean N | 判定 | 失败模式 |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
    for trial in summary["trials"]:
        contacts = trial["contacts"]
        lines.append(
            "| %s | %s | %d | %.2f | %s | %s | %s | %s | %s | %s | %s / %s | %s / %s | %s | %s |"
            % (trial["trial"], trial["object"], trial["samples"], trial["sim_duration_s"],
               _number_text(trial["drift"]["translation_mm"]),
               _number_text(trial["drift"]["rotation_deg"]),
               "是" if trial["drop"]["drop"] else "否",
               _percent(contacts["pad_fraction"]["lift"]["both"]),
               _percent(contacts["obj_ground_fraction"]["hold"]),
               _number_text(contacts["obj_ground_lost_t"], 2),
               _number_text(trial["forces"]["close"]["max_abs_n"]),
               _number_text(trial["forces"]["close"]["mean_abs_n"]),
               _number_text(trial["forces"]["lift"]["max_abs_n"]),
               _number_text(trial["forces"]["lift"]["mean_abs_n"]),
               "PASS" if trial["pass"] else "FAIL",
               ", ".join(trial["failure_modes"]) if trial["failure_modes"] else "—"))
    lines.append("")
    lines.append("## 每 trial 一行摘要")
    lines.append("")
    for trial in summary["trials"]:
        lines.append(
            "- **%s** (%s): %s；drift %.3f mm / %.3f°；对地接触消失 t=%s；"
            "lift 双侧接触 %s；close 力 max %.2f N；失败模式: %s"
            % (trial["trial"], trial["object"], "PASS" if trial["pass"] else "FAIL",
               trial["drift"]["translation_mm"], trial["drift"]["rotation_deg"],
               _number_text(trial["contacts"]["obj_ground_lost_t"], 2),
               _percent(trial["contacts"]["pad_fraction"]["lift"]["both"]),
               trial["forces"]["close"]["max_abs_n"],
               ", ".join(trial["failure_modes"]) if trial["failure_modes"] else "无"))
    lines.append("")
    lines.append("## 总体结论")
    lines.append("")
    if summary["verdict"] == "PASS":
        lines.append("**PASS**：%d/%d trial 全部满足预注册判据（平移漂移 < %s mm、旋转 < %s° 且未判 drop）。"
                     % (summary["passed_trials"], len(summary["trials"]),
                        _number_text(criteria["drift_translation_max_mm"]),
                        "—" if criteria["drift_rotation_max_deg"] is None
                        else _number_text(criteria["drift_rotation_max_deg"])))
        lines.append("")
        lines.append("该结论只覆盖本固定场景、固定对象、固定摩擦系数与协议声明的物理引擎/步长。")
    else:
        lines.append("**FAIL**：%d/%d trial 通过，失败 trial：%s。"
                     % (summary["passed_trials"], len(summary["trials"]),
                        "、".join(summary["failed_trials"]) or "（无）"))
        lines.append("")
        if summary["failure_modes"]:
            lines.append("失败模式归类（启发式，不参与 PASS/FAIL）：")
            for mode, trials in sorted(summary["failure_modes"].items()):
                lines.append("- %s: %s" % (mode, "、".join(trials)))
    lines.append("")
    lines.append("## 失败 trial 清单")
    lines.append("")
    if not summary["failed_trials"]:
        lines.append("无。")
    else:
        for trial in summary["trials"]:
            if trial["pass"]:
                continue
            lines.append(
                "- **%s** (%s): drift_t %.3f mm（限 %s）、drift_r %.3f°、drop=%s"
                "（z 下降 %.3f mm / norm 偏差 %.3f mm）、lift 双侧接触 %s、hold 对地 %s → 模式 %s"
                % (trial["trial"], trial["object"], trial["drift"]["translation_mm"],
                   _number_text(criteria["drift_translation_max_mm"]),
                   trial["drift"]["rotation_deg"], trial["drop"]["drop"],
                   trial["drop"]["base_z_decline_mm"], trial["drop"]["rel_norm_deviation_mm"],
                   _percent(trial["contacts"]["pad_fraction"]["lift"]["both"]),
                   _percent(trial["contacts"]["obj_ground_fraction"]["hold"]),
                   ", ".join(trial["failure_modes"])))
    lines.append("")
    lines.append("## 本结果不能证明什么")
    lines.append("")
    for index, limitation in enumerate(summary["limitations"], start=1):
        lines.append("%d. %s" % (index, limitation))
    lines.append("")
    lines.append("> " + summary["interpretation"])
    lines.append("")
    return "\n".join(lines)


def write_outputs(summary: dict[str, Any], json_out: Path | None, md_out: Path | None) -> None:
    if json_out is not None:
        _exclusive_write(json_out, json.dumps(summary, indent=2, ensure_ascii=False,
                                              allow_nan=False) + "\n")
    if md_out is not None:
        _exclusive_write(md_out, render_markdown(summary))


def _exclusive_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
    except FileExistsError as error:
        raise AnalysisError("%s: refusing to overwrite an existing report" % path) from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Analyze a preregistered real-contact grasp probe run.")
    parser.add_argument("--run-dir", type=Path, required=True,
                        help="results/<run_id> containing protocol.json and trial directories")
    parser.add_argument("--json-out", type=Path, default=None,
                        help="write the JSON summary here (exclusive create)")
    parser.add_argument("--md-out", type=Path, default=None,
                        help="write the Markdown report here (exclusive create)")
    args = parser.parse_args(argv)

    try:
        summary = analyze_run(args.run_dir)
        json_out = args.json_out or (args.run_dir / "analysis" / "summary.json")
        md_out = args.md_out or (args.run_dir / "analysis" / "REPORT.md")
        write_outputs(summary, json_out, md_out)
    except AnalysisError as error:
        print("analyze.py: INVALID INPUT: %s" % error, file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError) as error:  # pragma: no cover - safety net
        print("analyze.py: INVALID INPUT: %r" % error, file=sys.stderr)
        return 2

    verdict = summary["verdict"]
    print("%s: %d/%d trials passed; failed: %s"
          % (verdict, summary["passed_trials"], len(summary["trials"]),
             ", ".join(summary["failed_trials"]) or "none"))
    if summary["failure_modes"]:
        print("failure modes: " + "; ".join(
            "%s=%s" % (mode, ",".join(trials))
            for mode, trials in sorted(summary["failure_modes"].items())))
    print("json: %s" % json_out)
    print("markdown: %s" % md_out)
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
