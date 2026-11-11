#!/usr/bin/env python3
"""Evidence schema for a physical T08 push verdict.

WHY A SCHEMA AND NOT JUST A DICT
    Evidence is only usable if a reader can tell, without asking the author,
    whether it is complete. Every field here answers one question:

      who produced this?   -> source.trusted_source_id, never the agent
      when?                -> run.execution_window, two clocks
      is it whole?         -> sample_count / dropped_samples / max_gap_ns
      is it consistent?    -> strictly increasing sequence, finite values
      is it the right task?-> task.task_id + task.task_sha256
      has it been altered? -> manifest.sha256 over every input file

FAIL-CLOSED IS THE DEFAULT, NOT THE FINAL STEP
    validate() returns a list of PROBLEMS; only an empty list means valid.
    There is no assume-valid path: a missing field is a problem, an unknown
    trusted source is a problem, a wrong type is a problem. A verifier that
    had to remember to check something would eventually forget one.

WHY THE AGENT CANNOT SATISFY THIS
    Nothing here is written by the skill. It is read from step logs the
    Gazebo plugins write inside the physics loop. A skill reporting SUCCEEDED
    does not touch any of it.
"""

import hashlib
import math

SCHEMA_VERSION = "t08-evidence/1.0"

# A trajectory that covers only the target cannot detect "the arm swept the
# blue block aside on the way", which T08 forbids. Absence of evidence about
# the protected object is not evidence that it was safe.
REQUIRED_ROLES = ("target", "protected")

# Sources a verdict may rest on. Note what is absent: there is no "agent" and
# no "skill_report" entry, because a claim is not a measurement.
TRUSTED_SOURCES = {
    "flexcell::PhysicsTrace/v1": "Gazebo PostUpdate, every physics step",
    "flexcell::ContactTrace/v1": "Gazebo PostUpdate, every physics step",
}

# One sample is a fixed-length list so a truncated or reordered record is
# detectable by shape alone:
#   [seq, sim_ns, monotonic_ns, x, y, z, qx, qy, qz, qw]
SAMPLE_WIDTH = 10


def _finite(value):
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(float(value)))


def _is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def _problems_task(section):
    if not isinstance(section, dict):
        return ["task: missing or not an object"]
    out = []
    if not isinstance(section.get("task_id"), str) or not section["task_id"]:
        out.append("task.task_id: missing")
    digest = section.get("task_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        out.append("task.task_sha256: missing or not a sha256 hex digest")
    else:
        try:
            int(digest, 16)
        except ValueError:
            out.append("task.task_sha256: not hexadecimal")
    for key in ("target_object", "protected_object"):
        if not isinstance(section.get(key), str) or not section[key]:
            out.append("task.%s: missing" % key)
    if not _finite(section.get("rest_height_m")):
        out.append("task.rest_height_m: missing or not finite")
    return out


def _problems_run(section):
    if not isinstance(section, dict):
        return ["run: missing or not an object"]
    out = []
    if not isinstance(section.get("run_id"), str) or not section["run_id"]:
        out.append("run.run_id: missing")
    window = section.get("execution_window")
    if not isinstance(window, dict):
        return out + ["run.execution_window: missing"]
    keys = ("start_sim_ns", "end_sim_ns", "start_mono_ns", "end_mono_ns")
    for key in keys:
        if not _is_int(window.get(key)):
            out.append("run.execution_window.%s: missing or not an integer" % key)
    if all(_is_int(window.get(k)) for k in keys):
        if window["end_sim_ns"] <= window["start_sim_ns"]:
            out.append("run.execution_window: sim window empty or inverted")
        if window["end_mono_ns"] <= window["start_mono_ns"]:
            out.append("run.execution_window: monotonic window empty or inverted")
    return out


def _problems_source(section):
    if not isinstance(section, dict):
        return ["source: missing or not an object"]
    out = []
    ident = section.get("trusted_source_id")
    if ident not in TRUSTED_SOURCES:
        out.append("source.trusted_source_id: %r is not a trusted physical source"
                   % (ident,))
    if section.get("agent_reported") is not False:
        # Absence of the flag is not enough: a bundle must positively declare
        # that no agent supplied its numbers.
        out.append("source.agent_reported: must be explicitly false")
    return out


def _problems_one_trajectory(name, entry):
    if not isinstance(entry, dict):
        return ["objects.%s: missing" % name]
    out = []
    role = entry.get("role")
    if role not in REQUIRED_ROLES:
        out.append("objects.%s.role: %r not one of %s" % (name, role, REQUIRED_ROLES))
    samples = entry.get("samples")
    if not isinstance(samples, list) or not samples:
        return out + ["objects.%s.samples: missing or empty" % name]
    if entry.get("sample_count") != len(samples):
        out.append("objects.%s.sample_count: declared %r but %d present"
                   % (name, entry.get("sample_count"), len(samples)))
    dropped = entry.get("dropped_samples")
    if not _is_int(dropped) or dropped < 0:
        out.append("objects.%s.dropped_samples: missing or negative" % name)
    gap = entry.get("max_gap_ns")
    if not _is_int(gap) or gap <= 0:
        out.append("objects.%s.max_gap_ns: missing or non-positive" % name)
    previous_seq = previous_sim = None
    for index, sample in enumerate(samples):
        where = "objects.%s.samples[%d]" % (name, index)
        if not isinstance(sample, (list, tuple)) or len(sample) != SAMPLE_WIDTH:
            out.append(where + ": must be %d numbers" % SAMPLE_WIDTH)
            break
        if not all(_finite(v) for v in sample):
            out.append(where + ": non-numeric or non-finite field")
            break
        sequence, sim_ns = int(sample[0]), int(sample[1])
        quaternion = [float(v) for v in sample[6:10]]
        norm = math.sqrt(sum(v * v for v in quaternion))
        if abs(norm - 1.0) > 1e-3:
            # A zero or unnormalised quaternion is a corrupt read, not a
            # rotation, and would make any orientation test meaningless.
            out.append(where + ": quaternion norm %.6f is not 1" % norm)
            break
        if previous_seq is not None:
            if sequence <= previous_seq:
                out.append(where + ": sequence not strictly increasing")
                break
            if sequence != previous_seq + 1:
                out.append(where + ": sequence jumps %d -> %d"
                           % (previous_seq, sequence))
                break
            if sim_ns <= previous_sim:
                out.append(where + ": sim time not increasing")
                break
            if sim_ns - previous_sim > gap:
                out.append(where + ": sample gap %d ns exceeds declared max %d"
                           % (sim_ns - previous_sim, gap))
                break
        previous_seq, previous_sim = sequence, sim_ns
    return out


def _problems_objects(section, task):
    if not isinstance(section, dict) or not section:
        return ["objects: missing or empty"]
    out = []
    roles = [e.get("role") for e in section.values() if isinstance(e, dict)]
    for required in REQUIRED_ROLES:
        if required not in roles:
            out.append("objects: no trajectory carries role %r" % required)
    for name, entry in sorted(section.items()):
        out.extend(_problems_one_trajectory(name, entry))
    if isinstance(task, dict):
        for key in ("target_object", "protected_object"):
            declared = task.get(key)
            if declared and declared not in section:
                out.append("objects: task declares %s=%r but no trajectory for it"
                           % (key, declared))
    return out


def _problems_contacts(section):
    if not isinstance(section, dict):
        return ["contacts: missing or not an object"]
    out = []
    if section.get("trusted_source_id") not in TRUSTED_SOURCES:
        out.append("contacts.trusted_source_id: not a trusted contact source")
    if not isinstance(section.get("pusher_links"), list) or not section["pusher_links"]:
        out.append("contacts.pusher_links: must be a non-empty list")
    # component_present is why ContactTrace exists: it separates "no contact
    # happened" from "the contact component was never there". Treating those
    # as the same would pass a run whose simulator never reported contacts.
    if section.get("component_present") is not True:
        out.append("contacts.component_present: must be explicitly true; a "
                   "contact component that was absent cannot testify that no "
                   "contact occurred")
    intervals = section.get("intervals")
    if not isinstance(intervals, list):
        out.append("contacts.intervals: missing (an empty list is allowed, but "
                   "the absence of the field is not the same as the absence of "
                   "contact)")
    else:
        for index, item in enumerate(intervals):
            where = "contacts.intervals[%d]" % index
            if not isinstance(item, dict):
                out.append(where + ": not an object")
                continue
            if not _is_int(item.get("start_sim_ns")) or not _is_int(item.get("end_sim_ns")):
                out.append(where + ": missing integer bounds")
            elif item["end_sim_ns"] <= item["start_sim_ns"]:
                out.append(where + ": empty or inverted interval")
            if not isinstance(item.get("other"), str) or not item["other"]:
                out.append(where + ": missing contact partner name")
    return out


def _problems_gripper(section):
    if not isinstance(section, dict):
        return ["gripper: missing or not an object"]
    out = []
    if not isinstance(section.get("joint_name"), str) or not section["joint_name"]:
        out.append("gripper.joint_name: missing")
    if not _finite(section.get("min_aperture_rad")) or not _finite(section.get("max_aperture_rad")):
        out.append("gripper: aperture range missing or not finite")
    if section.get("span") and not isinstance(section["span"], list):
        out.append("gripper.span: must be a list of [mono_ns, aperture_rad]")
    return out


def _problems_attachment(section):
    if not isinstance(section, dict):
        return ["attachment: missing or not an object"]
    out = []
    if not isinstance(section.get("attached_during_window"), bool):
        # Recorded presence of an attachment is VALID evidence - of a carry.
        # The gate judges it; the schema only requires that it was observed and
        # stated as a boolean, so "carried" never collapses into "corrupt".
        out.append("attachment.attached_during_window: must be a boolean")
    if not _is_int(section.get("events")) or section["events"] < 0:
        out.append("attachment.events: missing or negative")
    return out


def _problems_teleport(section):
    if not isinstance(section, dict):
        return ["teleport: missing or not an object"]
    out = []
    if not _finite(section.get("max_single_step_jump_m")):
        out.append("teleport.max_single_step_jump_m: missing or not finite")
    if not _finite(section.get("jump_threshold_m")):
        out.append("teleport.jump_threshold_m: missing or not finite")
    return out


def _problems_manifest(section, files=None):
    if not isinstance(section, dict):
        return ["manifest: missing or not an object"]
    out = []
    entries = section.get("files")
    if not isinstance(entries, dict) or not entries:
        return ["manifest.files: missing or empty"]
    for path, digest in sorted(entries.items()):
        if not isinstance(digest, str) or len(digest) != 64:
            out.append("manifest.files[%r]: not a sha256 digest" % path)
    if files is not None:
        for path in sorted(files):
            if path not in entries:
                out.append("manifest.files: input %r is not covered by the manifest"
                           % path)
    if not isinstance(section.get("bundle_sha256"), str):
        out.append("manifest.bundle_sha256: missing")
    return out


def validate(bundle, files=None):
    """Return a list of problems. Empty means the bundle is valid.

    files: optional iterable of input file names that the manifest must cover.
    Passing it turns the manifest into a completeness check rather than a
    decoration, because an uncovered input is an unverifiable input.
    """
    if not isinstance(bundle, dict):
        return ["bundle: not an object"]
    problems = []
    if bundle.get("schema_version") != SCHEMA_VERSION:
        problems.append("schema_version: expected %r got %r"
                        % (SCHEMA_VERSION, bundle.get("schema_version")))
    for key in ("task", "run", "source", "objects", "contacts", "gripper",
                "attachment", "teleport", "manifest"):
        if key not in bundle:
            problems.append("%s: section missing" % key)
    problems += _problems_task(bundle.get("task"))
    problems += _problems_run(bundle.get("run"))
    problems += _problems_source(bundle.get("source"))
    problems += _problems_objects(bundle.get("objects"), bundle.get("task"))
    problems += _problems_contacts(bundle.get("contacts"))
    problems += _problems_gripper(bundle.get("gripper"))
    problems += _problems_attachment(bundle.get("attachment"))
    problems += _problems_teleport(bundle.get("teleport"))
    problems += _problems_manifest(bundle.get("manifest"), files)
    return problems


def sha256_file(path, block=1 << 20):
    digest = hashlib.sha256()
    with open(path, "rb") as stream:
        while True:
            chunk = stream.read(block)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def bundle_sha256(bundle):
    """Digest over everything except the digest field itself.

    Canonical JSON (sorted keys, no whitespace) so the digest does not depend
    on formatting. The manifest entry for the bundle is excluded by name,
    otherwise the value would depend on itself.
    """
    import json
    clone = dict(bundle)
    manifest = dict(clone.get("manifest") or {})
    manifest.pop("bundle_sha256", None)
    clone["manifest"] = manifest
    payload = json.dumps(clone, sort_keys=True, separators=(",", ":"),
                         allow_nan=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

