#!/usr/bin/env python3
"""Grade a held-out run using the SEALED answer.

This script must run with privilege (it reads /etc/evobot/sealed, root:root 600). The
agent process runs under an unprivileged UID and cannot read those files.

It reconstructs the full spec from the PUBLIC task plus the SEALED answer, then hands it
to the ordinary independent evaluator. No evaluator logic is duplicated or weakened.
"""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "benchmark" / "evaluators"))
import evaluate as ev

SEALED_DIR = Path("/etc/evobot/sealed")


def load_full_spec(public_path):
    public = json.loads(Path(public_path).read_text(encoding="utf-8"))
    answer_path = SEALED_DIR / (public["task_id"] + ".json")
    if not answer_path.is_file():
        raise RuntimeError("sealed answer missing for " + public["task_id"])
    answer = json.loads(answer_path.read_text(encoding="utf-8"))
    if answer.get("public_task_id") != public["task_id"]:
        raise RuntimeError("sealed answer does not belong to this task")
    spec = dict(public)
    for key in ("expected_goal", "constraints", "template_id", "random_seed",
                "instance_sha256"):
        if key in answer:
            spec[key] = answer[key]
    return spec


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--public", required=True)
    ap.add_argument("--observation", required=True)
    ap.add_argument("--out")
    args = ap.parse_args(argv)
    spec = load_full_spec(args.public)
    obs = json.loads(Path(args.observation).read_text(encoding="utf-8"))
    clean = {k: v for k, v in obs.items() if not k.startswith("_")}
    verdict = ev.evaluate(spec, clean)
    text = json.dumps(verdict, indent=2) + "\n"
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
