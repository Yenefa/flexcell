#!/usr/bin/env python3
"""Render an experience entry into the exact shape each consumer reads, and check it landed.

THE DEFECT THIS EXISTS FOR
    consumers.py answers "which module can ACT on this entry". It does not answer "did the
    entry actually REACH that module". Those are different questions, and the gap between
    them is silent: an entry routed to the planner is handed to a prompt renderer that reads
    item["lesson"], while a v2 entry carries suggested_action. Nothing raises. The lesson
    simply does not appear, the plan does not change, and the ledger records NO_CHANGE -
    which reads exactly like "the lesson had no effect".

    That is the same failure class the objective records for route_lessons.py: a true lesson
    delivered to a channel that cannot carry it. Routing fixed the ADDRESS; this fixes the
    ENVELOPE.

WHY A RENDERER AND NOT A FIELD RENAME
    The entry schema is the durable thing: seven fields the master goal requires, reviewed
    and version-chained. The consumer's input shape is a prompt format that may change for
    prompt reasons. Coupling them by renaming a field in the schema would break every stored
    record; an explicit renderer keeps the mapping visible and testable, and a test asserts
    the renderer's output is what the consumer actually reads.

WHAT THIS CAN AND CANNOT SHOW
    DELIVERED   the entry's actionable text reached the consumer's input. Deterministic.
    DROPPED     the consumer would receive nothing actionable. Deterministic, and a defect.
    It does NOT show the plan changed - that needs a model call, and effect.py still reports
    UNMEASURED for prompt-level consumers rather than inventing a difference. Delivered is
    not the same as effective, and conflating them is how "we injected the lesson and the
    plan was identical" gets recorded as a null result about the LESSON.
"""
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "evolution", "experience"))
sys.path.insert(0, os.path.join(WT, "runtime", "planner"))

import consumers  # noqa: E402

DELIVERED = "DELIVERED"
DROPPED = "DROPPED"
UNSUPPORTED = "UNSUPPORTED"


def _slug(text, limit=48):
    """A registry-safe name for a rendered candidate."""
    import re
    words = re.findall(r"[a-z0-9]+", str(text).lower())
    return "-".join(words)[:limit].strip("-") or "unnamed-candidate"


def actionable_text(entry):
    """The one sentence a consumer should act on, and where it came from.

    suggested_action is the v2 field. A v1 record uses lesson. Both are accepted, and the
    SOURCE is returned so a reader can see which one was used rather than assuming.
    """
    for key in ("suggested_action", "lesson"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip(), key
    return "", None


def deliver_planner(entry, observation):
    """Return the observation with the entry appended in the shape describe() reads.

    describe() reads item.get("failure_class") and item.get("lesson"). Rendering into that
    exact shape is the whole point: writing the raw v2 entry would land in the list and
    render as an empty bullet.
    """
    text, source = actionable_text(entry)
    items = list(observation.get("experience") or [])
    items.append({"failure_class": entry.get("failure_class") or "UNKNOWN",
                  "lesson": text,
                  "_entry_id": entry.get("entry_id"),
                  "_from": source})
    out = dict(observation)
    out["experience"] = items
    return out


def deliver_parameter(entry):
    """Compose the kwargs a parameter consumer would be called with.

    This reuses skill_asset's binding table rather than restating it: if the entry cannot be
    bound to a callable, it cannot be delivered as a parameter either, and having two
    opinions about that would let one of them be wrong.
    """
    import skill_asset
    try:
        callable_spec = skill_asset.binding_for(entry)
    except skill_asset.AssetError as exc:
        return {"compiled": False, "why": str(exc)}
    exists = skill_asset.callable_exists({"callable": callable_spec})
    return {"compiled": True, "callable": callable_spec, "callable_exists": exists}


def deliver_config(entry):
    """A config consumer's delivery is a declared key/value, not a call.

    Reported separately because "the file contains this setting at the right value" is a
    checkable fact, whereas "the setting exists" alone would pass on a default.
    """
    import consumers as _consumers
    spec = _consumers.CONSUMERS.get("harness") or {}
    entrypoint = spec.get("entrypoint")
    symbol = spec.get("symbol")
    params = (entry.get("effect_spec") or {}).get("params") or {}
    wanted = params.get("participant_capacity")
    full = os.path.join(WT, entrypoint or "")
    if not (entrypoint and symbol and os.path.exists(full)):
        return {"present": False, "why": "entrypoint or symbol missing from this checkout"}
    text = open(full, encoding="utf-8", errors="replace").read()
    import re
    m = re.search(r"<%s>(\d+)</%s>" % (symbol, symbol), text)
    live = int(m.group(1)) if m else None
    ok = symbol in text and (wanted is None or live == wanted)
    return {"present": ok, "symbol": symbol, "live_value": live,
            "declared_value": wanted}


RENDERERS = {
    "planner": deliver_planner,
}


def deliver_non_text(entry):
    """Delivery for consumers that take a parameter or a config, not prompt text."""
    consumer = entry.get("consumer")
    if consumer in ("spread_policy", "executor_recovery"):
        detail = deliver_parameter(entry)
        if not detail.get("compiled"):
            return {"verdict": DROPPED,
                    "why": "no callable binding: %s" % detail.get("why")}
        if not detail.get("callable_exists"):
            return {"verdict": DROPPED,
                    "why": "the bound callable is absent from this checkout: %r"
                           % (detail["callable"],)}
        return {"verdict": DELIVERED,
                "why": "bound to %s.%s with %r"
                       % (detail["callable"]["module"], detail["callable"]["function"],
                          detail["callable"]["kwargs"]),
                "callable": detail["callable"]}
    if consumer == "harness":
        detail = deliver_config(entry)
        if not detail.get("present"):
            return {"verdict": DROPPED,
                    "why": detail.get("why") or "the declared config value is not in place"}
        return {"verdict": DELIVERED,
                "why": "%s is set to %r (entry declares %r)"
                       % (detail["symbol"], detail["live_value"],
                          detail["declared_value"]),
                "config": detail}
    if consumer == "development":
        detail = deliver_development(entry)
        if detail.get("verdict") == DELIVERED:
            return detail
        return detail
    return {"verdict": UNSUPPORTED,
            "why": "no delivery path for consumer %r" % (consumer,)}


# ---------------------------------------------------------------- development experience
# THE OBVIOUS DELIVERY IS A LIE, AND THE HONEST ONE IS STILL USEFUL.
#
# development_skills/registry.json declares four states. PROPOSED means "written,
# unit-tested, mutation-tested" and its own promotion_rule says tests are necessary but not
# sufficient. An experience entry has NO test file and NO mutation run, so writing it into
# the registry as PROPOSED would be a false status - the registry would then be claiming a
# verification that never happened. That is why this consumer had no delivery path, and why
# adding one carelessly would have been worse than the gap.
#
# What an entry CAN honestly reach is the registry's candidate side: the shape a future
# agent reads when deciding what to test next. So delivery renders that shape and REPORTS
# WHICH REGISTRY FIELDS THE ENTRY CANNOT SUPPLY, rather than filling them with prose. A
# candidate that names its own missing tests is more useful than a PROPOSED entry that
# quietly has none.
REGISTRY_REQUIRED = ("name", "status", "status_reason", "trigger", "evidence", "incidents",
                     "entrypoints", "tests", "mutation", "revisit_metrics")
# fields an experience entry structurally cannot supply: they describe work done on a TOOL,
# which an experience entry does not contain
REGISTRY_NEEDS_A_TOOL = ("entrypoints", "tests", "mutation")


def deliver_development(entry):
    """Render an entry into the development-skills candidate shape.

    DELIVERED means the rendered candidate carries everything a future agent needs to
    evaluate and test the practice: a trigger, the actionable text, the measured provenance,
    and an honest statement of what is missing. It is NOT a claim that the practice works -
    effect stays NOT_MEASURED, exactly as the registry's own legend requires.
    """
    text, source = actionable_text(entry)
    if not text:
        return {"verdict": DROPPED, "why": "the entry carries no actionable text"}
    trigger = " ".join(entry.get("applicable_when") or []) or None
    if not trigger:
        # A skill with no stated trigger cannot be loaded at the right moment, which is the
        # failure mode that made adoption zero in the first place.
        return {"verdict": DROPPED,
                "why": "no applicable_when: a skill with no trigger is never loaded"}
    name = _slug(text)
    candidate = {
        "name": name,
        "status": "CANDIDATE_NOT_IN_REGISTRY",
        "status_reason": ("rendered from experience entry %s; it has no entrypoint, no test "
                          "file and no mutation run, so it may not be recorded as PROPOSED"
                          % (entry.get("entry_id") or "?")),
        "trigger": trigger,
        "action": text,
        "action_source": source,
        "evidence": ["setup/acceptance/evobot_continual_chain_20261118/records_v2.jsonl"],
        "measured_on": {"task_family": entry.get("task_family"),
                        "failure_class": entry.get("failure_class"),
                        "split": (entry.get("evidence") or {}).get("split")},
        "revisit_metrics": {"effect": "NOT_MEASURED",
                            "why": "an experience entry carries no with/without comparison "
                                   "of a development practice"},
        # the honest part: the registry requires these and the entry cannot supply them
        "missing_for_proposed": list(REGISTRY_NEEDS_A_TOOL),
    }
    missing = [k for k in REGISTRY_REQUIRED if k not in candidate]
    return {"verdict": DELIVERED,
            "why": ("rendered a candidate for the development-skills registry; %d/%d registry "
                    "fields are structurally unavailable to an experience entry"
                    % (len(REGISTRY_NEEDS_A_TOOL), len(REGISTRY_REQUIRED))),
            "candidate": candidate,
            "missing_registry_fields": REGISTRY_NEEDS_A_TOOL,
            "note": ("delivered to the CANDIDATE side on purpose: PROPOSED requires a test "
                     "file and a mutation run this entry does not have, and claiming it "
                     "would be the overstatement the registry's promotion_rule warns about")}


def deliver(entry, observation=None):
    """Render one entry for its consumer and report whether the text survived.

    Returns a dict, never raises: a consumer with no renderer is UNSUPPORTED, which is a
    fact about this package's coverage and must be visible rather than treated as success.
    """
    consumer = entry.get("consumer")
    out = {"entry_id": entry.get("entry_id"), "consumer": consumer}
    text, source = actionable_text(entry)
    out["text"] = text
    out["text_source"] = source
    if not text:
        out.update(verdict=DROPPED, why="the entry carries no actionable text in either "
                                        "suggested_action or lesson")
        return out
    renderer = RENDERERS.get(consumer)
    if renderer is None:
        # A parameter or config consumer does not take prompt text; ask the non-text path
        # before declaring the entry undeliverable, or every parameterised entry would be
        # reported UNSUPPORTED just because it has no "lesson" sentence.
        out.update(deliver_non_text(entry))
        return out
    if consumer == "planner":
        if observation is None:
            out.update(verdict=UNSUPPORTED, why="planner delivery needs an observation")
            return out
        enriched = renderer(entry, observation)
        import agent_planner
        prompt = agent_planner.describe(enriched)
        out["delivered"] = text in prompt
        out["prompt_sha"] = _sha(prompt)
        out["verdict"] = DELIVERED if out["delivered"] else DROPPED
        out["why"] = ("the lesson text appears in the rendered prompt"
                      if out["delivered"] else
                      "the lesson text does NOT appear in the rendered prompt")
        return out
    out.update(verdict=UNSUPPORTED, why="renderer for %r is not implemented" % (consumer,))
    return out


def _sha(text):
    import hashlib
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


if __name__ == "__main__":
    import json
    doc = json.loads(open(sys.argv[1], encoding="utf-8").read())
    print(json.dumps(deliver(doc), indent=2))
