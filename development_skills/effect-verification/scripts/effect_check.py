"""Require positive evidence that an effect happened.

Three failures in one session shared one root: an action was performed and a conclusion drawn
from the ABSENCE of a complaint rather than from evidence of the effect. Empty diff output
read as no changes, a failed sed read as a successful mutation, and "no tests ran" read as
tests passing.

Each helper here refuses to treat silence as success.
"""
import hashlib
import sys


class EffectNotVerified(Exception):
    """The effect was not demonstrated. Never downgrade this to a warning."""


def digest(path):
    try:
        with open(path, "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()
    except OSError as exc:
        raise EffectNotVerified("cannot read %s: %s" % (path, exc))


def require_changed(path, against):
    """Raise unless the file content actually differs from the reference copy."""
    now, before = digest(path), digest(against)
    if now == before:
        raise EffectNotVerified(
            "%s is byte-identical to %s: the edit did not take effect" % (path, against))
    return now


def require_contains(output, token, what="output"):
    """Raise unless the expected token is present. Absence of error is not presence."""
    if output is None:
        raise EffectNotVerified("%s is None; nothing was captured" % what)
    if token not in output:
        raise EffectNotVerified("%s does not contain %r" % (what, token))
    return True


def require_nonempty(value, what="value"):
    """Raise on None or empty. Empty is ambiguous and must not be read as success."""
    if value is None:
        raise EffectNotVerified("%s is None" % what)
    if isinstance(value, (str, list, dict, tuple)) and len(value) == 0:
        raise EffectNotVerified(
            "%s is empty; empty can mean success or failure, so it proves neither" % what)
    return True


def require_pytest_summary(output):
    """A pytest run with no tests is not a pass.

    'no tests ran' and 'collected 0 items' both mean the suite did not execute.
    """
    if output is None:
        raise EffectNotVerified("no pytest output captured")
    if "no tests ran" in output or "collected 0 items" in output:
        raise EffectNotVerified("pytest collected nothing; this is not a passing run")
    if " passed" not in output:
        raise EffectNotVerified("pytest output has no 'passed' summary: %r" % output[-200:])
    return True


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    if not argv:
        print("usage: effect_check.py changed <file> --against <backup>")
        print("       effect_check.py contains <text> <token>")
        return 2
    command = argv[0]
    try:
        if command == "changed":
            path = argv[1]
            against = argv[argv.index("--against") + 1]
            require_changed(path, against)
            print("EFFECT_VERIFIED: %s differs from %s" % (path, against))
            return 0
        if command == "contains":
            require_contains(argv[1], argv[2])
            print("EFFECT_VERIFIED: token present")
            return 0
    except EffectNotVerified as exc:
        print("EFFECT_NOT_VERIFIED: %s" % exc)
        return 1
    except (IndexError, ValueError):
        print("usage error")
        return 2
    print("unknown command %r" % command)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
