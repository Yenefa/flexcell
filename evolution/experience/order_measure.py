#!/usr/bin/env python3
"""Measure the planner's order check on the archive, for BOTH order clauses.

WHY THIS EXISTS
    The planner's SYSTEM prompt says "If the instruction fixes an order, follow it exactly."
    The first order rule caught one clause: "the X block must be put there FIRST". A second
    clause, "passing through the RIGHT bin first", was invisible to it - and the archive
    holds 24 instructions with that wording, 21 of which planned the FIRST move to the wrong
    bin while their why-text claimed to follow the instruction.

    A rule that refuses a CORRECT plan is worse than one that misses a wrong plan: it changes
    behaviour on runs that were already right. So this module reports true/false positives
    separately, not one accuracy number.
"""
import glob
import json
import os
import sys

WT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(WT, "runtime", "planner"))

import agent_planner  # noqa: E402

_PASS_THROUGH = ("passing through", "first")


def _iter_instances(acceptance):
    for path in glob.glob(os.path.join(acceptance, "**", "observation_input.json"),
                          recursive=True):
        directory = os.path.dirname(path)
        reply = os.path.join(directory, "agent_reply.json")
        if not os.path.exists(reply):
            continue
        try:
            observation = json.load(open(path, encoding="utf-8"))
            plan = json.load(open(reply, encoding="utf-8"))
        except (OSError, ValueError):
            continue
        moves = (plan.get("agent_plan") or {}).get("moves") or []
        if moves:
            yield directory, observation, moves


def measure(acceptance=None):
    """Score the pass-through clause against what each archived plan actually did.

    Ground truth is derived from the OBSERVATION's own zone positions (right = largest x),
    never from the evaluator's verdict - a check that reads the answer cannot be used to
    decide whether a plan will pass.
    """
    acceptance = acceptance or os.path.join(WT, "setup", "acceptance")
    tp = fp = tn = fn = 0
    examples = []
    for directory, observation, moves in _iter_instances(acceptance):
        text = str(observation.get("instruction") or "").lower()
        if not all(word in text for word in _PASS_THROUGH):
            continue
        zones = {z["name"]: float(z["position"][0])
                 for z in observation.get("zones") or []
                 if isinstance(z.get("position"), (list, tuple)) and len(z["position"]) >= 2}
        if len(zones) < 2:
            continue
        right = max(zones, key=lambda name: zones[name])
        actually_wrong = moves[0].get("zone") != right
        flagged = agent_planner.check_plan_order(observation, moves) is not None
        if actually_wrong and flagged:
            tp += 1
        elif actually_wrong:
            fn += 1
            examples.append({"instance": os.path.basename(directory), "case": "MISSED"})
        elif flagged:
            fp += 1
            examples.append({"instance": os.path.basename(directory), "case": "FALSE_POSITIVE"})
        else:
            tn += 1
    return {"clause": "passing through the <left|right> bin first",
            "true_positives": tp, "false_positives": fp,
            "true_negatives": tn, "false_negatives": fn,
            "checked": tp + fp + tn + fn,
            "examples": examples[:8],
            "claim": ("false positives must be zero: an order rule that refuses a correct "
                      "plan changes behaviour on runs that were already right. Ground truth "
                      "comes from the observation's zone positions, not the evaluator")}


if __name__ == "__main__":
    print(json.dumps(measure(), indent=2))
