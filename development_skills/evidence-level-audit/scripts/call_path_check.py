"""Check that a symbol which is trusted is actually called from where it must be.

A verifier with a full test suite and no caller is a document, not a gate. That happened in
this session: verify.py passed 65 tests while evaluate.py never imported it, and the real
consequence was a wire-up bug that made every genuine push grade as failed.

This check is deliberately narrow: it answers 'is this symbol referenced from these paths',
not 'is the call correct'. The narrowness is what makes it cheap enough to run always.
"""
import argparse
import os
import sys


def files_under(root):
    if os.path.isfile(root):
        return [root]
    found = []
    for base, _dirs, names in os.walk(root):
        for name in names:
            if name.endswith((".py", ".sh", ".md")):
                found.append(os.path.join(base, name))
    return sorted(found)


def callers_of(symbol, paths):
    """Return (files mentioning symbol, files not mentioning it)."""
    hits, misses = [], []
    for path in paths:
        try:
            with open(path, encoding="utf-8", errors="replace") as handle:
                text = handle.read()
        except OSError:
            continue
        (hits if symbol in text else misses).append(path)
    return hits, misses


def main(argv=None):
    ap = argparse.ArgumentParser(description="is a trusted symbol actually referenced")
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--expect-caller", required=True, action="append",
                    help="directory or file that must reference the symbol")
    args = ap.parse_args(sys.argv[1:] if argv is None else argv)

    ok = True
    for root in args.expect_caller:
        paths = files_under(root)
        if not paths:
            print("EMPTY  %s has no files to inspect" % root)
            ok = False
            continue
        hits, _misses = callers_of(args.symbol, paths)
        if hits:
            print("OK     %s: %d file(s) reference %r" % (root, len(hits), args.symbol))
        else:
            print("ABSENT %s: no file references %r -- it is a document, not a gate"
                  % (root, args.symbol))
            ok = False
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
