#!/usr/bin/env python3
"""For each failure signature the generator calls UNROUTED: is that a fact or a shrug?

THE GAP THIS EXISTS FOR
    postmortem.generate() reports 8 of 9 signatures as UNROUTED, which covers 92 of the 98
    failures in the archive:

        "UNROUTED: no consumer in this stack declares a change for 'graded_push', so the
         knowledge would be a number in a document"

    That sentence is a statement about OUR SIGNATURE TABLE, not about the world. It reads as
    "nothing here can act" while actually meaning "nobody has written a mapping". The two are
    very different: the first is a measured limit, the second is unwritten work.

    The objective already records what happens when the difference is ignored.
    route_lessons.py injected a lesson about landing coordinates into a planner that can only
    emit object->zone, and the plan came out identical. The lesson was true; the address was
    wrong. UNROUTED is that failure caught one step earlier - or, just as often, a capable
    module hiding behind a missing table entry.

WHAT IT DOES
    For a signature with no declared consumer, look for a module whose OUTPUT could carry the
    lesson, and MEASURE whether that output was already correct on the archived instances.

        ALREADY_CORRECT   the capable module's output was right on every instance checked, so
                          routing the lesson there would change nothing. UNROUTED is right,
                          but for a reason nobody had measured.
        FAILED_INSTANCES  the output was wrong somewhere: the lesson has a real address and
                          the table is missing it. This is the actionable case.
        UNMEASURED        no probe exists yet. Reported as such rather than guessed.

    Distinguishing these is the whole point: an archive that says "8 signatures unrouted"
    tells a reader there are eight problems, when some may be nothing to do and one may be
    the whole opportunity.

    A NOTE ON WHAT THIS FILE REFUSED TO DO: the first version also asserted "no capable
    module" for six signatures on the strength of their names alone. Those names describe the
    grader's verdict, not an action - but "obviously nothing can act on a grader verdict" is
    still an unmeasured claim, and this module exists to stop exactly that. They are now
    UNMEASURED with a hypothesis attached, and the hypothesis is labelled as one.
"""
import glob
import json
import math
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))

import postmortem  # noqa: E402

ALREADY_CORRECT = "ALREADY_CORRECT"
FAILED_INSTANCES = "FAILED_INSTANCES"
UNMEASURED = "UNMEASURED"

# An instruction that asks the planner to COMPARE two distances and then choose a bin. The
# choice is decidable from the observation alone, so the planner's output can be scored.
_DISTANCE_INSTRUCTION = "Compare distances before moving"


def _dist(a, b):
    return math.dist(list(a)[:2], list(b)[:2])


def _find(acceptance, instance, name):
    hits = glob.glob(os.path.join(acceptance, "**", instance, name), recursive=True)
    return hits[0] if hits else None


def _expected_bin(observation_input):
    """The bin the instruction requires, computed from the observation, or None.

    The clause is: "if the blue block is closer to the LEFT bin than to the right bin, put
    BOTH blocks in the RIGHT bin; otherwise put BOTH in the LEFT bin". Both branches are
    decidable with two distance comparisons - which is exactly why a planner could act on it.
    """
    instruction = str(observation_input.get("instruction") or "")
    if _DISTANCE_INSTRUCTION not in instruction:
        return None
    zones = {z["name"]: z["position"] for z in observation_input.get("zones") or []}
    blue = [o for o in observation_input.get("objects") or [] if o.get("color") == "blue"]
    if len(zones) < 2 or not blue:
        return None
    left = min(zones, key=lambda name: zones[name][0])
    right = max(zones, key=lambda name: zones[name][0])
    closer_to_left = _dist(blue[0]["position"], zones[left]) < _dist(
        blue[0]["position"], zones[right])
    return right if closer_to_left else left


def probe_planner_object_set(instances, acceptance):
    """Score the planner's bin choice on each instance. A capable module already right on
    every instance means the lesson has no address there."""
    checked, wrong = 0, []
    for instance in sorted(instances):
        obs_path = _find(acceptance, instance, "observation_input.json")
        reply_path = _find(acceptance, instance, "agent_reply.json")
        if not (obs_path and reply_path):
            continue
        try:
            observation = json.load(open(obs_path, encoding="utf-8"))
            reply = json.load(open(reply_path, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        want = _expected_bin(observation)
        if want is None:
            continue
        moves = [m for m in ((reply.get("agent_plan") or {}).get("moves") or [])
                 if isinstance(m, dict)]
        objects = {str(o.get("name")) for o in observation.get("objects") or []}
        chosen = {str(m.get("object")): m.get("zone") for m in moves}
        checked += 1
        # the instruction says put BOTH blocks in one bin, so the plan must name every object
        # and every one of them must go to the required bin
        if set(chosen) != objects or any(chosen.get(n) != want for n in objects):
            wrong.append({"instance": instance, "wanted": want,
                          "planned": {n: chosen.get(n) for n in sorted(objects)}})
    return {"consumer": "planner", "action_kind": "object_set", "instances_checked": checked,
            "instances_wrong": len(wrong), "wrong": wrong}


# signature -> a probe for the module that could carry it. ONLY signatures with a probe get
# a measured verdict; everything else is reported UNMEASURED rather than guessed at. An
# earlier version of this file also asserted "no capable module" for six signatures on the
# strength of their names, which is exactly the kind of unmeasured claim this module exists
# to stop.
def probe_push_recovery(instances, acceptance):
    """Can push_recover act on a failed push, and can THIS ARCHIVE show it?

    push_recover is a real closed-loop retry policy: after PushObject reports contact lost
    with the object short of the requested distance, it asks for the remainder. Its batch
    records a with/without comparison - single shot 2/5 terminal pass, closed loop 4/5 - and
    diagnoses the residue (the object is flicked BACKWARD by contact geometry, which a retry
    policy cannot fix).

    So a capable module exists. What this probe reports is that THE ARCHIVE ALREADY HERE
    CANNOT MEASURE ITS EFFECT, for a reason worth naming:

        the recorded attempts were produced BY the policy under test. Replaying a policy
        against its own output cannot show what the policy changed - the attempts already
        contain its decisions. That is a selection effect, not a null result.

    Measured: replaying the shipped policy over the recorded attempts reproduces the
    recorded verdict in 5 of 5 trials, which is a CORRECTNESS check on the replay, not an
    effect measurement. Re-running the same attempts with the pre-fix magnitude reading
    changes no outcome either, because those attempts were generated under the fix.
    """
    attempts_total, verdicts_matched, usable = 0, 0, []
    push_recover = _load_push_recover()
    if push_recover is None:
        return {"consumer": "executor_recovery", "action_kind": "recovery_action",
                "instances_checked": 0, "instances_wrong": 0, "wrong": [],
                "module_available": False,
                "why": "push_recover is not importable from this checkout"}
    batch = os.path.join(acceptance, "evobot_push_recover_20261112", "evidence")
    for trial in range(1, 6):
        path = os.path.join(batch, "recovery_t%d.json" % trial)
        if not os.path.exists(path):
            continue
        try:
            record = json.load(open(path, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        attempts = record.get("attempts") or []
        recorded = (record.get("verdict") or {}).get("outcome")
        if not attempts:
            continue
        attempts_total += len(attempts)
        try:
            replay = push_recover.accumulate(attempts, 0.09)
        except Exception:  # noqa: BLE001 - a replay failure is data
            continue
        if replay.get("outcome") == recorded:
            verdicts_matched += 1
        usable.append({"trial": trial, "attempts": len(attempts),
                       "recorded_outcome": recorded,
                       "replayed_outcome": replay.get("outcome")})
    return {"consumer": "executor_recovery", "action_kind": "recovery_action",
            # NOT instances_wrong: a selection effect is not a module failure, and reporting
            # it as one would have this signature classified FAILED_INSTANCES on no evidence
            "instances_checked": 0, "instances_wrong": 0, "wrong": [],
            "module_available": True, "attempts_replayed": attempts_total,
            "verdicts_reproduced": verdicts_matched, "trials": usable,
            "selection_effect": (
                "the recorded attempts were produced by the policy under test, so replaying "
                "it over them cannot measure what it changed; a with/without comparison "
                "needs attempts recorded WITHOUT the policy")}


def _load_push_recover():
    path = os.path.join(WT, "src", "flexcell", "flexcell_skills", "flexcell_skills",
                        "contracts")
    if path not in sys.path:
        sys.path.insert(0, path)
    try:
        import push_recover
        return push_recover
    except Exception:  # noqa: BLE001 - an unimportable module is a fact, not a crash
        return None

# Which consumers PLAUSIBLY map to a signature, so the gap is actionable rather than a shrug.
# This is a hypothesis to test, NOT a measurement, and it is reported as such.
CANDIDATE_CONSUMERS = {
    "placement_clause_failed": ["planner"],
    "graded_push": ["executor_recovery"],
    "graded_visit": ["planner"],
    "graded_visit_sequence": ["planner"],
    "graded_relative": ["planner"],
    "graded_unmoved": ["executor_recovery"],
    "unconfirmed_native": ["executor_recovery", "harness"],
}


PROBES = {
    # the wrong-bin failure: the planner decides object->zone, so it is the first candidate
    "placement_clause_failed": probe_planner_object_set,
    # the push failure: push_recover decides whether to retry - see probe_push_recovery
    "graded_push": probe_push_recovery,
}


def classify(signature, instances, acceptance):
    """State what is actually known about one unrouted signature."""
    probe = PROBES.get(signature)
    if probe is None:
        return {"state": UNMEASURED,
                "why": ("no probe has been written for this signature, so whether a module "
                        "could act on it is unknown - not answered"),
                "candidate_consumers": CANDIDATE_CONSUMERS.get(signature, []),
                "probe_is": ("a hypothesis to test; it is NOT a measurement and must not be "
                             "cited as one")}
    result = probe(instances, acceptance)
    if result.get("selection_effect"):
        # A MODULE EXISTS BUT THIS ARCHIVE CANNOT MEASURE IT. That is neither "already
        # correct" nor "wrong somewhere", and collapsing it into either would be a made-up
        # answer to a question the data cannot settle.
        return {"state": UNMEASURED,
                "why": ("a capable module exists (%s) but the archive cannot measure its "
                        "effect: %s" % (result.get("consumer"), result["selection_effect"])),
                "probe": result, "module_found": True,
                "candidate_consumers": [result.get("consumer")]}
    if not result["instances_checked"]:
        return {"state": UNMEASURED, "why": "the probe found no scoreable instance",
                "probe": result}
    if not result["instances_wrong"]:
        return {"state": ALREADY_CORRECT,
                "why": ("%s already produced the required output on all %d scoreable "
                        "instances, so routing the lesson there would change nothing"
                        % (result["consumer"], result["instances_checked"])),
                "probe": result}
    return {"state": FAILED_INSTANCES,
            "why": ("%s was wrong on %d of %d scoreable instances: the lesson has a real "
                    "address and the signature table is missing it"
                    % (result["consumer"], result["instances_wrong"],
                       result["instances_checked"])),
            "probe": result}


def report(acceptance=None):
    """Every signature the generator refuses as UNROUTED, with a measured reason."""
    acceptance = acceptance or os.path.join(WT, "setup", "acceptance")
    failures, _ = postmortem.scan_with_report(acceptance, include_held_out=False)
    by_signature = {}
    for failure in failures:
        signature = postmortem.signature_of(failure)
        instances = by_signature.setdefault(signature, set())
        instances.add(os.path.basename(os.path.dirname(failure["path"])))
    _, generation = postmortem.generate(acceptance=acceptance)
    out = []
    for signature, record in sorted(generation["signatures"].items()):
        if record.get("built"):
            continue
        why = str(record.get("why") or "")
        if not why.startswith("UNROUTED"):
            continue
        verdict = classify(signature, by_signature.get(signature, set()), acceptance)
        row = dict(verdict, signature=signature,
                   occurrences=record.get("occurrences"),
                   instances=len(by_signature.get(signature, ())),
                   generator_said=why)
        # A probe that says "this archive cannot measure it" is a claim about the path the
        # probe reads, NOT about the repository. evobot_push_feedback_20261112 holds an
        # independently collected A/B batch the replay probe never looked at, so leaving
        # the UNMEASURED verdict unqualified would overstate the absence of evidence.
        if row.get("state") == "UNMEASURED":
            try:
                import push_comparison
                external = push_comparison.measure(acceptance)
            except Exception as exc:  # noqa: BLE001 - a missing reader is not a measurement
                external = {"measured": False, "why": str(exc)}
            row["external_comparison"] = external
            if external.get("measured") and external.get("is_real_comparison"):
                row["why"] = (row.get("why", "") +
                              " | BUT the repo DOES hold an independently collected "
                              "with/without batch outside this probe's path: control "
                              "%s/%s -> feedback %s/%s (n=3, one dev instance, not "
                              "isolated)" % (external["control_passes"],
                                             external["control_runs"],
                                             external["feedback_passes"],
                                             external["feedback_runs"]))
        out.append(row)
    counts = {}
    for row in out:
        counts[row["state"]] = counts.get(row["state"], 0) + 1
    return {"unrouted": out, "by_state": counts,
            "failures_covered": sum(row["occurrences"] or 0 for row in out),
            "instances_covered": sum(row["instances"] or 0 for row in out),
            "claim": ("UNROUTED means no consumer declares a mapping. That is a statement "
                      "about this stack's signature table, not about whether a module could "
                      "act. Each one is now either measured as already correct, measured as "
                      "wrong somewhere, or honestly unmeasured")}


if __name__ == "__main__":
    print(json.dumps(report(), indent=2, ensure_ascii=False))
