#!/usr/bin/env python3
"""Split a held-out TaskSpec into a PUBLIC task and a SEALED answer.

WHY: the evaluator needs expected_goal to grade. The agent must never see it. Until now
both lived in the same checkout and isolation was only a documented promise.

Design:
  PUBLIC  benchmark/held_out/public/<opaque>.json
          instruction, objects, zones, task_id, evaluator_version, budget, split.
          NO expected_goal, NO constraints, NO random_seed, NO task template hint.
          The task_id is opaque so the public file does not reveal the seed.
  SEALED  /etc/evobot/sealed/<opaque>.json  (root:root, mode 600)
          expected_goal, template_id, random_seed, instance_sha256, public task_id.

The sealed files are outside the checkout and unreadable to the agent process, which is
launched under an unprivileged UID with no sudo. This is OS permission isolation, not a
kernel namespace: it holds as long as the agent process is not started as root.
"""
import hashlib
import json
import sys
from pathlib import Path

PUBLIC_FIELDS = ["task_id", "instruction", "objects", "zones",
                 "evaluator_version", "execution_budget", "split"]
SEALED_FIELDS = ["expected_goal", "constraints", "template_id",
                 "random_seed", "instance_sha256"]


def opaque_id(spec, salt):
    blob = (salt + "|" + spec["template_id"] + "|" + str(spec["random_seed"])).encode()
    return "HO-" + hashlib.sha256(blob).hexdigest()[:12]


def split_spec(spec, salt):
    oid = opaque_id(spec, salt)
    public = {k: json.loads(json.dumps(spec[k])) for k in PUBLIC_FIELDS}
    public["task_id"] = oid
    sealed = {k: json.loads(json.dumps(spec[k])) for k in SEALED_FIELDS if k in spec}
    sealed["public_task_id"] = oid
    sealed["original_task_id"] = spec["task_id"]
    return oid, public, sealed


def assert_public_is_clean(public):
    """A public task must not carry any answer-bearing STRUCTURE.

    Check KEYS, not prose. An earlier version scanned the whole JSON text for banned
    substrings and rejected a legitimate instruction containing the words "in this
    order": natural language is allowed to say "order", a field named "order" is not.
    Answer fields are structural, so structural checking is both stricter and correct.
    """
    allowed = set(PUBLIC_FIELDS)
    for key in public:
        if key not in allowed:
            raise AssertionError("public task has unexpected key %r" % key)
    for key in ("expected_goal", "constraints", "template_id", "random_seed",
                "instance_sha256"):
        if key in public:
            raise AssertionError("public task leaks %r" % key)
    # no answer-bearing nested keys either
    blob = json.dumps(public.get("objects", [])) + json.dumps(public.get("zones", []))
    for key in ("placement", "unmoved", "visit", "min_tiers", "order"):
        if "\"" + key + "\"" in blob:
            raise AssertionError("public scene leaks field %r" % key)
    tid = public.get("task_id", "")
    if tid.startswith("T0") or "seed" in tid.lower():
        raise AssertionError("public task_id reveals the template/seed")
    return True


def main(argv=None):
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--in-dir", required=True)
    ap.add_argument("--public-dir", required=True)
    ap.add_argument("--salt", required=True)
    args = ap.parse_args(argv)
    pub = Path(args.public_dir)
    pub.mkdir(parents=True, exist_ok=True)
    manifest = []
    for p in sorted(Path(args.in_dir).glob("*.json")):
        spec = json.loads(p.read_text(encoding="utf-8"))
        oid, public, sealed = split_spec(spec, args.salt)
        assert_public_is_clean(public)
        (pub / (oid + ".json")).write_text(json.dumps(public, indent=2) + "\n",
                                           encoding="utf-8")
        manifest.append({"public_task_id": oid, "sealed_path": "/etc/evobot/sealed/" + oid + ".json",
                         "template_id": sealed.get("template_id")})
        # sealed answers are written to stdout for the privileged installer; they never
        # touch this checkout.
        print(json.dumps({"__sealed__": True, "id": oid, "answer": sealed}))
    print(json.dumps({"__manifest__": True, "count": len(manifest), "items": manifest}),
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
