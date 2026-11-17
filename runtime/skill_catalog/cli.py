"""CLI for the declaration-only skill catalog (issue #245).

Exit codes: 0 success, 1 ID not found, 2 JSON/structure/version error.
Errors are emitted as a JSON object with explicit ``error`` and ``reason``;
they never appear inside a successful skills list.
"""
import argparse
import json
import sys

from .core import CatalogError, SkillNotFound, get_skill, list_skills, load_catalog


def _emit(doc):
    json.dump(doc, sys.stdout, ensure_ascii=False, indent=2, allow_nan=False)
    sys.stdout.write("\n")


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python3 -m runtime.skill_catalog",
        description="Query declared robot-action skills (declarations only).")
    parser.add_argument("command", choices=("list", "get"))
    parser.add_argument("--catalog", required=True, help="catalog JSON path")
    parser.add_argument("--id", help="skill ID, required by get")
    args = parser.parse_args(argv)
    if args.command == "get" and not args.id:
        _emit({"error": "USAGE", "reason": "get requires --id"})
        return 2
    try:
        catalog = load_catalog(args.catalog)
    except CatalogError as exc:
        _emit({"error": "CatalogError", "reason": str(exc)})
        return 2
    if args.command == "list":
        _emit({"declaration_only": True, "skills": list_skills(catalog)})
        return 0
    try:
        skill = get_skill(catalog, args.id)
    except SkillNotFound:
        _emit({"error": "SkillNotFound", "reason": "no skill with id %s" % args.id})
        return 1
    _emit({"declaration_only": True, "skill": skill})
    return 0
