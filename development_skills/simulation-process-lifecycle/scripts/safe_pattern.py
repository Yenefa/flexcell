"""Build and check safe pkill -f patterns.

The bracket trick exists so that pkill -f does not match its own command line: the pattern
[c]arry_server matches the literal text carry_server but not the literal text [c]arry_server.
That only works when the bracket wraps EXACTLY ONE character.

Wrapping the whole name, as in [carry_server], turns it into a character class that matches
any single one of those letters. That pattern matched 4 of 4 unrelated command lines in this
session and killed a whole execution chain before it started.
"""
import argparse
import re
import subprocess
import sys

MAX_SAFE_MATCHES = 40


def safe_pattern(name):
    """Return a pattern that matches name but not itself.

    Only the first character is bracketed. Anything else is not this trick.
    """
    if not name:
        raise ValueError("empty process name")
    if name.startswith("["):
        raise ValueError("name already looks like a bracket pattern: %r" % name)
    return "[" + name[0] + "]" + name[1:]


def is_hazardous(pattern):
    """True when a bracket expression spans more than one character.

    A multi-character bracket is a character class, not the self-exclusion trick, and it
    will match far more processes than intended.
    """
    for match in re.finditer(r"\[([^\]]*)\]", pattern):
        if len(match.group(1)) != 1:
            return True
    return False


def count_matches(pattern):
    """How many command lines the pattern matches, excluding this process tree."""
    try:
        out = subprocess.run(["pgrep", "-f", pattern], capture_output=True, text=True)
    except FileNotFoundError:
        return -1
    return len([line for line in out.stdout.splitlines() if line.strip()])


def main(argv=None):
    ap = argparse.ArgumentParser(description="safe pkill -f patterns")
    ap.add_argument("name", help="process name, e.g. carry_server")
    ap.add_argument("--match-test", action="store_true",
                    help="print what the pattern matches and kill nothing")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    try:
        pattern = safe_pattern(args.name)
    except ValueError as exc:
        print("REFUSED: %s" % exc)
        return 2

    if is_hazardous(pattern):
        print("REFUSED: %r is a character class, not a self-exclusion" % pattern)
        return 2

    if args.match_test:
        n = count_matches(pattern)
        print("pattern  %s" % pattern)
        print("matches  %d" % n)
        if n < 0:
            print("REFUSED: pgrep unavailable, so the match count is unknown")
            return 2
        if n >= MAX_SAFE_MATCHES:
            print("REFUSED: %d matches is almost certainly a mis-pattern" % n)
            return 2
        if n == 0:
            print("NOTE: nothing matches, so there is nothing to clean")
        return 0

    print(pattern)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
